"""Периодический опрос состояния ONT через SNMP.

Раз в 2 минуты:
- bulk-walk по ltp8xONTConfigTable (gpon_port, ont_id, description — все
  сконфигурированные ONT);
- bulk-walk по ltp8xONTStateTable (state, rssi, version, equipment_id);
- Создаём отсутствующие в БД ONT (автосоздание из Config-таблицы);
- Обновляем существующие ONT (gpon_port, ont_id, state, rssi, version,
  equipment_id, last_seen_at);
- Пишем RSSI-историю (раз в 5 минут или при изменении > 0.5 dBm).

gpon_port и ont_id — источник правды ConfigTable (колонки 3 и 4).
ltp8xONTStateChannel (колонка 3 в StateTable) всегда возвращает 0
и не используется.

ONT из SNMP, которых нет в БД, — создаются автоматически.
ONT, которых нет в SNMP, но есть в БД, — НЕ удаляются.
"""
import asyncio
from datetime import datetime, timedelta
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Olt, Ont, RssiHistory, Settings as SettingsModel
from .snmp_ont import (
    snmp_walk_all_states,
    snmp_walk_all_configs,
    config_from_raw,
)


RSSI_MIN_INTERVAL = timedelta(minutes=5)
RSSI_DELTA_THRESHOLD = 0.5


async def _load_cfg(session: AsyncSession) -> SettingsModel | None:
    return (await session.execute(
        select(SettingsModel).where(SettingsModel.id == 1)
    )).scalar_one_or_none()


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


async def poll_one_olt(session: AsyncSession, olt_id: int) -> int:
    """
    Опрашивает один OLT через SNMP.
    Создаёт отсутствующие ONT, обновляет существующие.
    Возвращает количество обновлённых + созданных ONT.
    """
    olt = await session.get(Olt, olt_id)
    if olt is None:
        return 0

    cfg = await _load_cfg(session)
    if cfg is None:
        return 0

    # 1. Config-таблица — все сконфигурированные ONT
    try:
        configs = await snmp_walk_all_configs(olt.ip, cfg.snmp_community_ro)
    except Exception as e:
        logger.warning(f"SNMP config {olt.ip}: {type(e).__name__}: {e}")
        configs = {}

    # 2. State-таблица — актуальные статусы
    try:
        states = await snmp_walk_all_states(olt.ip, cfg.snmp_community_ro)
    except Exception as e:
        logger.warning(f"SNMP state {olt.ip}: {type(e).__name__}: {e}")
        states = {}

    if not configs and not states:
        logger.warning(f"SNMP state/config {olt.ip}: оба пусты")
        return 0

    # Существующие ONT этого OLT
    existing = (await session.execute(
        select(Ont).where(Ont.olt_id == olt.id)
    )).scalars().all()
    by_serial = {o.serial: o for o in existing if o.serial}

    now = datetime.utcnow()
    updated = 0
    created = 0

    # Все серийники из SNMP (Config ∪ State)
    all_serials = set(configs.keys()) | set(states.keys())

    for serial in all_serials:
        ont = by_serial.get(serial)

        # --- Автосоздание отсутствующей ONT ---
        if ont is None:
            raw_cfg = configs.get(serial)
            st = states.get(serial)

            # Из Config — обязательные поля (gpon_port, ont_id)
            snmp_port = None
            snmp_ont_id = None
            description = None
            if raw_cfg:
                parsed = config_from_raw(raw_cfg)
                snmp_port = parsed.get("gpon_port")
                snmp_ont_id = parsed.get("ont_id")
                description = parsed.get("description")

            # Если в Config нет — пробуем из State (там канал/ID могут быть 0)
            # Не создаём, если нет хотя бы gpon_port и ont_id.
            if snmp_port is None or snmp_ont_id is None:
                logger.debug(
                    f"ONT {serial}: пропущено автосоздание — нет "
                    f"gpon_port/ont_id в Config"
                )
                continue

            # Если ONT есть в Config, но её state = unknown/free —
            # это offline-ONT в конфиге, а не «неизвестная»
            raw_state = (st.get("state") if st else None)
            status = raw_state or "OFFLINE"
            if status in ("unknown", "UNKNOWN", "free", "unactivated"):
                status = "OFFLINE"

            new_ont = Ont(
                olt_id=olt.id,
                serial=serial,
                gpon_port=snmp_port,
                ont_id=snmp_ont_id,
                status=status,
                rssi_db=(st.get("rssi_db") if st else None),
                version=(st.get("version") if st else None),
                equipment_id=(st.get("equipment_id") if st else None),
                description=description,
                last_seen_at=(
                    now if st and st.get("state") == "OK" else None
                ),
                updated_at=now,
            )
            session.add(new_ont)
            await session.flush()   # получаем new_ont.id

            # RSSI-история для только что созданной активной ONT
            if (
                new_ont.status == "OK"
                and new_ont.rssi_db is not None
            ):
                await _maybe_record_rssi(session, new_ont, new_ont.rssi_db, now)

            created += 1
            logger.info(
                f"ONT {serial}: создана (gpon_port={snmp_port}, "
                f"ont_id={snmp_ont_id}, status={new_ont.status})"
            )
            updated += 1
            continue

        # --- Обновление существующей ONT ---

        # gpon_port / ont_id из ConfigTable
        raw_cfg = configs.get(serial)
        if raw_cfg:
            parsed = config_from_raw(raw_cfg)
            snmp_port = parsed.get("gpon_port")
            snmp_ont_id = parsed.get("ont_id")
            if snmp_port is not None and ont.gpon_port != snmp_port:
                logger.info(f"ONT {serial}: gpon_port {ont.gpon_port} → {snmp_port}")
                ont.gpon_port = snmp_port
            if snmp_ont_id is not None and ont.ont_id != snmp_ont_id:
                logger.info(f"ONT {serial}: ont_id {ont.ont_id} → {snmp_ont_id}")
                ont.ont_id = snmp_ont_id
            if parsed.get("description") is not None:
                ont.description = parsed["description"]

        # status / rssi / version / equipment_id из StateTable
        st = states.get(serial)
        if st:
            new_state = st.get("state")
            if new_state:
                # Если state = unknown/free, но ONT в конфиге — это OFFLINE
                if new_state in ("unknown", "UNKNOWN", "free", "unactivated"):
                    new_state = "OFFLINE"
                ont.status = new_state

            rssi_db = st.get("rssi_db")
            if rssi_db is not None:
                ont.rssi_db = rssi_db

            if st.get("version"):
                ont.version = st["version"]
            if st.get("equipment_id"):
                ont.equipment_id = st["equipment_id"]

            if new_state == "OK":
                ont.last_seen_at = now

            if new_state == "OK" and rssi_db is not None:
                await _maybe_record_rssi(session, ont, rssi_db, now)

        ont.updated_at = now
        updated += 1

    await session.commit()

    if created:
        logger.info(f"{olt.ip}: автосоздано {created} ONT")

    return updated


async def poll_all(session_maker, concurrency: int = 3) -> dict:
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
                logger.exception(f"ont_state_poller one {olt_id}: {e}")
                return olt_id, 0

    results = await asyncio.gather(*(one(i) for i in olt_ids))
    results = [r for r in results if r is not None]

    total = sum(r[1] for r in results)
    if total:
        logger.info(f"ONT-SNMP poll: {total} ONT на {len(olt_ids)} OLT")
    return dict(results)