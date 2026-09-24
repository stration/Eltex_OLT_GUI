"""Проверка ltp8xSwitchVLANTable."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, bulkCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.9.2.1"


async def main():
    print(f"=== bulk walk {BASE} ===")
    count = 0
    current_oid = BASE
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    for _ in range(20):
        err_ind, err_stat, _, var_binds = await bulkCmd(
            engine, auth, transport, ctx,
            0, 25,
            ObjectType(ObjectIdentity(current_oid)),
            lexicographicMode=False,
        )
        if err_ind:
            print("err_ind:", err_ind); return
        if err_stat and err_stat.prettyPrint() != "noError":
            print("err_stat:", err_stat.prettyPrint()); return
        if not var_binds:
            break

        stop = False
        last_oid = None
        for item in var_binds:
            oid_str = str(item[0])
            if not oid_str.startswith(BASE):
                stop = True
                break
            print(f"{oid_str} = {item[1]}")
            count += 1
            last_oid = oid_str
            if count >= 100:
                print("... (обрезано на 100)")
                return

        if stop or last_oid is None:
            break
        current_oid = last_oid
        if len(var_binds) < 25:
            break

    print(f"\nВсего: {count}")


asyncio.run(main())