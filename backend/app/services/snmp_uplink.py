"""SNMP-опрос uplink-портов OLT (Eltex LTP-4X/8X).

Источники:
  1. ifTable (IF-MIB) — ifDescr, ifOperStatus, ifSpeed, ifHighSpeed.
  2. ltp8xSwitchPortsUtilizationTable — утилизация.
     OID: 1.3.6.1.4.1.35265.1.22.9.8.2.1
     индекс: <column>.<slot>.<portID>
  3. ltp8xSwitchPortCountersTable — счётчики портов.
     OID: 1.3.6.1.4.1.35265.1.22.9.5.1
     индекс: <column>.<slot>.<portID>
     ВАЖНО: обходится через nextCmd, потому что bulkCmd
     спотыкается о not-accessible поля индекса.

Маппинг ifIndex для LTP-4X (проверено на rev.B / 3.46.0):
  5 → GE1 (switch portID = 1), ..., 10 → 10G SFP+ 1 (portID = 6).
Правило: switch_portID = ifIndex - 4.
"""
from loguru import logger
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget, ContextData,
    ObjectType, ObjectIdentity, getCmd, nextCmd, bulkCmd,
)


OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
OID_IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"

UTIL_BASE_OID = "1.3.6.1.4.1.35265.1.22.9.8.2.1"
COL_UTIL_LAST_KBITS_SENT = 3
COL_UTIL_LAST_KBITS_RECV = 4
COL_UTIL_LAST_FRAMES_SENT = 5
COL_UTIL_LAST_FRAMES_RECV = 6
COL_UTIL_AVG_KBITS_SENT = 7
COL_UTIL_AVG_KBITS_RECV = 8
COL_UTIL_AVG_FRAMES_SENT = 9
COL_UTIL_AVG_FRAMES_RECV = 10

CNT_BASE_OID = "1.3.6.1.4.1.35265.1.22.9.5.1"
CNT_COL_GOOD_OCTETS_RCV = 3
CNT_COL_BAD_OCTETS_RCV = 4
CNT_COL_MAC_TRANSMIT_ERR = 5
CNT_COL_GOOD_PKTS_RCV = 6
CNT_COL_BAD_PKTS_RCV = 7
CNT_COL_BRDC_PKTS_RCV = 8
CNT_COL_MC_PKTS_RCV = 9
CNT_COL_GOOD_OCTETS_SENT = 16
CNT_COL_GOOD_PKTS_SENT = 17
CNT_COL_FC_SENT = 22
CNT_COL_GOOD_FC_RCV = 23
CNT_COL_DROP_EVENTS = 24
CNT_COL_UNDERSIZE_PKTS = 25
CNT_COL_FRAGMENTS_PKTS = 26
CNT_COL_OVERSIZE_PKTS = 27
CNT_COL_JABBER_PKTS = 28
CNT_COL_MAC_RCV_ERROR = 29
CNT_COL_BAD_CRC = 30
CNT_COL_COLLISIONS = 31
CNT_COL_LATE_COLLISIONS = 32
CNT_COL_BAD_FC_RCV = 33

IF_OPER_STATUS_MAP = {
    1: "up", 2: "down", 3: "testing", 4: "unknown",
    5: "dormant", 6: "notPresent", 7: "lowerLayerDown",
}

UPLINK_NAMES_LTP4X = {
    5: "GE1", 6: "GE2", 7: "GE3", 8: "GE4",
    9: "10G SFP+ 0", 10: "10G SFP+ 1",
}
UPLINK_NAMES_LTP8X = {
    5: "GE1", 6: "GE2", 7: "GE3", 8: "GE4",
    9: "GE5", 10: "GE6", 11: "GE7", 12: "GE8",
    13: "10G SFP+ 0", 14: "10G SFP+ 1",
}


def _is_ltp8x(model: str | None) -> bool:
    return "8X" in (model or "").upper()


def _uplink_names(model: str | None) -> dict[int, str]:
    return UPLINK_NAMES_LTP8X if _is_ltp8x(model) else UPLINK_NAMES_LTP4X


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


def _extract(item):
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


async def _walk_next(ip: str, community: str, base_oid: str,
                     limit: int = 5000) -> list[tuple[str, object]]:
    """Walk через nextCmd. Устойчив к not-accessible индексам."""
    results: list[tuple[str, object]] = []
    engine = SnmpEngine()
    auth = CommunityData(community, mpModel=1)
    transport = UdpTransportTarget((ip, 161), timeout=3, retries=1)
    ctx = ContextData()

    current = base_oid
    for _ in range(300):
        err_ind, err_stat, _, var_binds = await nextCmd(
            engine, auth, transport, ctx,
            ObjectType(ObjectIdentity(current)),
            lexicographicMode=False,
        )
        if err_ind:
            logger.warning(f"walk_next {ip} {base_oid}: {err_ind}")
            return results
        if err_stat and err_stat.prettyPrint() != "noError":
            logger.warning(f"walk_next {ip} {base_oid}: {err_stat.prettyPrint()}")
            return results
        if not var_binds:
            break

        stop = False
        last = None
        for item in var_binds:
            oid, val = _extract(item)
            if oid is None:
                continue
            if not oid.startswith(base_oid):
                stop = True
                break
            results.append((oid, val))
            last = oid
            if len(results) >= limit:
                return results
        if stop or last is None:
            break
        current = last

    return results


async def _get_many(ip: str, community: str, oids: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for oid in oids:
        try:
            engine = SnmpEngine()
            auth = CommunityData(community, mpModel=1)
            transport = UdpTransportTarget((ip, 161), timeout=3, retries=1)
            ctx = ContextData()
            err_ind, err_stat, _, var_binds = await getCmd(
                engine, auth, transport, ctx,
                ObjectType(ObjectIdentity(oid)),
            )
            if err_ind or (err_stat and err_stat.prettyPrint() != "noError"):
                continue
            for _, v in var_binds:
                result[oid] = v
                break
        except Exception:
            continue
    return result


async def _walk_utilization(ip: str, community: str) -> dict[int, dict]:
    util_by_port: dict[int, dict] = {}
    raw = await _walk_next(ip, community, UTIL_BASE_OID)
    base_dotted = UTIL_BASE_OID + "."
    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 3:
            continue
        try:
            column = int(parts[0])
            port_id = int(parts[-1])
        except ValueError:
            continue
        u = util_by_port.setdefault(port_id, {})
        v = _to_int(val)
        mapping = {
            COL_UTIL_LAST_KBITS_SENT: "last_kbits_sent",
            COL_UTIL_LAST_KBITS_RECV: "last_kbits_recv",
            COL_UTIL_LAST_FRAMES_SENT: "last_frames_sent",
            COL_UTIL_LAST_FRAMES_RECV: "last_frames_recv",
            COL_UTIL_AVG_KBITS_SENT: "avg_kbits_sent",
            COL_UTIL_AVG_KBITS_RECV: "avg_kbits_recv",
            COL_UTIL_AVG_FRAMES_SENT: "avg_frames_sent",
            COL_UTIL_AVG_FRAMES_RECV: "avg_frames_recv",
        }
        key = mapping.get(column)
        if key is not None:
            u[key] = v
    return util_by_port


async def _walk_counters(ip: str, community: str) -> dict[int, dict]:
    counters_by_port: dict[int, dict] = {}
    try:
        raw = await _walk_next(ip, community, CNT_BASE_OID)
    except Exception as e:
        logger.warning(f"counters walk {ip}: {type(e).__name__}: {e}")
        return counters_by_port

    logger.debug(f"counters walk {ip}: {len(raw)} строк")

    base_dotted = CNT_BASE_OID + "."
    for oid_str, val in raw:
        if not oid_str.startswith(base_dotted):
            continue
        tail = oid_str[len(base_dotted):]
        parts = tail.split(".")
        if len(parts) < 3:
            continue
        try:
            column = int(parts[0])
            port_id = int(parts[-1])
        except ValueError:
            continue
        c = counters_by_port.setdefault(port_id, {})
        v = _to_int(val)
        mapping = {
            CNT_COL_GOOD_OCTETS_RCV: "rx_bytes",
            CNT_COL_BAD_OCTETS_RCV: "rx_bad_bytes",
            CNT_COL_MAC_TRANSMIT_ERR: "tx_mac_errors",
            CNT_COL_GOOD_PKTS_RCV: "rx_pkts",
            CNT_COL_BAD_PKTS_RCV: "rx_errors",
            CNT_COL_BRDC_PKTS_RCV: "rx_broadcast",
            CNT_COL_MC_PKTS_RCV: "rx_multicast",
            CNT_COL_GOOD_OCTETS_SENT: "tx_bytes",
            CNT_COL_GOOD_PKTS_SENT: "tx_pkts",
            CNT_COL_FC_SENT: "tx_flow_control",
            CNT_COL_GOOD_FC_RCV: "rx_flow_control",
            CNT_COL_DROP_EVENTS: "rx_drops",
            CNT_COL_UNDERSIZE_PKTS: "rx_undersize",
            CNT_COL_FRAGMENTS_PKTS: "rx_fragments",
            CNT_COL_OVERSIZE_PKTS: "rx_oversize",
            CNT_COL_JABBER_PKTS: "rx_jabber",
            CNT_COL_MAC_RCV_ERROR: "rx_mac_errors",
            CNT_COL_BAD_CRC: "rx_crc_errors",
            CNT_COL_COLLISIONS: "tx_collisions",
            CNT_COL_LATE_COLLISIONS: "tx_late_collisions",
            CNT_COL_BAD_FC_RCV: "rx_bad_flow_control",
        }
        key = mapping.get(column)
        if key is not None:
            c[key] = v

    logger.debug(
        f"counters {ip}: портов с данными = {len(counters_by_port)}, "
        f"ключи = {sorted(counters_by_port.keys())[:10]}"
    )
    return counters_by_port


async def snmp_get_uplinks(
    ip: str, community: str, model: str | None = None,
) -> list[dict]:
    """Возвращает список uplink-портов (GE, 10G SFP+) с утилизацией и счётчиками."""
    names_map = _uplink_names(model)
    if not names_map:
        return []

    # Шаг 1: ifDescr
    descr_raw = await _walk_next(ip, community, OID_IF_DESCR)
    if_index_descr: dict[int, str] = {}
    for oid_str, val in descr_raw:
        parts = oid_str.split(".")
        if not parts:
            continue
        try:
            idx = int(parts[-1])
        except ValueError:
            continue
        s = _to_str(val)
        if s:
            if_index_descr[idx] = s

    # Шаг 2: утилизация
    util_by_port = await _walk_utilization(ip, community)

    # Шаг 3: счётчики
    counters_by_port = await _walk_counters(ip, community)

    # Шаг 4: ifOperStatus/ifSpeed + склейка
    result: list[dict] = []
    for if_index, name in sorted(names_map.items()):
        actual_descr = if_index_descr.get(if_index)

        oper_oid = f"{OID_IF_OPER_STATUS}.{if_index}"
        speed_oid = f"{OID_IF_SPEED}.{if_index}"
        high_speed_oid = f"{OID_IF_HIGH_SPEED}.{if_index}"

        vals = await _get_many(ip, community, [oper_oid, speed_oid, high_speed_oid])

        oper_num = _to_int(vals.get(oper_oid))
        speed_bps = _to_int(vals.get(speed_oid))
        high_speed_mbps = _to_int(vals.get(high_speed_oid))

        switch_port_id = if_index - 4
        util = util_by_port.get(switch_port_id, {})
        cnt = counters_by_port.get(switch_port_id)

        result.append({
            "if_index": if_index,
            "name": name,
            "if_descr": actual_descr,
            "oper_status": IF_OPER_STATUS_MAP.get(oper_num, "unknown")
                if oper_num is not None else None,
            "oper_status_num": oper_num,
            "speed_bps": speed_bps,
            "speed_mbps": high_speed_mbps,
            "last_kbits_sent": util.get("last_kbits_sent"),
            "last_kbits_recv": util.get("last_kbits_recv"),
            "last_frames_sent": util.get("last_frames_sent"),
            "last_frames_recv": util.get("last_frames_recv"),
            "avg_kbits_sent": util.get("avg_kbits_sent"),
            "avg_kbits_recv": util.get("avg_kbits_recv"),
            "avg_frames_sent": util.get("avg_frames_sent"),
            "avg_frames_recv": util.get("avg_frames_recv"),
            "counters": cnt or None,
        })

    return result