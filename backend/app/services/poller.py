"""Периодическая проверка доступности OLT (ping + SNMP)."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy import select
from datetime import datetime

from ..db import SessionLocal
from ..models import Olt, Settings as SettingsModel
from .checker import check_many

scheduler = AsyncIOScheduler(timezone="UTC")


async def _tick():
    async with SessionLocal() as session:
        cfg = (await session.execute(select(SettingsModel).where(SettingsModel.id == 1))).scalar_one_or_none()
        if cfg is None:
            return
        rows = (await session.execute(select(Olt))).scalars().all()
        if not rows:
            return
        pairs = [(o.id, o.ip) for o in rows]
        results = await check_many(pairs, cfg.snmp_community_ro)
        by_id = {o.id: o for o in rows}
        for olt_id, res in results:
            o = by_id[olt_id]
            o.status = "online" if (res["ping_ok"] or res["snmp_ok"]) else "offline"
            o.last_ping_ms = res["ping_ms"]
            if o.status == "online":
                o.last_seen_at = datetime.utcnow()
            if res["model"]:
                o.model = res["model"]
            if res["hw_revision"]:
                o.hw_revision = res["hw_revision"]
        await session.commit()


def start_poller(interval_sec: int = 60):
    scheduler.add_job(_tick, "interval", seconds=interval_sec, id="ping_all", replace_existing=True)
    scheduler.start()
    logger.info(f"Poller запущен, интервал {interval_sec} с")


def stop_poller():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass