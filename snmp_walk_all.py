import asyncio
import time
from app.services.snmp_ont import snmp_walk_all_ports, snmp_walk_all_macs

async def main():
    ip = "10.10.1.105"
    community = "public"

    t0 = time.time()
    ports = await snmp_walk_all_ports(ip, community)
    dt = time.time() - t0
    print(f"=== snmp_walk_all_ports: {dt:.2f} сек, ONT: {len(ports)} ===")
    for serial_hex, rows in list(ports.items())[:3]:
        print(f"  {serial_hex}: {len(rows)} портов")
        for r in rows[:2]:
            print(f"    {r}")

    t0 = time.time()
    macs = await snmp_walk_all_macs(ip, community)
    dt = time.time() - t0
    print(f"\n=== snmp_walk_all_macs: {dt:.2f} сек, ONT: {len(macs)} ===")
    for serial_hex, rows in list(macs.items())[:3]:
        print(f"  {serial_hex}: {len(rows)} MAC")
        for r in rows[:2]:
            print(f"    {r}")

asyncio.run(main())