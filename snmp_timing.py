import asyncio
import time
from app.services.snmp_ont import snmp_get_ont_ports

async def main():
    ip = "10.10.1.105"
    community = "public"
    serial = "ELTX89091F7C"   # замените на серийник вашей ONT 1/2

    for i in range(3):
        t0 = time.time()
        ports = await snmp_get_ont_ports(ip, community, serial)
        dt = time.time() - t0
        print(f"[{i+1}] {dt:.2f} сек, портов: {len(ports)}")
        await asyncio.sleep(1)

asyncio.run(main())