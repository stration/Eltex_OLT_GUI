"""Walk по колонке 3 (ltp8xONTConfigChannel)."""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, walkCmd,
)

IP = "10.10.1.105"
COMMUNITY = "public"
OID = "1.3.6.1.4.1.35265.1.22.3.4.1.1.3"  # ltp8xONTConfigChannel


async def main():
    print(f"=== walk {OID} ===")
    count = 0
    async for (e, s, i, vb) in walkCmd(
        SnmpEngine(),
        CommunityData(COMMUNITY, mpModel=1),
        UdpTransportTarget((IP, 161), timeout=3, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(OID)),
        lexicographicMode=False,
    ):
        if e:
            print("Ошибка:", e); return
        if s and s.prettyPrint() != "noError":
            print("Ошибка:", s.prettyPrint()); return
        for oid, val in vb:
            print(f"{oid} = {val}")
            count += 1
    print(f"\nВсего: {count}")


asyncio.run(main())