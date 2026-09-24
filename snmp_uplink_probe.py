"""Проверка OID для uplink-портов (GE, 10G SFP+).

Проверяем:
1. ifTable — состояние интерфейсов (link/up, speed, duplex).
2. ltp8xSwitchPortCountersTable — счётчики.
3. ltp8xSwitchPortsUtilizationTable — утилизация.
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


async def walk_next(base, limit=80):
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
    # 1. ifDescr — имена всех интерфейсов
    print("=== ifDescr (первые 30) ===")
    await walk_next("1.3.6.1.2.1.2.2.1.2", limit=30)

    # 2. ifOperStatus (1=up, 2=down, ...)
    print("\n=== ifOperStatus (первые 30) ===")
    await walk_next("1.3.6.1.2.1.2.2.1.8", limit=30)

    # 3. ifSpeed (bps)
    print("\n=== ifSpeed (первые 30) ===")
    await walk_next("1.3.6.1.2.1.2.2.1.5", limit=30)

    # 4. ifHighSpeed (Mbps)
    print("\n=== ifHighSpeed (первые 30) ===")
    await walk_next("1.3.6.1.2.1.31.1.1.1.15", limit=30)

    # 5. ltp8xSwitchPortsTable — имена портов
    print("\n=== ltp8xSwitchPortsTable (Name) ===")
    await walk_next("1.3.6.1.4.1.35265.1.22.9.1.1.1.2", limit=30)

    # 6. ltp8xSwitchPortsUtilization — утилизация
    print("\n=== ltp8xSwitchPortsUtilizationTable ===")
    await walk_next("1.3.6.1.4.1.35265.1.22.9.8.2.1", limit=80)

    # 7. ltp8xSwitchPortCounters — счётчики
    print("\n=== ltp8xSwitchPortCountersTable (первые 50) ===")
    await walk_next("1.3.6.1.4.1.35265.1.22.9.5.1", limit=50)


asyncio.run(main())