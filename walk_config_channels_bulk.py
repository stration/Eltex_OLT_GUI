"""Walk по всей ConfigTable через bulkCmd, фильтр по column=3 (Channel)."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, bulkCmd,
)

IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.3.4.1"


def _extract(item):
    """Достаём (oid_str, val) — как в snmp_ont.py."""
    obj = item
    depth = 0
    while isinstance(obj, list) and len(obj) == 1 and depth < 5:
        obj = obj[0]
        depth += 1
    if isinstance(obj, (list, tuple)) and len(obj) == 2:
        try:
            name, value = obj
            return str(name), value
        except Exception:
            pass
    try:
        return str(obj[0]), obj[1]
    except Exception:
        return None, None


async def main():
    print(f"=== bulk walk {BASE}, фильтр column=3 ===")
    count = 0
    total = 0
    current_oid = BASE
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    context = ContextData()

    for _ in range(50):
        err_ind, err_stat, err_idx, var_binds = await bulkCmd(
            engine, auth, transport, context,
            0, 25,
            ObjectType(ObjectIdentity(current_oid)),
            lexicographicMode=False,
        )
        if err_ind:
            print("Ошибка:", err_ind); return
        if err_stat and err_stat.prettyPrint() != "noError":
            print("Ошибка:", err_stat.prettyPrint()); return
        if not var_binds:
            break

        stop = False
        last_oid = None
        for item in var_binds:
            oid_str, val = _extract(item)
            if oid_str is None:
                continue
            if not oid_str.startswith(BASE):
                stop = True
                break
            total += 1
            tail = oid_str[len(BASE) + 1:]
            parts = tail.split(".")
            if parts and parts[0] == "3":
                print(f"{oid_str} = {val}")
                count += 1
            last_oid = oid_str

        if stop or last_oid is None:
            break
        current_oid = last_oid
        if len(var_binds) < 25:
            break

    print(f"\nВсего записей: {total}, из них column=3: {count}")


asyncio.run(main())