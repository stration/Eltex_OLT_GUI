"""SNMP-опрос VLAN-таблицы OLT (Eltex LTP-4X/8X).

Таблица ltp8xSwitchVLANTable (1.3.6.1.4.1.35265.1.22.9.2.1):
  индекс: {slot}.{vid}  (slot для LTP всегда 1)
  колонки:
    1  = slot                Unsigned32
    2  = vid                 Unsigned32
    3  = name                DisplayString
    4  = taggedPorts         PortList (bitmask)
    5  = untaggedPorts       PortList
    10 = igmpSnoopingEnabled TruthValue (1=on, 2=off)
    11 = igmpQuerierEnabled  TruthValue
    12 = igmpQueryInterval   Unsigned32, сек
    13 = igmpMrouterPorts    PortList
    20 = mldSnoopingEnabled  TruthValue
    21 = mldQuerierEnabled   TruthValue
    22 = mldQueryInterval    Unsigned32
    23 = mldMrouterPorts     PortList
    24 = isolationEnabled    TruthValue
    25 = macDuplicationEnabled TruthValue
    26 = multicastLoopbackEnabled TruthValue

ВАЖНО: таблица sparse — записи с индексами 1, 9, 602 (не подряд).
bulkCmd не работает, используем nextCmd с ручным циклом.
"""
from loguru import logger
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, nextCmd,
)

VLAN_BASE_OID = "1.3.6.1.4.1.35265.1.22.9.2.1"

COL_SLOT = 1
COL_VID = 2
COL_NAME = 3
COL_TAGGED_PORTS = 4
COL_UNTAGGED_PORTS = 5
COL_IGMP_SNOOPING = 10
COL_IGMP_QUERIER = 11
COL_IGMP_QUERY_INTERVAL = 12
COL_IGMP_MROUTER_PORTS = 13
COL_MLD_SNOOPING = 20
COL_MLD_QUERIER = 21
COL_MLD_QUERY_INTERVAL = 22
COL_MLD_MROUTER_PORTS = 23
COL_ISOLATION = 24
COL_MAC_DUPLICATION = 25
COL_MULTICAST_LOOPBACK = 26


# ----------------------------------------------------------------------
# Маппинг индексов switch-таблицы в человеко-читаемые имена портов
# ----------------------------------------------------------------------
# Формат значения: (short_name, full_name)
#   short_name — показываем в UI (GE1, PON0, 10G SFP+ 0, ...)
#   full_name  — в tooltip для сверки с CLI (front-port 0, pon-port 0, ...)
#
# Проверено на LTP-4X rev.B / прошивка 3.46.0.

PORT_NAMES_LTP4X: dict[int, tuple[str, str]] = {
    1:  ("GE1",           "front-port 0"),
    2:  ("GE2",           "front-port 1"),
    3:  ("GE3",           "front-port 2"),
    4:  ("GE4",           "front-port 3"),
    5:  ("10G SFP+ 0",    "10G-front-port 0"),
    6:  ("10G SFP+ 1",    "10G-front-port 1"),
    11: ("PON0",          "pon-port 0"),
    12: ("PON1",          "pon-port 1"),
    13: ("MGMT-PON",      "mgmt-pon-port 0"),
    15: ("PON2",          "pon-port 2"),
    16: ("PON3",          "pon-port 3"),
}

PORT_NAMES_LTP8X: dict[int, tuple[str, str]] = {
    1:  ("GE1",           "front-port 0"),
    2:  ("GE2",           "front-port 1"),
    3:  ("GE3",           "front-port 2"),
    4:  ("GE4",           "front-port 3"),
    5:  ("GE5",           "front-port 4"),
    6:  ("GE6",           "front-port 5"),
    7:  ("GE7",           "front-port 6"),
    8:  ("GE8",           "front-port 7"),
    9:  ("10G SFP+ 0",    "10G-front-port 0"),
    10: ("10G SFP+ 1",    "10G-front-port 1"),
    11: ("PON0",          "pon-port 0"),
    12: ("PON1",          "pon-port 1"),
    13: ("MGMT-PON",      "mgmt-pon-port 0"),
    14: ("PON2",          "pon-port 2"),
    15: ("PON3",          "pon-port 3"),
    16: ("PON4",          "pon-port 4"),
    17: ("PON5",          "pon-port 5"),
    18: ("PON6",          "pon-port 6"),
    19: ("PON7",          "pon-port 7"),
}


def _is_ltp8x(model: str | None) -> bool:
    return "8X" in (model or "").upper()


def port_index_to_info(idx: int, model: str | None) -> tuple[str, str]:
    """Возвращает (short_name, full_name) для индекса switch-таблицы."""
    table = PORT_NAMES_LTP8X if _is_ltp8x(model) else PORT_NAMES_LTP4X
    if idx in table:
        return table[idx]
    # fallback: неизвестный индекс
    return (f"port {idx}", f"switch index {idx}")


def ports_to_infos(ports: list[int], model: str | None) -> list[dict]:
    """Преобразует список индексов в список {index, short, full}."""
    return [
        {
            "index": p,
            "short": port_index_to_info(p, model)[0],
            "full": port_index_to_info(p, model)[1],
        }
        for p in ports
    ]


# ----------------------------------------------------------------------
# Утилиты
# ----------------------------------------------------------------------

def _extract_oid_val(item):
    obj = item
    depth = 0
    while isinstance(obj, list) and len(obj) == 1 and depth < 5:
        obj = obj[0]
        depth += 1

    if isinstance(obj, (list, tuple)) and len(obj) == 2:
        try:
            return str(obj[0]), obj[1]
        except Exception:
            pass

    try:
        return str(obj[0]), obj[1]
    except Exception:
        pass

    if isinstance(obj, list) and len(obj) >= 1:
        try:
            inner = obj[0]
            return str(inner[0]), inner[1]
        except Exception:
            pass

    return None, None


def _to_int(val) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _to_bool(val) -> bool | None:
    """TruthValue: 1=True, 2=False."""
    v = _to_int(val)
    if v == 1:
        return True
    if v == 2:
        return False
    return None


def _to_str(val) -> str | None:
    try:
        s = str(val).strip()
    except Exception:
        return None
    return s or None


def _portlist_to_ports(val) -> list[int]:
    """
    Декодирует PortList из OctetString в список портов.
    Q-BRIDGE-MIB: первый байт = порты 1..8, старший бит = порт 1.
    Возвращает список номеров портов (1-based).
    """
    if val is None:
        return []

    raw: bytes | None = None

    if hasattr(val, "asOctets"):
        try:
            raw = val.asOctets()
        except Exception:
            raw = None

    if raw is None and isinstance(val, (bytes, bytearray)):
        raw = bytes(val)

    if raw is None:
        try:
            s = str(val).strip()
            if s.startswith("0x") or s.startswith("0X"):
                raw = bytes.fromhex(s[2:].replace(" ", "").replace(":", ""))
            else:
                raw = s.encode("latin-1", errors="replace")
        except Exception:
            return []

    if not raw:
        return []

    ports: list[int] = []
    for byte_idx, byte_val in enumerate(raw):
        for bit in range(8):
            if byte_val & (1 << (7 - bit)):
                port_num = byte_idx * 8 + bit + 1
                ports.append(port_num)
    return ports


def _portlist_to_hex(val) -> str | None:
    if val is None:
        return None
    if hasattr(val, "asOctets"):
        try:
            raw = val.asOctets()
            return "0x" + raw.hex()
        except Exception:
            pass
    try:
        s = str(val)
        if s.startswith("0x"):
            return s
        raw = s.encode("latin-1", errors="replace")
        return "0x" + raw.hex()
    except Exception:
        return None


async def _next_walk_sparse(ip: str, community: str, base_oid: str) -> list[tuple[str, object]]:
    """
    Walk по sparse-таблице через nextCmd с ручным циклом.
    Возвращает список (oid_str, value).
    """
    results: list[tuple[str, object]] = []

    engine = SnmpEngine()
    auth = CommunityData(community, mpModel=1)
    transport = UdpTransportTarget((ip, 161), timeout=3, retries=1)
    ctx = ContextData()

    current = base_oid
    for _ in range(2000):
        try:
            err_ind, err_stat, _, var_binds = await nextCmd(
                engine, auth, transport, ctx,
                ObjectType(ObjectIdentity(current)),
                lexicographicMode=False,
            )
        except Exception as e:
            logger.warning(f"SNMP next {ip} {base_oid}: {type(e).__name__}: {e}")
            return results

        if err_ind:
            logger.warning(f"SNMP next {ip} {base_oid}: {err_ind}")
            return results
        if err_stat and err_stat.prettyPrint() != "noError":
            logger.warning(f"SNMP next {ip} {base_oid}: {err_stat.prettyPrint()}")
            return results
        if not var_binds:
            break

        got = False
        for item in var_binds:
            oid_str, val = _extract_oid_val(item)
            if oid_str is None:
                continue
            if not oid_str.startswith(base_oid):
                return results
            results.append((oid_str, val))
            current = oid_str
            got = True

        if not got:
            break

    return results


async def snmp_get_vlans(
    ip: str, community: str, model: str | None = None,
) -> list[dict]:
    """
    Возвращает список VLAN с членством портов и настройками multicast.
    model — модель OLT ('LTP-4X' / 'LTP-8X'), нужна для расшифровки портов.
    """
    raw = await _next_walk_sparse(ip, community, VLAN_BASE_OID)
    if not raw:
        return []

    base_dotted = VLAN_BASE_OID + "."
    by_vid: dict[int, dict] = {}

    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 3:
            continue
        try:
            column = int(parts[0])
            vid = int(parts[-1])
        except ValueError:
            continue

        v = by_vid.setdefault(vid, {"vid": vid})

        if column == COL_SLOT:
            v["slot"] = _to_int(val)
        elif column == COL_VID:
            v["vid"] = _to_int(val)
        elif column == COL_NAME:
            v["name"] = _to_str(val)
        elif column == COL_TAGGED_PORTS:
            nums = _portlist_to_ports(val)
            v["tagged_ports_hex"] = _portlist_to_hex(val)
            v["tagged_ports"] = nums
            v["tagged_ports_info"] = ports_to_infos(nums, model)
        elif column == COL_UNTAGGED_PORTS:
            nums = _portlist_to_ports(val)
            v["untagged_ports_hex"] = _portlist_to_hex(val)
            v["untagged_ports"] = nums
            v["untagged_ports_info"] = ports_to_infos(nums, model)
        elif column == COL_IGMP_SNOOPING:
            v["igmp_snooping"] = _to_bool(val)
        elif column == COL_IGMP_QUERIER:
            v["igmp_querier"] = _to_bool(val)
        elif column == COL_IGMP_QUERY_INTERVAL:
            v["igmp_query_interval"] = _to_int(val)
        elif column == COL_IGMP_MROUTER_PORTS:
            nums = _portlist_to_ports(val)
            v["igmp_mrouter_ports"] = nums
            v["igmp_mrouter_ports_info"] = ports_to_infos(nums, model)
        elif column == COL_MLD_SNOOPING:
            v["mld_snooping"] = _to_bool(val)
        elif column == COL_MLD_QUERIER:
            v["mld_querier"] = _to_bool(val)
        elif column == COL_MLD_QUERY_INTERVAL:
            v["mld_query_interval"] = _to_int(val)
        elif column == COL_MLD_MROUTER_PORTS:
            nums = _portlist_to_ports(val)
            v["mld_mrouter_ports"] = nums
            v["mld_mrouter_ports_info"] = ports_to_infos(nums, model)
        elif column == COL_ISOLATION:
            v["isolation"] = _to_bool(val)
        elif column == COL_MAC_DUPLICATION:
            v["mac_duplication"] = _to_bool(val)
        elif column == COL_MULTICAST_LOOPBACK:
            v["multicast_loopback"] = _to_bool(val)

    return [by_vid[vid] for vid in sorted(by_vid.keys())]