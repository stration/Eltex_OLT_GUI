import asyncio
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Ont
from app.services.snmp_ont import snmp_walk_all_ports


def _snmp_to_human(hex_str: str) -> str:
    """08 45 4C 54 58 62 15 11 → ELTX621511 (10 символов)"""
    # Убираем первый байт (08), берём следующие 7
    if len(hex_str) < 16:
        return hex_str
    tail = hex_str[2:]  # 14 hex-символов
    try:
        return bytes.fromhex(tail).decode("ascii", errors="replace")
    except Exception:
        return tail


async def main():
    # Все ONT из БД
    async with SessionLocal() as session:
        rows = (await session.execute(select(Ont))).scalars().all()

    db_serials = {ont.serial: ont for ont in rows}
    print(f"ONT в БД: {len(db_serials)}")

    # SNMP-walk портов
    ports = await snmp_walk_all_ports("10.10.1.105", "public")
    print(f"ONT в SNMP: {len(ports)}")

    print("\n=== Сопоставление ===")
    matched = 0
    unmatched_snmp = []
    for snmp_hex in sorted(ports.keys()):
        human = _snmp_to_human(snmp_hex)
        # Ищем в БД по первым 10 символам
        found = None
        for db_serial, ont in db_serials.items():
            if db_serial.startswith(human) or human.startswith(db_serial[:10]):
                found = ont
                break
        if found:
            matched += 1
            print(f"  {snmp_hex} → '{human}' → ONT {found.gpon_port}/{found.ont_id} ({found.serial}) ✓")
        else:
            unmatched_snmp.append(snmp_hex)
            print(f"  {snmp_hex} → '{human}' → НЕ НАЙДЕНО ✗")

    print(f"\nСовпало: {matched} из {len(ports)}")
    if unmatched_snmp:
        print(f"Не найдено: {len(unmatched_snmp)}")

    # Обратная проверка: ONT в БД без SNMP
    matched_db = set()
    for snmp_hex in ports.keys():
        human = _snmp_to_human(snmp_hex)
        for db_serial in db_serials:
            if db_serial.startswith(human):
                matched_db.add(db_serial)
    not_in_snmp = set(db_serials.keys()) - matched_db
    if not_in_snmp:
        print(f"\nONT в БД без SNMP-записи: {len(not_in_snmp)}")
        for s in sorted(not_in_snmp):
            print(f"  {s}")


asyncio.run(main())