"""SNMP-опрос таблиц ONT: порты, MAC-и, конфигурация, состояние (state).

Таблица 1 — ltp8xONTUNIPortsStateTable (1.3.6.1.4.1.35265.1.22.3.2.1):
  индекс: <column>.<slot>.<8-байт serial>.<port>
  колонки: 5=LinkUp, 6=Speed, 7=Duplex, 8=PoEEnabled

Таблица 2 — ltp8xONTAddressTable (1.3.6.1.4.1.35265.1.22.3.12.1):
  индекс: <column>.<slot>.<8-байт serial>.<entry_id>
  колонки: 5=CVID, 6=SVID, 7=MAC, 13=GEMPortId, 14=UVID

Таблица 3 — ltp8xONTConfigTable (1.3.6.1.4.1.35265.1.22.3.4.1):
  индекс: <column>.<slot>.<8-байт serial>
  колонки (этап 1): см. CFG_*
  ВАЖНО: колонка 3 = gpon_port, колонка 4 = ont_id. Источник правды
  для gpon_port/ont_id (в StateTable колонка 3 всегда 0).

Таблица 4 — ltp8xONTStateTable (1.3.6.1.4.1.35265.1.22.3.1.1):
  индекс: <column>.<slot>.<8-байт serial>
  колонки (этап C):
    1=Slot, 2=Serial, 3=StateChannel (ВСЕГДА 0, не использовать),
    4=StateONTID (не использовать), 5=State,
    6=EqDelay, 7=FEC, 10=Distance, 11=RSSI, 12=EquipmentID,
    13=TxPower, 14=RxPower, 15=Temperature,
    17=Version, 18=HWVersion, 24=RFPortOn, 25=LaserVoltage, 26=LaserBiasCurrent

ВАЖНО: серийник в OID передаётся как <8>,<ELTX>,<4 байта>.
4 байта — hex-суффикс, остальное ASCII. Полный серийник — 12 символов,
например 'ELTX62151198'. Везде используем _full_serial_from_oid_tail.
"""
from loguru import logger
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, bulkCmd,
)

PORTS_BASE_OID = "1.3.6.1.4.1.35265.1.22.3.2.1"
MAC_BASE_OID = "1.3.6.1.4.1.35265.1.22.3.12.1"
CONFIG_BASE_OID = "1.3.6.1.4.1.35265.1.22.3.4.1"
STATE_BASE_OID = "1.3.6.1.4.1.35265.1.22.3.1.1"
FULL_SERVICES_BASE_OID = "1.3.6.1.4.1.35265.1.22.3.25.1"
CUSTOM_CC_BASE_OID = "1.3.6.1.4.1.35265.1.22.3.14.1"
SELECTIVE_TUNNEL_BASE_OID = "1.3.6.1.4.1.35265.1.22.3.26.1"

# Порты
COL_LINKUP = 5
COL_SPEED = 6
COL_DUPLEX = 7
COL_POE = 8

# MAC-таблица
COL_CVID = 5
COL_SVID = 6
COL_MAC = 7
COL_GEM = 13
COL_UVID = 14

# Config-таблица
CFG_CHANNEL = 3
CFG_ONT_ID = 4
CFG_PASSWORD = 6
CFG_FEC_UP = 7
CFG_DESCRIPTION = 8
CFG_MGMT_PROFILE = 9
CFG_CC_PROFILE_0 = 11
CFG_CC_PROFILE_1 = 12
CFG_CC_PROFILE_2 = 13
CFG_CC_PROFILE_3 = 14
CFG_CC_PROFILE_4 = 15
CFG_CC_PROFILE_5 = 16
CFG_CC_PROFILE_6 = 17
CFG_CC_PROFILE_7 = 18
CFG_SHAPING_PROFILE = 19
CFG_PORTS_PROFILE = 31
CFG_RF_PORT_ENABLED = 32
CFG_VOICE_PROFILE = 34
CFG_ENABLED = 35
CFG_TEMPLATE = 43
CFG_EASY_MODE = 44
CFG_DOWN_BCAST_FILTER = 45

# State-таблица (используем только ST_STATE..ST_HW_VERSION)
ST_SLOT = 1
ST_SERIAL = 2
ST_CHANNEL = 3           # НЕ ИСПОЛЬЗУЕТСЯ (всегда 0)
ST_ONT_ID = 4            # НЕ ИСПОЛЬЗУЕТСЯ (всегда 0)
ST_STATE = 5
ST_EQ_DELAY = 6
ST_FEC = 7
ST_OMCI_PORT = 9
ST_DISTANCE = 10
ST_RSSI = 11
ST_EQUIPMENT_ID = 12
ST_TX_POWER = 13
ST_RX_POWER = 14
ST_TEMPERATURE = 15
ST_VERSION = 17
ST_HW_VERSION = 18
ST_RF_PORT_ON = 24
ST_LASER_VOLTAGE = 25
ST_LASER_BIAS_CURRENT = 26

# FullServices
FS_CC_PROFILE = 4
FS_DBA_PROFILE = 5

# CustomCrossConnect
CUSTOM_ENABLED = 4
CUSTOM_VID = 5
CUSTOM_COS = 6
CUSTOM_SVID = 7

# SelectiveTunnel
ST_UVID = 5

PROFILE_TABLES = {
    "dba":           "1.3.6.1.4.1.35265.1.22.3.40.1",
    "ports":         "1.3.6.1.4.1.35265.1.22.3.41.1",
    "management":    "1.3.6.1.4.1.35265.1.22.3.6.1",
    "shaping":       "1.3.6.1.4.1.35265.1.22.3.18.1",
    "cross-connect": "1.3.6.1.4.1.35265.1.22.3.9.1",
    "voice":         "1.3.6.1.4.1.35265.1.22.3.43.1",
}
PROFILE_NAME_COLUMN = 3

LINK_MAP = {1: "up", 2: "down"}
SPEED_MAP = {0: None, 1: "10M", 2: "100M", 3: "1000M", 4: None}
DUPLEX_MAP = {0: None, 1: "full", 2: "half", 3: None}
RF_PORT_MAP = {0: "disabled", 1: "enabled", 2: "no-change"}

# LTPONTState — из MIB ELTEX-LTP8X
ONT_STATE_MAP = {
    0: "free",
    1: "allocated",
    2: "authInProgress",
    3: "authFailed",
    4: "authOk",
    5: "cfgInProgress",
    6: "cfgFailed",
    7: "OK",
    8: "failed",
    9: "blocked",
    10: "mibreset",
    11: "preconfig",
    12: "fwUpdating",
    13: "unactivated",
    14: "redundant",
    15: "disabled",
    16: "unknown",
}

RSSI_DIVISOR = 10.0

MAX_REPETITIONS = 25
MAX_ITERATIONS = 200

PROFILE_UNSET = 65535


# ----------------------------------------------------------------------
# Утилиты
# ----------------------------------------------------------------------

def _snmp_serial_filter(serial: str) -> str | None:
    s = (serial or "").strip().upper()
    if len(s) != 12 or not s.startswith("ELTX"):
        return None
    try:
        prefix_hex = "".join(f"{ord(c):02X}" for c in s[:4])
        serial_hex = prefix_hex + s[4:]
        parts = ["8"] + [str(int(serial_hex[i:i + 2], 16)) for i in range(0, 16, 2)]
        return ".".join(parts)
    except Exception:
        return None


def _serial_from_oid_tail(parts: list[str]) -> str | None:
    """ОБРЕЗАННЫЙ серийник 'ELTX123456' (10 символов). Устарело."""
    try:
        if len(parts) < 10:
            return None
        if parts[3:7] != ["69", "76", "84", "88"]:
            return None
        hex_bytes = [int(x) for x in parts[7:10]]
        hex_suffix = "".join(f"{b:02X}" for b in hex_bytes)
        return "ELTX" + hex_suffix
    except (ValueError, IndexError):
        return None


def _full_serial_from_oid_tail(parts: list[str]) -> str | None:
    """ПОЛНЫЙ серийник 'ELTX12345678' (12 символов)."""
    try:
        if len(parts) < 11:
            return None
        if parts[3:7] != ["69", "76", "84", "88"]:
            return None
        hex_bytes = [int(x) for x in parts[7:11]]
        hex_suffix = "".join(f"{b:02X}" for b in hex_bytes)
        return "ELTX" + hex_suffix
    except (ValueError, IndexError):
        return None


def _extract_oid_val(item):
    obj = item
    depth = 0
    while isinstance(obj, list) and len(obj) == 1 and depth < 5:
        obj = obj[0]
        depth += 1

    if isinstance(obj, (list, tuple)) and len(obj) == 2:
        try:
            name, value = obj
            return str(name), value
        except Exception:
            pass

    try:
        oid = obj[0]
        val = obj[1]
        return str(oid), val
    except Exception:
        pass

    if isinstance(obj, list) and len(obj) >= 1:
        try:
            inner = obj[0]
            oid = inner[0]
            val = inner[1]
            return str(oid), val
        except Exception:
            pass

    return None, None


def _mac_to_string(val) -> str | None:
    try:
        if hasattr(val, "asOctets"):
            raw = val.asOctets()
        else:
            s = val.prettyPrint()
            if isinstance(s, str) and s.startswith("0x"):
                raw = bytes.fromhex(s[2:])
            else:
                raw = bytes(str(s), "latin-1")
        if len(raw) != 6:
            return None
        return ":".join(f"{b:02X}" for b in raw)
    except Exception as e:
        logger.debug(f"_mac_to_string: {type(e).__name__}: {e}")
        return None


def _to_int_or_none(val) -> int | None:
    try:
        v = int(val)
    except (ValueError, TypeError):
        return None
    if v in (65535, -1, 0xFFFFFFFF):
        return None
    return v


def _to_int_any(val) -> int | None:
    """int(val) без отбрасывания 65535/-1 (для state)."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _to_str_or_none(val) -> str | None:
    try:
        s = str(val)
    except Exception:
        return None
    s = s.strip()
    if s in ("", "0x"):
        return None
    if s.startswith("0x"):
        try:
            return bytes.fromhex(s[2:]).decode("utf-8", errors="replace")
        except Exception:
            return s
    return s or None


def _to_bool_or_none(val) -> bool | None:
    try:
        v = int(val)
    except (ValueError, TypeError):
        return None
    if v == 1:
        return True
    if v == 2:
        return False
    return None


def _custom_enabled_from_val(val) -> str:
    try:
        v = int(val)
        return "enabled" if v == 1 else "disabled"
    except Exception:
        return "disabled"


# ----------------------------------------------------------------------
# Bulk-walk
# ----------------------------------------------------------------------

async def _bulk_walk(
    ip: str, community: str, base_oid: str, timeout: float = 3.0,
) -> list[tuple[str, object]]:
    results: list[tuple[str, object]] = []

    engine = SnmpEngine()
    auth = CommunityData(community, mpModel=1)
    transport = UdpTransportTarget((ip, 161), timeout=timeout, retries=1)
    context = ContextData()

    current_oid = base_oid

    for _ in range(MAX_ITERATIONS):
        try:
            err_ind, err_stat, err_idx, var_binds = await bulkCmd(
                engine, auth, transport, context,
                0, MAX_REPETITIONS,
                ObjectType(ObjectIdentity(current_oid)),
                lexicographicMode=False,
            )
        except Exception as e:
            logger.warning(f"SNMP bulk {ip} {base_oid}: {type(e).__name__}: {e}")
            return results

        if err_ind:
            logger.warning(f"SNMP bulk {ip} {base_oid}: {err_ind}")
            return results
        if err_stat and err_stat.prettyPrint() != "noError":
            logger.warning(f"SNMP bulk {ip} {base_oid}: {err_stat.prettyPrint()}")
            return results

        if not var_binds:
            break

        stop = False
        last_oid = None
        for item in var_binds:
            oid_str, val = _extract_oid_val(item)
            if oid_str is None:
                continue
            if not oid_str.startswith(base_oid):
                stop = True
                break
            results.append((oid_str, val))
            last_oid = oid_str

        if stop or last_oid is None:
            break

        current_oid = last_oid

        if len(var_binds) < MAX_REPETITIONS:
            break

    return results


# ----------------------------------------------------------------------
# Порты ONT
# ----------------------------------------------------------------------

async def snmp_get_ont_ports(ip: str, community: str, serial: str) -> list[dict]:
    filter_str = _snmp_serial_filter(serial)
    if not filter_str:
        return []

    raw = await _bulk_walk(ip, community, PORTS_BASE_OID)
    base_dotted = PORTS_BASE_OID + "."
    ports: dict[int, dict] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 11:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue
        if column not in (COL_LINKUP, COL_SPEED, COL_DUPLEX, COL_POE):
            continue
        if filter_str not in tail:
            continue
        try:
            port = int(parts[-1])
        except ValueError:
            continue

        p = ports.setdefault(port, {"port_id": port})

        if column == COL_LINKUP:
            v = _to_int_or_none(val)
            if v is not None:
                p["link"] = LINK_MAP.get(v)
        elif column == COL_SPEED:
            v = _to_int_or_none(val)
            if v is not None:
                p["speed"] = SPEED_MAP.get(v)
        elif column == COL_DUPLEX:
            v = _to_int_or_none(val)
            if v is not None:
                p["duplex"] = DUPLEX_MAP.get(v)
        elif column == COL_POE:
            v = _to_int_or_none(val)
            if v is not None:
                p["poe_state"] = "enable" if v == 1 else "disable"

    return [
        {
            "port_id": pid,
            "link": ports[pid].get("link"),
            "speed": ports[pid].get("speed"),
            "duplex": ports[pid].get("duplex"),
            "poe_state": ports[pid].get("poe_state"),
        }
        for pid in sorted(ports.keys())
    ]


async def snmp_walk_all_ports(ip: str, community: str) -> dict[str, list[dict]]:
    raw = await _bulk_walk(ip, community, PORTS_BASE_OID)
    base_dotted = PORTS_BASE_OID + "."
    by_serial: dict[str, dict[int, dict]] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 11:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue
        if column not in (COL_LINKUP, COL_SPEED, COL_DUPLEX, COL_POE):
            continue

        serial_human = _full_serial_from_oid_tail(parts)
        if not serial_human:
            continue

        try:
            port = int(parts[-1])
        except ValueError:
            continue

        p = by_serial.setdefault(serial_human, {}).setdefault(port, {"port_id": port})

        if column == COL_LINKUP:
            v = _to_int_or_none(val)
            if v is not None:
                p["link"] = LINK_MAP.get(v)
        elif column == COL_SPEED:
            v = _to_int_or_none(val)
            if v is not None:
                p["speed"] = SPEED_MAP.get(v)
        elif column == COL_DUPLEX:
            v = _to_int_or_none(val)
            if v is not None:
                p["duplex"] = DUPLEX_MAP.get(v)
        elif column == COL_POE:
            v = _to_int_or_none(val)
            if v is not None:
                p["poe_state"] = "enable" if v == 1 else "disable"

    return {
        serial_human: [ports[pid] for pid in sorted(ports.keys())]
        for serial_human, ports in by_serial.items()
    }


# ----------------------------------------------------------------------
# MAC-адреса ONT
# ----------------------------------------------------------------------

async def snmp_get_ont_macs(ip: str, community: str, serial: str) -> list[dict]:
    filter_str = _snmp_serial_filter(serial)
    if not filter_str:
        return []

    raw = await _bulk_walk(ip, community, MAC_BASE_OID)
    base_dotted = MAC_BASE_OID + "."
    entries: dict[int, dict] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 12:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue
        if column not in (COL_CVID, COL_SVID, COL_MAC, COL_GEM, COL_UVID):
            continue
        if filter_str not in tail:
            continue
        try:
            entry_id = int(parts[-1])
        except ValueError:
            continue

        e = entries.setdefault(entry_id, {"entry_id": entry_id})

        if column == COL_MAC:
            mac = _mac_to_string(val)
            if mac:
                e["mac"] = mac
        elif column == COL_CVID:
            e["cvid"] = _to_int_or_none(val)
        elif column == COL_SVID:
            e["svid"] = _to_int_or_none(val)
        elif column == COL_GEM:
            e["gem"] = _to_int_or_none(val)
        elif column == COL_UVID:
            e["uvid"] = _to_int_or_none(val)

    result = []
    for entry_id in sorted(entries.keys()):
        e = entries[entry_id]
        if not e.get("mac"):
            continue
        result.append({
            "mac": e.get("mac"),
            "gem": e.get("gem"),
            "uvid": e.get("uvid"),
            "cvid": e.get("cvid"),
            "svid": e.get("svid"),
        })
    return result


async def snmp_walk_all_macs(ip: str, community: str) -> dict[str, list[dict]]:
    """Один bulk-walk ltp8xONTAddressTable."""
    raw = await _bulk_walk(ip, community, MAC_BASE_OID)
    base_dotted = MAC_BASE_OID + "."
    by_serial_entry: dict[str, dict[int, dict]] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 12:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue
        if column not in (COL_CVID, COL_SVID, COL_MAC, COL_GEM, COL_UVID):
            continue

        serial_human = _full_serial_from_oid_tail(parts)
        if not serial_human:
            continue

        try:
            entry_id = int(parts[-1])
        except ValueError:
            continue

        e = by_serial_entry.setdefault(serial_human, {}).setdefault(
            entry_id, {"entry_id": entry_id},
        )

        if column == COL_MAC:
            mac = _mac_to_string(val)
            if mac:
                e["mac"] = mac
        elif column == COL_CVID:
            e["cvid"] = _to_int_or_none(val)
        elif column == COL_SVID:
            e["svid"] = _to_int_or_none(val)
        elif column == COL_GEM:
            e["gem"] = _to_int_or_none(val)
        elif column == COL_UVID:
            e["uvid"] = _to_int_or_none(val)

    result: dict[str, list[dict]] = {}
    for serial_human, entries in by_serial_entry.items():
        macs = []
        for entry_id in sorted(entries.keys()):
            e = entries[entry_id]
            if not e.get("mac"):
                continue
            macs.append({
                "mac": e["mac"],
                "gem": e.get("gem"),
                "uvid": e.get("uvid"),
                "cvid": e.get("cvid"),
                "svid": e.get("svid"),
            })
        result[serial_human] = macs

    return result


# ----------------------------------------------------------------------
# Общие параметры конфигурации ONT
# ----------------------------------------------------------------------

async def snmp_walk_all_configs(ip: str, community: str) -> dict[str, dict]:
    raw = await _bulk_walk(ip, community, CONFIG_BASE_OID)
    base_dotted = CONFIG_BASE_OID + "."
    by_serial: dict[str, dict] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 10:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue

        serial_human = _full_serial_from_oid_tail(parts)
        if not serial_human:
            continue

        cfg = by_serial.setdefault(serial_human, {})
        cfg[f"col_{column}"] = val

    return by_serial


def config_from_raw(raw: dict) -> dict:
    def _int(col):
        v = raw.get(f"col_{col}")
        return _to_int_or_none(v) if v is not None else None

    def _str(col):
        v = raw.get(f"col_{col}")
        return _to_str_or_none(v) if v is not None else None

    def _bool(col):
        v = raw.get(f"col_{col}")
        return _to_bool_or_none(v) if v is not None else None

    def _profile(col):
        v = _int(col)
        if v is None or v == PROFILE_UNSET:
            return None
        return v

    rf_raw = _int(CFG_RF_PORT_ENABLED)
    rf_state = RF_PORT_MAP.get(rf_raw) if rf_raw is not None else None

    return {
        "gpon_port": _int(CFG_CHANNEL),
        "ont_id": _int(CFG_ONT_ID),
        "password": _str(CFG_PASSWORD),
        "fec_up": _bool(CFG_FEC_UP),
        "description": _str(CFG_DESCRIPTION),
        "enabled": _bool(CFG_ENABLED),
        "easy_mode": _bool(CFG_EASY_MODE),
        "downstream_broadcast_filter": _bool(CFG_DOWN_BCAST_FILTER),
        "rf_port_state": rf_state,
        "profile_management_idx": _profile(CFG_MGMT_PROFILE),
        "profile_shaping_idx": _profile(CFG_SHAPING_PROFILE),
        "profile_ports_idx": _profile(CFG_PORTS_PROFILE),
        "profile_voice_idx": _profile(CFG_VOICE_PROFILE),
        "template_idx": _profile(CFG_TEMPLATE),
        "profile_cc_idx_0": _profile(CFG_CC_PROFILE_0),
        "profile_cc_idx_1": _profile(CFG_CC_PROFILE_1),
        "profile_cc_idx_2": _profile(CFG_CC_PROFILE_2),
        "profile_cc_idx_3": _profile(CFG_CC_PROFILE_3),
        "profile_cc_idx_4": _profile(CFG_CC_PROFILE_4),
        "profile_cc_idx_5": _profile(CFG_CC_PROFILE_5),
        "profile_cc_idx_6": _profile(CFG_CC_PROFILE_6),
        "profile_cc_idx_7": _profile(CFG_CC_PROFILE_7),
    }


# ----------------------------------------------------------------------
# Состояние ONT (State-таблица)
# ----------------------------------------------------------------------

async def snmp_walk_all_states(ip: str, community: str) -> dict[str, dict]:
    """
    Один bulk-walk ltp8xONTStateTable.
    Возвращает {serial: {state, rssi, version, equipment_id, ...}}.
    serial — полный 'ELTX...' (12 символов).
    Поля gpon_port/ont_id из StateTable НЕ возвращаются (там всегда 0).
    Для gpon_port/ont_id используйте snmp_walk_all_configs.
    """
    raw = await _bulk_walk(ip, community, STATE_BASE_OID)
    base_dotted = STATE_BASE_OID + "."
    by_serial: dict[str, dict] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 11:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue

        serial_human = _full_serial_from_oid_tail(parts)
        if not serial_human:
            continue

        cfg = by_serial.setdefault(serial_human, {})
        cfg[f"col_{column}"] = val

    result: dict[str, dict] = {}
    for serial_human, raw_cols in by_serial.items():
        result[serial_human] = state_from_raw(raw_cols)

    return result


def _normalize_status(snmp_state: str | None) -> str:
    """
    Приводит SNMP-состояние к 4 человеческим статусам, которые мы показываем в UI.

    Логика:
      OK         — ONT работает (state = OK или authOk)
      OFFLINE    — ONT в конфиге, но не подключена / не активна
      PENDING    — идёт авторизация / конфигурирование (временное состояние)
      REDUNDANT  — ONT в резервном режиме
      UNKNOWN    — не смогли получить состояние (нет данных)

    ВАЖНО: SNMP-код 16 (unknown) — это OFFLINE, потому что OLT не знает
    состояние, но ONT в конфиге есть. Аналогично free / unactivated / preconfig.
    """
    if snmp_state is None:
        return "UNKNOWN"
    if snmp_state in ("OK", "authOk"):
        return "OK"
    if snmp_state in (
        "unknown", "failed", "authFailed", "cfgFailed",
        "blocked", "disabled", "unactivated", "free", "preconfig",
        "mibreset",
    ):
        return "OFFLINE"
    if snmp_state in ("allocated", "authInProgress", "cfgInProgress", "fwUpdating"):
        return "PENDING"
    if snmp_state == "redundant":
        return "REDUNDANT"
    return "UNKNOWN"


def state_from_raw(raw: dict) -> dict:
    """Нормализованный dict. gpon_port/ont_id здесь НЕТ (они в ConfigTable)."""
    def _int(col):
        v = raw.get(f"col_{col}")
        return _to_int_any(v) if v is not None else None

    def _str(col):
        v = raw.get(f"col_{col}")
        return _to_str_or_none(v) if v is not None else None

    state_num = _int(ST_STATE)
    state_raw = ONT_STATE_MAP.get(state_num, "unknown") if state_num is not None else None
    state_str = _normalize_status(state_raw)

    rssi_raw = _int(ST_RSSI)
    rssi_db: float | None = None
    if rssi_raw is not None and rssi_raw != 65535:
        rssi_db = round(rssi_raw / RSSI_DIVISOR, 2)

    return {
        "state_num": state_num,
        "state": state_str,
        "state_raw": state_raw,
        "distance": _int(ST_DISTANCE),
        "rssi_db": rssi_db,
        "equipment_id": _str(ST_EQUIPMENT_ID),
        "version": _str(ST_VERSION),
        "hw_version": _str(ST_HW_VERSION),
        "rx_power": _int(ST_RX_POWER),
        "tx_power": _int(ST_TX_POWER),
        "temperature": _int(ST_TEMPERATURE),
    }


# ----------------------------------------------------------------------
# Сервисы ONT — FullServices
# ----------------------------------------------------------------------

async def snmp_walk_all_full_services(ip: str, community: str) -> dict[str, dict[int, dict]]:
    raw = await _bulk_walk(ip, community, FULL_SERVICES_BASE_OID)
    base_dotted = FULL_SERVICES_BASE_OID + "."
    by_serial: dict[str, dict[int, dict]] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 11:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue
        if column not in (FS_CC_PROFILE, FS_DBA_PROFILE):
            continue

        serial_human = _full_serial_from_oid_tail(parts)
        if not serial_human:
            continue

        try:
            service_id = int(parts[-1])
        except ValueError:
            continue

        svc = by_serial.setdefault(serial_human, {}).setdefault(service_id, {})

        if column == FS_CC_PROFILE:
            idx = _to_int_or_none(val)
            svc["cc_idx"] = None if (idx is None or idx == PROFILE_UNSET) else idx
        elif column == FS_DBA_PROFILE:
            idx = _to_int_or_none(val)
            svc["dba_idx"] = None if (idx is None or idx == PROFILE_UNSET) else idx

    return by_serial


# ----------------------------------------------------------------------
# Сервисы ONT — CustomCrossConnect
# ----------------------------------------------------------------------

async def snmp_walk_all_custom_cc(ip: str, community: str) -> dict[str, dict[int, dict]]:
    raw = await _bulk_walk(ip, community, CUSTOM_CC_BASE_OID)
    base_dotted = CUSTOM_CC_BASE_OID + "."
    by_serial: dict[str, dict[int, dict]] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 11:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue
        if column not in (CUSTOM_ENABLED, CUSTOM_VID, CUSTOM_COS, CUSTOM_SVID):
            continue

        serial_human = _full_serial_from_oid_tail(parts)
        if not serial_human:
            continue

        try:
            custom_id = int(parts[-1])
        except ValueError:
            continue

        entry = by_serial.setdefault(serial_human, {}).setdefault(custom_id, {})

        if column == CUSTOM_ENABLED:
            entry["enabled"] = _custom_enabled_from_val(val)
        elif column == CUSTOM_VID:
            entry["cvid"] = _to_int_or_none(val)
        elif column == CUSTOM_COS:
            entry["cos"] = _to_int_or_none(val)
        elif column == CUSTOM_SVID:
            entry["svid"] = _to_int_or_none(val)

    return by_serial


# ----------------------------------------------------------------------
# Сервисы ONT — SelectiveTunnel
# ----------------------------------------------------------------------

async def snmp_walk_all_selective_tunnels(ip: str, community: str) -> dict[str, dict[int, list[int]]]:
    raw = await _bulk_walk(ip, community, SELECTIVE_TUNNEL_BASE_OID)
    base_dotted = SELECTIVE_TUNNEL_BASE_OID + "."
    by_serial: dict[str, dict[int, list[int]]] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 12:
            continue
        try:
            column = int(parts[0])
        except ValueError:
            continue
        if column != ST_UVID:
            continue

        serial_human = _full_serial_from_oid_tail(parts)
        if not serial_human:
            continue

        try:
            service_id = int(parts[-2])
        except (ValueError, IndexError):
            continue

        uvid = _to_int_or_none(val)
        if uvid is None:
            continue

        by_serial.setdefault(serial_human, {}).setdefault(service_id, []).append(uvid)

    return by_serial


# ----------------------------------------------------------------------
# Справочники профилей (index → name)
# ----------------------------------------------------------------------

async def snmp_fetch_profile_names(ip: str, community: str) -> dict[str, dict[int, str]]:
    result: dict[str, dict[int, str]] = {}

    for ptype, base_oid in PROFILE_TABLES.items():
        try:
            raw = await _bulk_walk(ip, community, base_oid)
        except Exception as e:
            logger.warning(f"SNMP profiles {ptype}: {type(e).__name__}: {e}")
            result[ptype] = {}
            continue

        names: dict[int, str] = {}
        base_dotted = base_oid + "."
        for oid_str, val in raw:
            if not oid_str.startswith(base_dotted):
                continue
            tail = oid_str[len(base_dotted):]
            parts = tail.split(".")
            if len(parts) < 2:
                continue
            try:
                column = int(parts[0])
                profile_index = int(parts[1])
            except ValueError:
                continue
            if column != PROFILE_NAME_COLUMN:
                continue
            name = _to_str_or_none(val)
            if name:
                names[profile_index] = name

        result[ptype] = names

    return result