"""Проверка маппинга switch_index ↔ ifIndex ↔ uplink для GE/10G."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, getCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"


async def get(oid):
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()
    err_ind, err_stat, _, var_binds = await getCmd(
        engine, auth, transport, ctx, ObjectType(ObjectIdentity(oid)),
    )
    if err_ind or (err_stat and err_stat.prettyPrint() != "noError"):
        return None
    for _, v in var_binds:
        return v
    return None


async def main():
    print("ifIndex → GE/10G (ifDescr):")
    for idx in range(5, 11):
        descr = await get(f"1.3.6.1.2.1.2.2.1.2.{idx}")
        oper = await get(f"1.3.6.1.2.1.2.2.1.8.{idx}")
        speed = await get(f"1.3.6.1.2.1.31.1.1.1.15.{idx}")
        print(f"  ifIndex {idx}: descr={descr!r} oper={oper!r} speedMbps={speed!r}")

    print("\nswitch_portID → LastKbitsSent/Recv (utilization):")
    for pid in range(1, 11):
        sent = await get(f"1.3.6.1.4.1.35265.1.22.9.8.2.1.3.1.{pid}")
        recv = await get(f"1.3.6.1.4.1.35265.1.22.9.8.2.1.4.1.{pid}")
        print(f"  portID {pid}: lastSent={sent!r} lastRecv={recv!r}")


asyncio.run(main())