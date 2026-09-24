"""Walk по КОЛОНКАМ ltp8xSwitchVLANTable."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, bulkCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"

# Колонки ltp8xSwitchVLANEntry
COLS = {
    "Slot":               "1.3.6.1.4.1.35265.1.22.9.2.1.1",
    "Vid":                "1.3.6.1.4.1.35265.1.22.9.2.1.2",
    "Name":               "1.3.6.1.4.1.35265.1.22.9.2.1.3",
    "TaggedPorts":        "1.3.6.1.4.1.35265.1.22.9.2.1.4",
    "UntaggedPorts":      "1.3.6.1.4.1.35265.1.22.9.2.1.5",
    "IGMPSnooping":       "1.3.6.1.4.1.35265.1.22.9.2.1.10",
    "MLDSnooping":        "1.3.6.1.4.1.35265.1.22.9.2.1.20",
}


async def walk_col(name, base):
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    current_oid = base
    print(f"\n=== {name} [{base}] ===")
    seen = 0
    for _ in range(10):
        err_ind, err_stat, _, var_binds = await bulkCmd(
            engine, auth, transport, ctx,
            0, 25,
            ObjectType(ObjectIdentity(current_oid)),
            lexicographicMode=False,
        )
        if err_ind:
            print(f"  err_ind: {err_ind}"); return
        if err_stat and err_stat.prettyPrint() != "noError":
            print(f"  err_stat: {err_stat.prettyPrint()}"); return
        if not var_binds:
            break

        stop = False
        last_oid = None
        for item in var_binds:
            oid_str = str(item[0])
            if not oid_str.startswith(base):
                stop = True
                break
            # Извлекаем {slot}.{vid}
            tail = oid_str[len(base) + 1:]
            print(f"  {tail:12} = {item[1]}")
            seen += 1
            last_oid = oid_str
            if seen >= 30:
                print("  ... (обрезано)")
                return

        if stop or last_oid is None:
            break
        current_oid = last_oid
        if len(var_binds) < 25:
            break

    print(f"  (всего {seen})")


async def main():
    for name, base in COLS.items():
        try:
            await walk_col(name, base)
        except Exception as e:
            print(f"\n{name}: EXC {type(e).__name__}: {e}")


asyncio.run(main())