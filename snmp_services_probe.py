import asyncio
from app.services.snmp_ont import _bulk_walk

IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.3.25.1"

# ELTX62150F1C → 0x62 0x15 0x0F 0x1C
# В OID байты серийника: 8, 69, 76, 84, 88, 98, 21, 15, 28
FILTER = "98.21.15.28"


async def main():
    rows = await _bulk_walk(IP, COMMUNITY, BASE)
    print(f"Всего: {len(rows)}")
    count = 0
    for oid, val in rows:
        if FILTER in str(oid):
            print(f"  {oid} = {val}")
            count += 1
    print(f"\nДля ELTX62150F1C: {count}")


asyncio.run(main())