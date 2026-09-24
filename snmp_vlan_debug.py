"""Отладка VLAN-таблицы. Пробуем разные способы обхода."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, getCmd, nextCmd, bulkCmd,
)


IP = "10.10.1.105"
COMMUNITY = "public"

# Первая известная запись (по данным MIB-браузера)
OID_VID_1   = "1.3.6.1.4.1.35265.1.22.9.2.1.2.1.1"   # Vid, slot=1, vid=1
OID_NAME_1  = "1.3.6.1.4.1.35265.1.22.9.2.1.3.1.1"
OID_TAG_1   = "1.3.6.1.4.1.35265.1.22.9.2.1.4.1.1"


async def try_get(oid):
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    err_ind, err_stat, _, var_binds = await getCmd(
        engine, auth, transport, ctx,
        ObjectType(ObjectIdentity(oid)),
    )
    print(f"\n=== GET {oid} ===")
    print(f"  err_ind: {err_ind}")
    print(f"  err_stat: {err_stat.prettyPrint() if err_stat else None}")
    for name, v in var_binds:
        print(f"  {name} = {v!r}")


async def try_getnext(oid):
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    err_ind, err_stat, _, var_binds = await nextCmd(
        engine, auth, transport, ctx,
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    )
    print(f"\n=== GETNEXT {oid} ===")
    print(f"  err_ind: {err_ind}")
    print(f"  err_stat: {err_stat.prettyPrint() if err_stat else None}")
    for name, v in var_binds:
        print(f"  {name} = {v!r}")


async def try_getnext_from_base(oid):
    """Getnext от базового OID, но с ручным перебором."""
    engine = SnmpEngine()
    auth = CommunityData(COMMUNITY, mpModel=1)
    transport = UdpTransportTarget((IP, 161), timeout=3, retries=1)
    ctx = ContextData()

    current = oid
    print(f"\n=== GETNEXT walk from {oid} (ручной) ===")
    for _ in range(5):
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
        for name, v in var_binds:
            name_s = str(name)
            print(f"  {name_s} = {v!r}")
            current = name_s
            break
        else:
            break


async def main():
    # 1. GET конкретной записи
    await try_get(OID_VID_1)
    await try_get(OID_NAME_1)
    await try_get(OID_TAG_1)

    # 2. GETNEXT с конкретного OID
    await try_getnext(OID_VID_1)

    # 3. GETNEXT walk от колонки Vid
    await try_getnext_from_base("1.3.6.1.4.1.35265.1.22.9.2.1.2")


asyncio.run(main())