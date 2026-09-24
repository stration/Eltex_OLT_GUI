"""Проверка SNMP-таблиц конфигурации ONT."""
import asyncio
from app.services.snmp_ont import _bulk_walk

# Базовые OID таблиц конфигурации (из MIB ELTEX-LTP8X)
TABLES = {
    "ONTConfig (общие параметры)":  "1.3.6.1.4.1.35265.1.22.3.4.1",
    "FullServices (профили сервисов)": "1.3.6.1.4.1.35265.1.22.3.25.1",
    "CustomCrossConnect":             "1.3.6.1.4.1.35265.1.22.3.14.1",
    "SelectiveTunnel":                "1.3.6.1.4.1.35265.1.22.3.26.1",
}

IP = "10.10.1.105"
COMMUNITY = "public"


async def main():
    for name, oid in TABLES.items():
        print(f"\n=== {name} ({oid}) ===")
        rows = await _bulk_walk(IP, COMMUNITY, oid)
        print(f"Всего: {len(rows)}")
        for o, v in rows[:10]:
            print(f"  {o} = {v}")


asyncio.run(main())