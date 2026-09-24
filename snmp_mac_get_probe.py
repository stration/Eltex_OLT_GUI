"""Проверка snmp_get_ont_macs для конкретной ONT."""
import asyncio
from app.services.snmp_ont import snmp_get_ont_macs


IP = "10.10.1.105"
COMMUNITY = "public"
SERIAL = "ELTX62151198"


async def main():
    print(f"SNMP {IP}, community={COMMUNITY}, serial={SERIAL}")
    macs = await snmp_get_ont_macs(IP, COMMUNITY, SERIAL)
    print(f"\nВсего MAC: {len(macs)}")
    for m in macs:
        print(f"  {m}")


asyncio.run(main())