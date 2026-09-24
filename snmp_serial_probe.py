# D:\build\ltp-gui\backend\snmp_serial_probe.py
import asyncio
from app.services.snmp_ont import _bulk_walk, PORTS_BASE_OID

async def main():
    raw = await _bulk_walk("10.10.1.105", "public", PORTS_BASE_OID)
    serials = set()
    for oid_str, val in raw:
        tail = oid_str[len(PORTS_BASE_OID) + 1:]
        parts = tail.split(".")
        if len(parts) < 11:
            continue
        # Байты 2..9 — серийник
        serial_bytes = [int(x) for x in parts[2:10]]
        hex_str = "".join(f"{b:02X}" for b in serial_bytes)
        serials.add(hex_str)
    print(f"Всего серийников: {len(serials)}")
    for s in sorted(serials):
        print(f"  {s}  (hex) → {bytes.fromhex(s).decode('ascii', errors='replace')!r}")

asyncio.run(main())