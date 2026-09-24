import asyncio
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Ont
from app.services.snmp_ont import snmp_walk_all_ports


async def main():
    async with SessionLocal() as session:
        rows = (await session.execute(select(Ont).where(Ont.olt_id == 1))).scalars().all()
    db_serials = sorted({o.serial for o in rows if o.serial})
    print(f"ONT в БД: {len(db_serials)}")

    ports = await snmp_walk_all_ports("10.10.1.105", "public")
    print(f"SNMP вернул портов для {len(ports)} серийников")
    for key in list(ports.keys())[:5]:
        print(f"  key={key!r}  портов: {len(ports[key])}")

    print(f"\n=== Проверка startswith(human[:10]) ===")
    matched = 0
    for key in ports.keys():
        prefix = key[:10]
        matches = [real for real in db_serials if real.startswith(prefix)]
        if matches:
            matched += 1
        print(f"  {key!r} → matches: {matches}")

    print(f"\nСовпадений: {matched} из {len(ports)}")


asyncio.run(main())