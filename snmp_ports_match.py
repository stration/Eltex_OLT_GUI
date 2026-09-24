import asyncio
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Ont
from app.services.snmp_ont import snmp_walk_all_ports, serial_hex_to_human


async def main():
    # Серийники из БД
    async with SessionLocal() as session:
        rows = (await session.execute(select(Ont).where(Ont.olt_id == 1))).scalars().all()
    db_serials = sorted({o.serial for o in rows if o.serial})
    print(f"ONT в БД: {len(db_serials)}")
    for s in db_serials[:5]:
        print(f"  {s}")

    # Порты из SNMP
    ports = await snmp_walk_all_ports("10.10.1.105", "public")
    print(f"\nSNMP вернул портов для {len(ports)} серийников")
    for hex_str in list(ports.keys())[:5]:
        human = serial_hex_to_human(hex_str)
        print(f"  {hex_str} → {human!r}  (длина: {len(human) if human else 0})")

    # Проверка сопоставления
    print(f"\n=== Проверка startswith(human[:10]) ===")
    for hex_str in list(ports.keys())[:5]:
        human = serial_hex_to_human(hex_str)
        if not human:
            print(f"  {hex_str}: human=None")
            continue
        prefix = human[:10]
        matches = [real for real in db_serials if real.startswith(prefix)]
        print(f"  {hex_str} → human={human!r} prefix={prefix!r} → matches: {matches}")


asyncio.run(main())