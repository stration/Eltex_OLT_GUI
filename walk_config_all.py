"""Walk по всей ltp8xONTConfigTable — что вообще есть в таблице."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, walkCmd,
)

IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.3.4.1"


async def main():
    print(f"=== walk {BASE} (первые 50 записей) ===")
    count = 0
    async for (e, s, i, vb) in walkCmd(
        SnmpEngine(),
        CommunityData(COMMUNITY, mpModel=1),
        UdpTransportTarget((IP, 161), timeout=3, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(BASE)),
        lexicographicMode=False,
    ):
        if e:
            print("Ошибка:", e); return
        if s and s.prettyPrint() != "noError":
            print("Ошибка:", s.prettyPrint()); return
        for oid, val in vb:
            print(f"{oid} = {val}")
            count += 1
            if count >= 50:
                print("... (обрезано на 50)")
                return
    print(f"\nВсего показано: {count}")


asyncio.run(main())