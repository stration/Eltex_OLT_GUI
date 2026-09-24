"""Проверка SNMP-таблицы ltp8xONTStateTable."""
import asyncio
from app.services.snmp_ont import _bulk_walk

IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.3.1.1"


async def main():
    rows = await _bulk_walk(IP, COMMUNITY, BASE)
    print(f"Всего: {len(rows)}\n")
    for oid, val in rows[:40]:
        print(f"  {oid} = {val}")


asyncio.run(main())