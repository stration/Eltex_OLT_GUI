"""Walk по ltp8xSwitchVLANTable с правильными параметрами."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, bulkCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"

# Обходим всю ветку switch: 9.2.1 = VLAN table
BASES = [
    ("switchPorts (9.1.1)",  "1.3.6.1.4.1.35265.1.22.9.1.1"),
    ("switchVLAN (9.2.1)",   "1.3.6.1.4.1.35265.1.22.9.2.1"),
    ("switchAll (9)",        "1.3.6.1.4.1.35265.1.22.9"),
]


async def walk(ip, community, base, limit=80):
    engine = SnmpEngine()
    auth = CommunityData(community, mpModel=1)
    transport = UdpTransportTarget((ip, 161), timeout=3, retries=1)
    ctx = ContextData()

    current_oid = base
    seen = 0
    for _ in range(20):
        err_ind, err_stat, _, var_binds = await bulkCmd(
            engine, auth, transport, ctx,
            0, 25,
            ObjectType(ObjectIdentity(current_oid)),
            lexicographicMode=False,
        )
        if err_ind:
            print(f"   err_ind: {err_ind}")
            return
        if err_stat and err_stat.prettyPrint() != "noError":
            print(f"   err_stat: {err_stat.prettyPrint()}")
            return
        if not var_binds:
            break

        stop = False
        last_oid = None
        for item in var_binds:
            oid_str = str(item[0])
            if not oid_str.startswith(base):
                stop = True
                break
            print(f"   {oid_str} = {item[1]}")
            seen += 1
            last_oid = oid_str
            if seen >= limit:
                print(f"   ... (обрезано)")
                return

        if stop or last_oid is None:
            break
        current_oid = last_oid
        if len(var_binds) < 25:
            break

    print(f"   (всего {seen})")


async def main():
    for name, base in BASES:
        print(f"\n=== {name} [{base}] ===")
        try:
            await walk(IP, COMMUNITY, base, limit=40)
        except Exception as e:
            print(f"   EXC: {type(e).__name__}: {e}")


asyncio.run(main())