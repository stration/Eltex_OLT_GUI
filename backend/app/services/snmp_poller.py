"""Периодический поллер MAC-ов и портов ONT.

MAC-адреса — через SNMP (ltp8xONTAddressTable), один bulk-walk,
группировка по полному серийнику 'ELTX...'.
Порты — через SNMP (ltp8xONTUNIPortsStateTable).
Серийник в OID портов обрезан до 10 символов, поэтому сопоставляем
по первым 10 символам с серийниками из БД. Если префикс неоднозначен
(>1 ONT подходит), пропускаем — для таких ONT порты пойдут через CLI.

Раз в 5 минут:
1. SNMP → MAC-и всех ONT → ont_macs_cache
2. SNMP → порты всех ONT → ont_ports_cache (там, где однозначно)
"""
import asyncio
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Olt, Ont, Settings as SettingsModel, OntMacCache, OntPortCache
from ..security import decrypt
from .cli_service import ssh_run_cmd, telnet_run_cmd, CliError
from .snmp_ont import snmp_walk_all_ports, snmp_walk_all_macs


async def _run_cli(olt: Olt, cfg: SettingsModel, cmd: str, timeout: float = 60.0) -> str:
    """Оставлено для обратной совместимости (пока где-то нужен CLI)."""
    if not cfg.cli_user or not cfg.cli_password_enc:
        raise CliError("Не заданы учётки CLI")
    password = decrypt(cfg.cli_password_enc) or ""
    if cfg.default_transport == "ssh":
        return await ssh_run_cmd(olt.ip, cfg.cli_user, password, cmd, timeout=timeout)
    else:
        return await telnet_run_cmd(olt.ip, cfg.cli_user, password, cmd, timeout=timeout)


async def _load_cfg(session: AsyncSession) -> SettingsModel | None:
    return (await session.execute(
        select(SettingsModel).where(SettingsModel.id == 1)
    )).scalar_one_or_none()


# ----------------------------------------------------------------------
# MAC-адреса: SNMP (по полному серийнику)
# ----------------------------------------------------------------------

async def poll_macs_one_olt(session: AsyncSession, olt: Olt, cfg: SettingsModel) -> int:
    onts = (await session.execute(
        select(Ont).where(Ont.olt_id == olt.id)
    )).scalars().all()

    if not onts:
        return 0

    try:
        macs_by_serial = await snmp_walk_all_macs(olt.ip, cfg.snmp_community_ro)
    except Exception as e:
        logger.warning(f"SNMP macs {olt.ip}: {type(e).__name__}: {e}")
        return 0

    if not macs_by_serial:
        logger.warning(f"SNMP macs {olt.ip}: пустой ответ")
        # Не удаляем кеш — возможно, временная ошибка
        return 0

    updated = 0
    for ont in onts:
        if not ont.serial:
            continue
        rows = macs_by_serial.get(ont.serial, [])
        # Пишем даже пустой список — чтобы почистить старые MAC-и, если они исчезли
        await _replace_macs(session, olt.id, ont.serial, rows)
        if rows:
            updated += 1

    await session.commit()
    return updated


# ----------------------------------------------------------------------
# Порты: SNMP (по первым 10 символам серийника)
# ----------------------------------------------------------------------

async def poll_ports_one_olt(session: AsyncSession, olt: Olt, cfg: SettingsModel) -> int:
    onts = (await session.execute(
        select(Ont).where(Ont.olt_id == olt.id)
    )).scalars().all()

    if not onts:
        return 0

    serials = [o.serial for o in onts if o.serial]
    if not serials:
        return 0

    try:
        ports_by_serial = await snmp_walk_all_ports(olt.ip, cfg.snmp_community_ro)
    except Exception as e:
        logger.warning(f"SNMP ports {olt.ip}: {type(e).__name__}: {e}")
        return 0

    if not ports_by_serial:
        logger.warning(f"SNMP ports {olt.ip}: пустой ответ")
        return 0

    # Ключ в ports_by_serial — обрезанный серийник (10 символов, 'ELTX...').
    # Сопоставляем с полными серийниками из БД.
    # Если префиксу соответствует >1 ONT — пропускаем (пойдёт через CLI),
    # иначе можем записать чужие порты.
    updated = 0
    skipped_ambiguous = 0

    for human_key, ports in ports_by_serial.items():
        candidates = [s for s in serials if s.startswith(human_key)]

        if not candidates:
            continue
        if len(candidates) > 1:
            skipped_ambiguous += len(candidates)
            logger.debug(
                f"poll ports {olt.ip}: префикс {human_key} соответствует "
                f"{len(candidates)} ONT ({candidates}), пропущено"
            )
            continue

        matched_serial = candidates[0]
        await _replace_ports(session, olt.id, matched_serial, ports)
        updated += 1

    await session.commit()

    if skipped_ambiguous:
        logger.info(
            f"poll ports {olt.ip}: обновлено {updated} ONT, "
            f"пропущено {skipped_ambiguous} (неоднозначные префиксы)"
        )
    return updated


# ----------------------------------------------------------------------
# Замены в БД
# ----------------------------------------------------------------------

async def _replace_macs(
    session: AsyncSession, olt_id: int, serial: str, rows: list[dict],
):
    await session.execute(
        delete(OntMacCache).where(
            OntMacCache.olt_id == olt_id,
            OntMacCache.serial == serial,
        )
    )
    for r in rows:
        session.add(OntMacCache(
            olt_id=olt_id,
            serial=serial,
            mac=r.get("mac"),
            gem=r.get("gem"),
            uvid=r.get("uvid"),
            cvid=r.get("cvid"),
            svid=r.get("svid"),
        ))


async def _replace_ports(
    session: AsyncSession, olt_id: int, serial: str, rows: list[dict],
):
    await session.execute(
        delete(OntPortCache).where(
            OntPortCache.olt_id == olt_id,
            OntPortCache.serial == serial,
        )
    )
    for r in rows:
        session.add(OntPortCache(
            olt_id=olt_id,
            serial=serial,
            port_id=r.get("port_id"),
            link=r.get("link"),
            speed=r.get("speed"),
            duplex=r.get("duplex"),
            poe_state=r.get("poe_state"),
        ))


# ----------------------------------------------------------------------
# Прогон по всем OLT
# ----------------------------------------------------------------------

async def poll_one_olt(session: AsyncSession, olt_id: int) -> dict:
    olt = await session.get(Olt, olt_id)
    if olt is None:
        return {"macs_updated": 0, "ports_updated": 0, "error": "OLT не найден"}

    cfg = await _load_cfg(session)
    if cfg is None:
        return {"macs_updated": 0, "ports_updated": 0, "error": "Настройки не заданы"}

    macs_updated = 0
    try:
        macs_updated = await poll_macs_one_olt(session, olt, cfg)
        logger.info(f"poll macs {olt.ip}: обновлено {macs_updated} ONT")
    except Exception as e:
        logger.exception(f"poll macs {olt.ip}: {e}")

    ports_updated = 0
    try:
        ports_updated = await poll_ports_one_olt(session, olt, cfg)
        logger.info(f"poll ports {olt.ip}: обновлено {ports_updated} ONT")
    except Exception as e:
        logger.exception(f"poll ports {olt.ip}: {e}")

    return {"macs_updated": macs_updated, "ports_updated": ports_updated, "error": None}


async def poll_all(session_maker, concurrency: int = 1) -> dict:
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
                    return olt_id, await poll_one_olt(session, olt_id)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"snmp_poller one {olt_id}: {e}")
                return olt_id, {"macs_updated": 0, "ports_updated": 0, "error": str(e)}

    results = await asyncio.gather(*(one(i) for i in olt_ids))
    results = [r for r in results if r is not None]
    total_macs = sum(r[1].get("macs_updated", 0) for r in results)
    total_ports = sum(r[1].get("ports_updated", 0) for r in results)
    if total_macs or total_ports:
        logger.info(f"MAC-поллер: {total_macs} ONT (MAC), {total_ports} ONT (порты)")
    return dict(results)