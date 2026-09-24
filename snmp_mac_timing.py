import asyncio
import time
from app.services.snmp_ont import snmp_get_ont_macs

async def main():
    ip = "10.10.1.105"
    community = "public"
    serial = "ELTX62151198"   # ONT с MAC 2C:4D:54:83:8B:70

    for i in range(3):
        t0 = time.time()
        macs = await snmp_get_ont_macs(ip, community, serial)
        dt = time.time() - t0
        print(f"[{i+1}] {dt:.2f} сек, MAC-ов: {len(macs)}")
        for m in macs:
            print(f"    {m}")
        await asyncio.sleep(1)

asyncio.run(main())