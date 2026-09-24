"""
Диагностика: snmpwalk по колонкам LinkUp и Speed для одной ONT.
Запуск: python snmp_ports_probe.py
"""
import asyncio
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, walkCmd,
)

IP = "10.10.1.105"
COMMUNITY = "public"

# Фильтр по серийному номеру (можно None — тогда выводятся все)
# Формат: строка ASCII-байтов через точку, как в OID.
# ELTX89091F7C  →  69.76.84.88.137.9.31.124
SERIAL_FILTER = "69.76.84.88.137.9.31.124"

OIDS = {
    "LinkUp":  "1.3.6.1.4.1.35265.1.22.3.2.1.5",
    "Speed":   "1.3.6.1.4.1.35265.1.22.3.2.1.6",
    "Duplex":  "1.3.6.1.4.1.35265.1.22.3.2.1.7",
    "Port":    "1.3.6.1.4.1.35265.1.22.3.2.1.3",
}


async def walk_one(name: str, base_oid: str):
    print(f"\n=== {name} ({base_oid}) ===")
    count = 0
    try:
        async for (err_ind, err_stat, err_idx, var_binds) in walkCmd(
            SnmpEngine(),
            CommunityData(COMMUNITY, mpModel=1),
            UdpTransportTarget((IP, 161), timeout=3, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if err_ind:
                print(f"  Ошибка: {err_ind}")
                return
            if err_stat:
                print(f"  Ошибка: {err_stat.prettyPrint()}")
                return
            for oid, val in var_binds:
                oid_str = str(oid)
                if SERIAL_FILTER and SERIAL_FILTER not in oid_str:
                    continue
                # Из OID достаём порт — последнее число
                port = oid_str.rsplit(".", 1)[-1]
                print(f"  port {port}: {val}")
                count += 1
    except Exception as e:
        print(f"  Исключение: {type(e).__name__}: {e}")
    print(f"  Записей: {count}")


async def main():
    print(f"Опрос {IP} (community={COMMUNITY})")
    print(f"Фильтр серийника: {SERIAL_FILTER or '(нет)'}")
    for name, oid in OIDS.items():
        await walk_one(name, oid)


asyncio.run(main())