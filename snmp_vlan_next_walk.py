"""Walk по VLAN через nextCmd с ручным циклом (работает для sparse-таблиц)."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, nextCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.9.2.1"


def _extract_oid_val(item):
    """Достаём (oid, value) из var_binds — на случай вложенной структуры."""
    obj = item
    depth = 0
    while isinstance(obj, list) and len(obj) == 1 and depth < 5:
        obj = obj[0]
        depth += 1

    if isinstance(obj, (list, tuple)) and len(obj) == 2:
        try:
            return str(obj[0]), obj[1]
        except Exception:
            pass

    try:
        return str(obj[0]), obj[1]
    except Exception:
        pass

    if isinstance(obj, list) and len(obj) >= 1:
        try:
            inner = obj[0]
            return str(inner[0]), inner[1]
        except Exception:
            pass

    return None, None


async def walk_all():
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    current = BASE
    seen = 0
    print(f"=== nextCmd walk {BASE} ===")

    for _ in range(500):   # защита от бесконечного цикла
        err_ind, err_stat, _, var_binds = await nextCmd(
            engine, auth, transport, ctx,
            ObjectType(ObjectIdentity(current)),
            lexicographicMode=False,
        )
        if err_ind:
            print(f"  err_ind: {err_ind}")
            break
        if err_stat and err_stat.prettyPrint() != "noError":
            print(f"  err_stat: {err_stat.prettyPrint()}")
            break
        if not var_binds:
            break

        got = False
        for item in var_binds:
            oid_str, val = _extract_oid_val(item)
            if oid_str is None:
                continue
            if not oid_str.startswith(BASE):
                print(f"\n  Всего: {seen}")
                return
            print(f"  {oid_str} = {val!r}")
            seen += 1
            current = oid_str
            got = True

        if not got:
            break

    print(f"\n  Всего: {seen}")


asyncio.run(walk_all())