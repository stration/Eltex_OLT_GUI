"""Проверка snmp_walk_all_ports с полными серийниками."""
import asyncio
from app.services.snmp_ont import snmp_walk_all_ports


IP = "10.10.1.105"
COMMUNITY = "public"


async def main():
    print(f"SNMP {IP}")
    ports_by_serial = await snmp_walk_all_ports(IP, COMMUNITY)
    print(f"\nВсего ONT с портами: {len(ports_by_serial)}")
    for serial in sorted(ports_by_serial.keys()):
        ports = ports_by_serial[serial]
        links = sum(1 for p in ports if p.get("link") == "up")
        print(f"  {serial}: {len(ports)} портов ({links} up)")
        for p in ports[:2]:
            print(f"    port {p['port_id']}: link={p.get('link')} speed={p.get('speed')} duplex={p.get('duplex')}")


asyncio.run(main())