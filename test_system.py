"""Прямая проверка snmp_get_system."""
import asyncio
from app.services.snmp_system import snmp_get_system


async def main():
    print("=== Прямой вызов snmp_get_system ===")
    result = await snmp_get_system("10.10.1.105", "public")
    for k, v in result.items():
        print(f"  {k:20} = {v!r}")


asyncio.run(main())