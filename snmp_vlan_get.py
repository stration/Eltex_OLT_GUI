"""Проверка конкретных OID VLAN."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, getCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"

# Проверим несколько OID из разных ветвей
OIDS = [
    # ltp8x.9.2.1 (ltp8xSwitchVLANTable) — 8x
    "1.3.6.1.4.1.35265.1.22.9.2.1.1.2.1",  # VID первой VLAN
    "1.3.6.1.4.1.35265.1.22.9.2.1.1.3.1",  # Name
    # ltp4x.9.2.1 — 4x
    "1.3.6.1.4.1.35265.1.70.9.2.1.1.2.1",
    "1.3.6.1.4.1.35265.1.70.9.2.1.1.3.1",
    # ltp8xSwitch без VLAN — просто список портов
    "1.3.6.1.4.1.35265.1.22.9.1.1.1.1",   # ltp8xSwitchPortsID.1
    "1.3.6.1.4.1.35265.1.22.9.1.1.1.2",   # ltp8xSwitchPortsName.1
    # ifTable — state портов
    "1.3.6.1.2.1.2.2.1.2.1",              # ifDescr.1
    "1.3.6.1.2.1.2.2.1.3.1",              # ifType.1
]


async def main():
    for oid in OIDS:
        engine = SnmpEngine()
        auth = CommunityData(COMMUNITY, mpModel=1)
        transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
        ctx = ContextData()

        err_ind, err_stat, _, var_binds = await getCmd(
            engine, auth, transport, ctx,
            ObjectType(ObjectIdentity(oid)),
        )
        if err_ind:
            print(f"{oid}  ERROR: {err_ind}")
            continue
        if err_stat and err_stat.prettyPrint() != "noError":
            print(f"{oid}  STATUS: {err_stat.prettyPrint()}")
            continue
        for _, v in var_binds:
            print(f"{oid}  = {v}")


asyncio.run(main())