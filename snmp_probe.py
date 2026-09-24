import asyncio
from pysnmp.hlapi.asyncio import *

async def main():
    base_oid = "1.3.6.1.4.1.35265.1.22.3.2"
    print(f"=== snmpwalk {base_oid} на 10.10.1.105 ===")
    count = 0
    try:
        async for (error_ind, error_status, error_index, var_binds) in walkCmd(
            SnmpEngine(),
            CommunityData("public", mpModel=1),
            UdpTransportTarget(("10.10.1.105", 161), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if error_ind:
                print("Ошибка:", error_ind)
                return
            if error_status:
                print("Ошибка:", error_status.prettyPrint())
                return
            for oid, val in var_binds:
                print(f"{oid} = {val}")
                count += 1
    except Exception as e:
        print(f"Исключение: {type(e).__name__}: {e}")
    print(f"\nВсего: {count}")

asyncio.run(main())