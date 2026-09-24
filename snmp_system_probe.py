"""Проверка системных OID ltp8xStandalone."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, getCmd,
)


IP = "10.10.1.105"          # ← поменяйте при необходимости
COMMUNITY = "public"


OIDS = {
    "uptime":            "1.3.6.1.4.1.35265.1.22.1.1.7.0",
    "firmware_rev":      "1.3.6.1.4.1.35265.1.22.1.1.6.0",
    "hardware_rev":      "1.3.6.1.4.1.35265.1.22.1.1.8.0",
    "mac":               "1.3.6.1.4.1.35265.1.22.1.1.9.0",
    "cpu_load_1m":       "1.3.6.1.4.1.35265.1.22.1.10.3.0",
    "cpu_load_5m":       "1.3.6.1.4.1.35265.1.22.1.10.4.0",
    "cpu_load_15m":      "1.3.6.1.4.1.35265.1.22.1.10.5.0",
    "ram_free":          "1.3.6.1.4.1.35265.1.22.1.10.2.0",
    "disk_free":         "1.3.6.1.4.1.35265.1.22.1.10.1.0",
    "fan0_rpm":          "1.3.6.1.4.1.35265.1.22.1.10.7.0",
    "fan1_rpm":          "1.3.6.1.4.1.35265.1.22.1.10.9.0",
    "sensor1_temp":      "1.3.6.1.4.1.35265.1.22.1.10.10.0",
    "sensor2_temp":      "1.3.6.1.4.1.35265.1.22.1.10.11.0",
}


async def main():
    print(f"=== SNMP GET {IP} ===")
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    for name, oid in OIDS.items():
        try:
            err_ind, err_stat, _, var_binds = await getCmd(
                engine, auth, transport, ctx,
                ObjectType(ObjectIdentity(oid)),
            )
            if err_ind:
                print(f"  {name:18} = ERROR: {err_ind}")
                continue
            if err_stat and err_stat.prettyPrint() != "noError":
                print(f"  {name:18} = STATUS: {err_stat.prettyPrint()}")
                continue
            for _, v in var_binds:
                print(f"  {name:18} = {v}")
        except Exception as e:
            print(f"  {name:18} = EXC: {type(e).__name__}: {e}")


asyncio.run(main())