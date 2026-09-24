import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, bulkCmd,
)

IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.3.2.1"


async def main():
    print("=== Один вызов bulkCmd ===")
    result = await bulkCmd(
        SnmpEngine(),
        CommunityData(COMMUNITY, mpModel=1),
        UdpTransportTarget((IP, 161), timeout=3, retries=1),
        ContextData(),
        0, 5,
        ObjectType(ObjectIdentity(BASE)),
        lexicographicMode=False,
    )
    print(f"Тип результата: {type(result)}")
    print(f"Длина: {len(result) if hasattr(result, '__len__') else 'n/a'}")

    err_ind, err_stat, err_idx, var_binds = result
    print(f"\nerr_ind: {err_ind}")
    print(f"err_stat: {err_stat}")
    print(f"err_idx: {err_idx}")
    print(f"var_binds тип: {type(var_binds)}")
    print(f"var_binds длина: {len(var_binds)}")
    print(f"\nПервые 3 элемента var_binds:")
    for i, item in enumerate(var_binds[:3]):
        print(f"  [{i}] type={type(item)}, repr={repr(item)[:200]}")
        # Пробуем распаковать
        try:
            oid, val = item
            print(f"       → oid={oid}, val={val}")
        except Exception as e:
            print(f"       → НЕ распаковывается: {type(e).__name__}: {e}")
            # Может, это уже OID, и val отдельно?
            print(f"       → dir: {[x for x in dir(item) if not x.startswith('_')][:20]}")


asyncio.run(main())