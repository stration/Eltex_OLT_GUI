"""Периодический опрос ONT через CLI: `show interface ont 0-N configured`.

Используется как fallback, если SNMP-поллер (ont_state_poller) не дал данных.
"""
import asyncio
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Olt, Ont, RssiHistory, Settings as SettingsModel
from ..security import decrypt
from .cli_service import ssh_run_cmd, telnet_run_cmd, CliError
from .parsers import parse_onts_configured


RSSI_MIN_INTERVAL = timedelta(minutes=5)
RSSI_DELTA_THRESHOLD = 0.5


async def _run_cli(olt: Olt, cfg: SettingsModel, cmd: str) -> str:
    if not cfg.cli_user or not cfg.cli_password_enc:
        raise CliError("Не заданы учётки CLI")
    password = decrypt(cfg.cli_password_enc) or ""
    if cfg.default_transport == "ssh":
        return await ssh_run_cmd(olt.ip, cfg.cli_user, password, cmd, timeout=25)
    else:
        return await telnet_run_cmd(olt.ip, cfg.cli_user, password, cmd, timeout=25)


async def poll_one_olt(olt_id: int, session: AsyncSession) -> int:
    olt = await session.get(Olt, olt_id)
    if olt is None:
        return 0
    cfg = (await session.execute(
        select(SettingsModel).where(SettingsModel.id == 1)
    )).scalar_one_or_none()
    if cfg is None:
        return 0

    max_port = 7 if (olt.model or "").endswith("8X") else 3
    cmd = f"show interface ont 0-{max_port} configured"

    try:
        output = await _run_cli(olt, cfg, cmd)
    except asyncio.CancelledError:
        raise
    except CliError as e:
        logger.warning(f"ONT poll {olt.ip}: {e}")
        return 0
    except Exception as e:
        logger.exception(f"ONT poll {olt.ip}: {e}")
        return 0

    rows = parse_onts_configured(output)
    if not rows:
        logger.warning(
            f"ONT poll {olt.ip}: распарсено 0 строк (получено {len(output)} байт)"
        )
        return 0

    now = datetime.utcnow()

    existing = (await session.execute(
        select(Ont).where(Ont.olt_id == olt.id)
    )).scalars().all()
    by_key: dict[tuple[int, int], Ont] = {(o.gpon_port, o.ont_id): o for o in existing}

    for row in rows:
        key = (row.gpon_port, row.ont_id)
        ont = by_key.get(key)
        if ont is None:
            ont = Ont(
                olt_id=olt.id, gpon_port=row.gpon_port, ont_id=row.ont_id,
                serial=row.serial, status=row.status,
            )
            session.add(ont)
            await session.flush()
        else:
            ont.serial = row.serial
            ont.status = row.status

        ont.rssi_db = row.rssi_db
        ont.version = row.version
        ont.equipment_id = row.equipment_id
        ont.description = row.description
        if row.status == "OK":
            ont.last_seen_at = now
        ont.updated_at = now

        if row.rssi_db is not None and row.status == "OK":
            await _maybe_record_rssi(session, ont, row.rssi_db, now)

    await session.commit()
    return len(rows)


async def _maybe_record_rssi(
    session: AsyncSession, ont: Ont, rssi: float, now: datetime,
):
    last = (await session.execute(
        select(RssiHistory)
        .where(RssiHistory.ont_pk == ont.id)
        .order_by(RssiHistory.ts.desc())
        .limit(1)
    )).scalar_one_or_none()

    need_write = False
    if last is None:
        need_write = True
    else:
        delta = abs(last.rssi_db - rssi)
        age = now - last.ts
        if delta > RSSI_DELTA_THRESHOLD or age > RSSI_MIN_INTERVAL:
            need_write = True

    if need_write:
        session.add(RssiHistory(ont_pk=ont.id, ts=now, rssi_db=rssi))


async def poll_all_olts(session_maker, concurrency: int = 3):
    async with session_maker() as session:
        olts = (await session.execute(select(Olt))).scalars().all()
        olt_ids = [o.id for o in olts]

    if not olt_ids:
        return {}

    sem = asyncio.Semaphore(concurrency)

    async def one(olt_id: int):
        async with sem:
            try:
                async with session_maker() as session:
                    return olt_id, await poll_one_olt(olt_id, session)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"poll_one_olt {olt_id}: {e}")
                return olt_id, 0

    results = await asyncio.gather(*(one(i) for i in olt_ids))
    results = [r for r in results if r is not None]

    total = sum(r[1] for r in results)
    if total:
        logger.info(f"ONT poll: {total} ONT на {len(olt_ids)} OLT")
    return dict(results)