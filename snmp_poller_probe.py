"""Ручной прогон poll_macs_one_olt для одной OLT."""
import asyncio
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Olt, OntMacCache
from app.services.snmp_poller import poll_macs_one_olt, _load_cfg


async def main():
    async with SessionLocal() as session:
        olt = (await session.execute(select(Olt))).scalars().first()
        if not olt:
            print("Нет OLT в БД")
            return
        cfg = await _load_cfg(session)
        if not cfg:
            print("Нет настроек")
            return

        print(f"OLT {olt.ip}, community={cfg.snmp_community_ro}")
        updated = await poll_macs_one_olt(session, olt, cfg)
        print(f"Обновлено ONT: {updated}")

        # Показать кеш
        rows = (await session.execute(
            select(OntMacCache).where(OntMacCache.olt_id == olt.id)
        )).scalars().all()
        print(f"\nВсего записей в кеше: {len(rows)}")
        by_serial: dict[str, list] = {}
        for r in rows:
            by_serial.setdefault(r.serial, []).append(r.mac)
        for serial in sorted(by_serial.keys())[:5]:
            macs = by_serial[serial]
            print(f"  {serial}: {len(macs)} MAC ({macs[0] if macs else '—'})")
        if len(by_serial) > 5:
            print(f"  ... и ещё {len(by_serial) - 5} ONT")


asyncio.run(main())