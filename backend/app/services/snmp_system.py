"""SNMP-опрос системной информации OLT (Eltex LTP-4X/8X).

MIB: ELTEX-LTP8X-STANDALONE (1.3.6.1.4.1.35265.1.22.1)

Дерево:
  ltp8xStandalone   = 1.3.6.1.4.1.35265.1.22.1
  ltp8xSystem       = ltp8xStandalone.1
  ltp8xBoardStatus  = ltp8xStandalone.10
  ltp8xPowerSupply  = ltp8xStandalone.17

Скалярные OID:
  uptime       = .1.7.0         сек
  firmware_rev = .1.6.0
  hw_rev       = .1.8.0
  mac          = .1.9.0
  cpu_1m       = .10.3.0        %
  cpu_5m       = .10.4.0
  cpu_15m      = .10.5.0
  ram_free     = .10.2.0        байт
  disk_free    = .10.1.0        КБ
  fan0_rpm     = .10.7.0
  fan1_rpm     = .10.9.0
  sensor1_temp = .10.10.0       °C
  sensor2_temp = .10.11.0

  PSU (таблица):
    .17.1.3.{n}  name
    .17.1.4.{n}  type: 0=DC, 1=AC
    .17.1.5.{n}  intact
"""
from loguru import logger
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, getCmd,
)

SYSTEM_BASE = "1.3.6.1.4.1.35265.1.22.1"

# ltp8xSystem.*
OID_UPTIME = f"{SYSTEM_BASE}.1.7.0"
OID_FIRMWARE_REV = f"{SYSTEM_BASE}.1.6.0"
OID_HW_REV = f"{SYSTEM_BASE}.1.8.0"
OID_MAC = f"{SYSTEM_BASE}.1.9.0"

# ltp8xBoardStatus.*
OID_CPU_1M = f"{SYSTEM_BASE}.10.3.0"
OID_CPU_5M = f"{SYSTEM_BASE}.10.4.0"
OID_CPU_15M = f"{SYSTEM_BASE}.10.5.0"
OID_RAM_FREE = f"{SYSTEM_BASE}.10.2.0"
OID_DISK_FREE = f"{SYSTEM_BASE}.10.1.0"

OID_FAN0_RPM = f"{SYSTEM_BASE}.10.7.0"
OID_FAN1_RPM = f"{SYSTEM_BASE}.10.9.0"
OID_SENSOR1_TEMP = f"{SYSTEM_BASE}.10.10.0"
OID_SENSOR2_TEMP = f"{SYSTEM_BASE}.10.11.0"

# PSU table
OID_PSU_NAME = f"{SYSTEM_BASE}.17.1.3"
OID_PSU_TYPE = f"{SYSTEM_BASE}.17.1.4"
OID_PSU_INTACT = f"{SYSTEM_BASE}.17.1.5"

PSU_TYPE_MAP = {0: "DC", 1: "AC"}


def _to_int(val) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _to_str(val) -> str | None:
    try:
        s = str(val).strip()
    except Exception:
        return None
    return s or None


async def _get_one(ip: str, community: str, oid: str) -> object | None:
    """Один SNMP GET. Возвращает None, если OID не поддерживается."""
    try:
        engine = SnmpEngine()
        auth = CommunityData(community, mpModel=1)
        transport = UdpTransportTarget((ip, 161), timeout=3, retries=1)
        ctx = ContextData()

        err_ind, err_stat, _, var_binds = await getCmd(
            engine, auth, transport, ctx,
            ObjectType(ObjectIdentity(oid)),
        )

        if err_ind:
            logger.debug(f"SNMP get {ip} {oid}: {err_ind}")
            return None
        if err_stat and err_stat.prettyPrint() != "noError":
            logger.debug(f"SNMP get {ip} {oid}: {err_stat.prettyPrint()}")
            return None

        if not var_binds:
            return None

        for _, v in var_binds:
            # NoSuchInstance / NoSuchObject → None
            val_str = str(v)
            if "No Such" in val_str or "NoSuch" in val_str:
                return None
            # Проверка на pyasn1-заглушку
            if hasattr(v, "isSameTypeAs") and not hasattr(v, "__int__"):
                try:
                    int(v)
                except Exception:
                    pass
            return v
    except Exception as e:
        logger.debug(f"SNMP get {ip} {oid}: {type(e).__name__}: {e}")
    return None


async def snmp_get_system(ip: str, community: str) -> dict:
    """Возвращает системную информацию OLT. Все поля — Optional."""
    uptime = await _get_one(ip, community, OID_UPTIME)
    firmware = await _get_one(ip, community, OID_FIRMWARE_REV)
    hw_rev = await _get_one(ip, community, OID_HW_REV)
    mac = await _get_one(ip, community, OID_MAC)

    cpu_1m = await _get_one(ip, community, OID_CPU_1M)
    cpu_5m = await _get_one(ip, community, OID_CPU_5M)
    cpu_15m = await _get_one(ip, community, OID_CPU_15M)
    ram_free = await _get_one(ip, community, OID_RAM_FREE)
    disk_free = await _get_one(ip, community, OID_DISK_FREE)

    fan0 = await _get_one(ip, community, OID_FAN0_RPM)
    fan1 = await _get_one(ip, community, OID_FAN1_RPM)
    t1 = await _get_one(ip, community, OID_SENSOR1_TEMP)
    t2 = await _get_one(ip, community, OID_SENSOR2_TEMP)

    data = {
        "uptime_sec": _to_int(uptime),
        "firmware_rev": _to_str(firmware),
        "hardware_rev": _to_str(hw_rev),
        "mac": _to_str(mac),
        "cpu_load_1m": _to_int(cpu_1m),
        "cpu_load_5m": _to_int(cpu_5m),
        "cpu_load_15m": _to_int(cpu_15m),
        "ram_free_bytes": _to_int(ram_free),
        "disk_free_kb": _to_int(disk_free),
        "fan0_rpm": _to_int(fan0),
        "fan1_rpm": _to_int(fan1),
        "sensor1_temp": _to_int(t1),
        "sensor2_temp": _to_int(t2),
        "psu": [],
    }

    for idx in (1, 2):
        name = await _get_one(ip, community, f"{OID_PSU_NAME}.{idx}")
        type_num = await _get_one(ip, community, f"{OID_PSU_TYPE}.{idx}")
        intact_num = await _get_one(ip, community, f"{OID_PSU_INTACT}.{idx}")

        name_str = _to_str(name)
        type_int = _to_int(type_num)
        intact_int = _to_int(intact_num)

        if name_str is None and type_int is None and intact_int is None:
            continue

        data["psu"].append({
            "index": idx,
            "name": name_str,
            "type": PSU_TYPE_MAP.get(type_int) if type_int is not None else None,
            "intact": intact_int == 1 if intact_int is not None else None,
        })

    return data