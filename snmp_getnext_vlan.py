"""Walk через nextCmd — иногда надёжнее для sparse-таблиц."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, nextCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.9.2"


async def main():
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    current_oid = BASE
    print(f"=== nextCmd walk {BASE} ===")
    seen = 0
    for _ in range(30):
        err_ind, err_stat, _, var_binds = await nextCmd(
            engine, auth, transport, ctx,
            ObjectType(ObjectIdentity(current_oid)),
            lexicographicMode=False,
        )
        if err_ind:
            print(f"err_ind: {err_ind}")
            return
        if err_stat and err_stat.prettyPrint() != "noError":
            print(f"err_stat: {err_stat.prettyPrint()}")
            return
        if not var_binds:
            break

        stop = False
        last_oid = None
        for item in var_binds:
            oid_str = str(item[0])
            if not oid_str.startswith(BASE):
                stop = True
                break
            print(f"   {oid_str} = {item[1]}")
            seen += 1
            last_oid = oid_str
            if seen >= 60:
                print("   ... (обрезано)")
                return

        if stop or last_oid is None:
            break
        current_oid = last_oid

    print(f"\nВсего: {seen}")


asyncio.run(main())