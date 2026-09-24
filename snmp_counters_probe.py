"""Проверка OID счётчиков портов (ltp8xSwitchPortCountersTable).

Пробуем несколько вариантов base OID, чтобы понять, какой рабочий.
"""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, nextCmd, bulkCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"


def _extract(item):
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


async def walk_next(base: str, limit: int = 40):
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    current = base
    seen = 0
    for _ in range(50):
        err_ind, err_stat, _, var_binds = await nextCmd(
            engine, auth, transport, ctx,
            ObjectType(ObjectIdentity(current)),
            lexicographicMode=False,
        )
        if err_ind:
            print(f"  err_ind: {err_ind}"); return
        if err_stat and err_stat.prettyPrint() != "noError":
            print(f"  err_stat: {err_stat.prettyPrint()}"); return
        if not var_binds:
            break

        stop = False
        last = None
        for item in var_binds:
            oid, val = _extract(item)
            if oid is None:
                continue
            if not oid.startswith(base):
                stop = True
                break
            print(f"  {oid} = {val!r}")
            seen += 1
            last = oid
            if seen >= limit:
                print("  ..."); return

        if stop or last is None:
            break
        current = last


async def main():
    # Вариант 1: base = ...9.5.1.1 (Entry, ожидаемый)
    print("=== ВАРИАНТ 1: base = 1.3.6.1.4.1.35265.1.22.9.5.1.1 ===")
    await walk_next("1.3.6.1.4.1.35265.1.22.9.5.1.1", limit=40)

    # Вариант 2: base = ...9.5.1 (Table, то, что было)
    print("\n=== ВАРИАНТ 2: base = 1.3.6.1.4.1.35265.1.22.9.5.1 ===")
    await walk_next("1.3.6.1.4.1.35265.1.22.9.5.1", limit=40)

    # Вариант 3: base = ...9.5 (Switch)
    print("\n=== ВАРИАНТ 3: base = 1.3.6.1.4.1.35265.1.22.9.5 ===")
    await walk_next("1.3.6.1.4.1.35265.1.22.9.5", limit=60)


asyncio.run(main())