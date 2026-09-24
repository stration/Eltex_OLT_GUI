"""Диагностика: полный набор колонок ltp8xONTStateTable для одной ONT."""
import asyncio
from app.services.snmp_ont import _bulk_walk

IP = "10.10.1.105"
COMMUNITY = "public"
BASE = "1.3.6.1.4.1.35265.1.22.3.1.1"

# ELTX890DD7BC → '98.21.16.216' или похожий (последние 3 байта серийника)
FILTER = "98.21.16.216"

# Сопоставление колонок из MIB
COL_NAMES = {
    1: "Slot",
    2: "Serial",
    3: "Channel (gpon_port)",
    4: "ONT ID",
    5: "State",
    6: "EqualizationDelay",
    7: "FEC State",
    8: "EncryptionKey",
    9: "OMCIPortId",
    10: "Distance",
    11: "RSSI",
    12: "EquipmentID",
    13: "TxPower",
    14: "RxPower",
    15: "Temperature",
    16: "VideoRxPower",
    17: "Version",
    18: "HWVersion",
    20: "Reconfigure",
    21: "UpdateFirmware",
    22: "Reset",
    23: "ResetToDefaults",
    24: "RFPortOn",
    25: "LaserVoltage",
    26: "LaserBiasCurrent",
}


async def main():
    rows = await _bulk_walk(IP, COMMUNITY, BASE)
    print(f"Всего: {len(rows)}\n")

    # Группируем по серийнику (для указанной ONT)
    by_col = {}
    for oid, val in rows:
        s = str(oid)
        if FILTER not in s:
            continue
        # Извлекаем номер колонки
        tail = s[len(BASE) + 1:]
        parts = tail.split(".")
        try:
            col = int(parts[0])
        except (ValueError, IndexError):
            continue
        by_col[col] = val

    print(f"Колонки для серийника {FILTER}:")
    for col in sorted(by_col.keys()):
        name = COL_NAMES.get(col, f"col_{col}")
        print(f"  .{col:2d}  {name:25s} = {by_col[col]!r}")

    # Также покажем по одной записи из разных колонок, чтобы понять формат
    print("\n=== Образцы по колонкам (по 3 записи) ===")
    for col in sorted(COL_NAMES.keys()):
        samples = []
        for oid, val in rows:
            s = str(oid)
            tail = s[len(BASE) + 1:]
            parts = tail.split(".")
            try:
                c = int(parts[0])
            except (ValueError, IndexError):
                continue
            if c == col and len(samples) < 3:
                samples.append(val)
        if samples:
            print(f"  .{col:2d}  {COL_NAMES[col]:25s}: {samples}")


asyncio.run(main())