"""Ручной запуск ont_state_poller для одной OLT + диагностика."""
import asyncio
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Olt, Ont
from app.services.ont_state_poller import poll_one_olt
from app.services.snmp_ont import snmp_walk_all_states


IP = "10.10.1.105"  # ← поменяйте, если OLT другой


async def main():
    async with SessionLocal() as session:
        olt = (await session.execute(select(Olt))).scalars().first()
        if not olt:
            print("Нет OLT в БД")
            return
        print(f"OLT id={olt.id} ip={olt.ip}")

        # 1. Что видит SNMP
        print("\n=== SNMP: sample из State-таблицы ===")
        states = await snmp_walk_all_states(olt.ip, "public")
        print(f"Всего в SNMP: {len(states)}")
        # Смотрим первые 5 и разбираем порт/ont_id
        for serial in sorted(states.keys())[:5]:
            s = states[serial]
            print(f"  {serial}: gpon_port={s.get('gpon_port')!r} ont_id={s.get('ont_id')!r} state={s.get('state')!r}")
        # Проверим конкретный
        probe = "ELTX62151198"
        if probe in states:
            s = states[probe]
            print(f"  {probe}: gpon_port={s.get('gpon_port')!r} ont_id={s.get('ont_id')!r}")

        # 2. Что в БД ДО поллера
        print("\n=== БД до поллера ===")
        rows = (await session.execute(select(Ont).where(Ont.olt_id == olt.id))).scalars().all()
        from collections import Counter
        by_port = Counter(o.gpon_port for o in rows)
        print(f"Всего ONT: {len(rows)}")
        for port in sorted(by_port.keys()):
            print(f"  gpon_port={port}: {by_port[port]} ONT")
        for o in rows[:5]:
            print(f"  {o.serial}: gpon_port={o.gpon_port} ont_id={o.ont_id}")

        # 3. Запускаем поллер
        print("\n=== Запуск poll_one_olt ===")
        updated = await poll_one_olt(session, olt.id)
        print(f"Обновлено: {updated}")

        # 4. Что в БД ПОСЛЕ поллера
        print("\n=== БД после поллера ===")
        rows = (await session.execute(select(Ont).where(Ont.olt_id == olt.id))).scalars().all()
        by_port = Counter(o.gpon_port for o in rows)
        for port in sorted(by_port.keys()):
            print(f"  gpon_port={port}: {by_port[port]} ONT")
        for o in rows[:5]:
            print(f"  {o.serial}: gpon_port={o.gpon_port} ont_id={o.ont_id}")


asyncio.run(main())