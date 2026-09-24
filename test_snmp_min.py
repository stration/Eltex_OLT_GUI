"""Минимальный тест: один GET через hlapi.asyncio."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, getCmd,
)


async def main():
    ip = "10.10.1.105"
    community = "public"
    oid = "1.3.6.1.4.1.35265.1.22.1.1.7.0"  # uptime

    engine = SnmpEngine()
    auth = CommunityData(community, mpModel=1)
    transport = UdpTransportTarget((ip, 161), timeout=3, retries=1)
    ctx = ContextData()

    err_ind, err_stat, _, var_binds = await getCmd(
        engine, auth, transport, ctx,
        ObjectType(ObjectIdentity(oid)),
    )

    print("err_ind =", err_ind)
    print("err_stat =", err_stat.prettyPrint() if err_stat else None)
    for name, val in var_binds:
        print(f"  {name} = {val}")


asyncio.run(main())