"""SNMP-опрос GPON-портов (PON-каналов) OLT.

Таблица — ltp8xPONChannelStateTable (1.3.6.1.4.1.35265.1.22.2.1.1):
  индекс: <column>.<slot>.<channel>  (channel 1-based! порт 0 = index 1)
  колонки:
    3  = state (0=free, 1=inited, 2=cfgInProgress, 3=cfgFailed,
                4=ok, 5=failed, 6=disabled, 7=unknown, 8=redundant)
    4  = ont_count
    6  = SFP vendor
    7  = SFP product number
    8  = SFP revision
    9  = Tx power (dBm * 1000)
    10 = SFP temperature (°C)
    11 = SFP voltage (uV)
    12 = SFP Tx bias current (uA)

ВАЖНО: Eltex в ltp8xPONChannelStateTable использует 1-based индекс канала
(порт 0 = SNMP index 1), а в ltp8xONTConfigChannel — 0-based (порт 0 = 0).
Здесь делаем -1, чтобы получить gpon_port в нотации CLI.
"""
from loguru import logger
from .snmp_ont import _bulk_walk, _to_str_or_none

PON_BASE_OID = "1.3.6.1.4.1.35265.1.22.2.1.1"

CH_STATE = 3
CH_ONT_COUNT = 4
CH_SFP_VENDOR = 6
CH_SFP_PRODUCT = 7
CH_SFP_REVISION = 8
CH_TX_POWER = 9
CH_SFP_TEMPERATURE = 10
CH_SFP_VOLTAGE = 11
CH_SFP_TX_BIAS = 12

PON_STATE_MAP = {
    0: "free",
    1: "inited",
    2: "cfgInProgress",
    3: "cfgFailed",
    4: "ok",
    5: "failed",
    6: "disabled",
    7: "unknown",
    8: "redundant",
}

# Маркеры «нет данных» для SFP-полей
TX_POWER_NO_DATA = 32767
TEMPERATURE_NO_DATA = 32766
TX_BIAS_NO_DATA = 32767
VOLTAGE_NO_DATA_MIN = 100_000
VOLTAGE_NO_DATA_MAX = 6_000_000


def _int_keep_negative(val) -> int | None:
    """int(val), сохраняя отрицательные (нужно для Tx power)."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _sfp_no_data(vendor: str | None, ont_count: int | None) -> bool:
    """SFP не установлен, если нет vendor и нет ONT."""
    if vendor:
        return False
    return ont_count in (None, 0)


async def snmp_get_pon_channels(
    ip: str, community: str, max_port: int = 7,
) -> list[dict]:
    """
    Возвращает список портов 0..max_port.
    Для каждого — state, ont_count, SFP-данные, Tx power, температура.
    Порт без данных в SNMP отдаётся со state='unknown'.
    """
    raw = await _bulk_walk(ip, community, PON_BASE_OID)
    base_dotted = PON_BASE_OID + "."
    by_port: dict[int, dict] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 3:
            continue
        try:
            column = int(parts[0])
            snmp_index = int(parts[-1])
        except ValueError:
            continue
        if column not in (
            CH_STATE, CH_ONT_COUNT, CH_SFP_VENDOR, CH_SFP_PRODUCT,
            CH_SFP_REVISION, CH_TX_POWER, CH_SFP_TEMPERATURE,
            CH_SFP_VOLTAGE, CH_SFP_TX_BIAS,
        ):
            continue

        # SNMP index 1-based → gpon_port 0-based
        channel = snmp_index - 1

        p = by_port.setdefault(channel, {"gpon_port": channel})

        if column == CH_STATE:
            v = _int_keep_negative(val)
            if v is not None:
                p["state_num"] = v
                p["state"] = PON_STATE_MAP.get(v, "unknown")
        elif column == CH_ONT_COUNT:
            p["ont_count"] = _int_keep_negative(val)
        elif column == CH_SFP_VENDOR:
            p["sfp_vendor"] = _to_str_or_none(val)
        elif column == CH_SFP_PRODUCT:
            p["sfp_product_number"] = _to_str_or_none(val)
        elif column == CH_SFP_REVISION:
            p["sfp_revision"] = _to_str_or_none(val)
        elif column == CH_TX_POWER:
            v = _int_keep_negative(val)
            if v is not None and v != TX_POWER_NO_DATA:
                p["tx_power_dbm"] = round(v / 1000.0, 2)
        elif column == CH_SFP_TEMPERATURE:
            v = _int_keep_negative(val)
            if v is not None and v != TEMPERATURE_NO_DATA:
                p["temperature_c"] = v
        elif column == CH_SFP_VOLTAGE:
            v = _int_keep_negative(val)
            if v is not None and VOLTAGE_NO_DATA_MIN <= v <= VOLTAGE_NO_DATA_MAX:
                p["voltage_v"] = round(v / 1_000_000.0, 3)
        elif column == CH_SFP_TX_BIAS:
            v = _int_keep_negative(val)
            if v is not None and v != TX_BIAS_NO_DATA:
                p["tx_bias_ma"] = round(v / 1000.0, 2)

    # Дополняем недостающие порты и чистим мусор
    result = []
    for ch in range(max_port + 1):
        port = by_port.get(ch, {
            "gpon_port": ch,
            "state": "unknown",
            "state_num": None,
            "ont_count": None,
        })

        if _sfp_no_data(port.get("sfp_vendor"), port.get("ont_count")):
            for k in (
                "sfp_vendor", "sfp_product_number", "sfp_revision",
                "tx_power_dbm", "temperature_c", "voltage_v", "tx_bias_ma",
            ):
                port.pop(k, None)

        result.append(port)
    return result