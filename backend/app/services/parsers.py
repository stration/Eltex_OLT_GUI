"""Парсеры вывода CLI LTP-4X/LTP-8X.

Тестируется на реальном выводе LTP-4X rev.B, ПО 3.46.0.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OntRow:
    gpon_port: int
    ont_id: int
    serial: str
    status: str
    rssi_db: Optional[float]
    version: Optional[str]
    equipment_id: Optional[str]
    description: Optional[str]


_COL_SPLIT = re.compile(r"\s{2,}")
_RE_TOTAL = re.compile(r"^Total ONT count")
_RE_NO_ONT = re.compile(r"^GPON-port \d+ has no ")
_RE_DASHES = re.compile(r"^-+$")
_RE_HEADER_KW = ("Serial", "ONT ID", "GPON-port", "RSSI[dBm]")


def _is_service_line(stripped: str) -> bool:
    if not stripped:
        return True
    if _RE_DASHES.match(stripped):
        return True
    if _RE_TOTAL.match(stripped):
        return True
    if _RE_NO_ONT.match(stripped):
        return True
    kw_count = sum(1 for kw in _RE_HEADER_KW if kw in stripped)
    if kw_count >= 2:
        return True
    return False


# ---- ONT list / state ----------------------------------------------------

def parse_onts_configured(text: str) -> list[OntRow]:
    rows: list[OntRow] = []
    for raw in text.splitlines():
        line = raw.strip()
        if _is_service_line(line):
            continue
        cols = _COL_SPLIT.split(line)
        if len(cols) < 5:
            continue
        if not cols[1].startswith("ELTX"):
            continue
        try:
            ont_id = int(cols[2])
            gpon_port = int(cols[3])
        except ValueError:
            continue

        status = cols[4]
        rssi_raw = cols[5] if len(cols) > 5 else "n/a"
        version = cols[6] if len(cols) > 6 else None
        equipment_id = cols[7] if len(cols) > 7 else None
        description = " ".join(cols[8:]).strip() if len(cols) > 8 else None

        rssi_db: Optional[float] = None
        try:
            if rssi_raw.lower() != "n/a":
                rssi_db = float(rssi_raw)
        except ValueError:
            pass

        def _clean(v: Optional[str]) -> Optional[str]:
            if v is None or v == "" or v.lower() == "n/a":
                return None
            return v

        rows.append(OntRow(
            gpon_port=gpon_port, ont_id=ont_id, serial=cols[1],
            status=status, rssi_db=rssi_db,
            version=_clean(version), equipment_id=_clean(equipment_id),
            description=_clean(description),
        ))
    return rows


def parse_gpon_port_states(text: str) -> dict[int, str]:
    result: dict[int, str] = {}
    current_port: Optional[int] = None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^GPON-port\s+(\d+)", line, re.IGNORECASE)
        if m:
            current_port = int(m.group(1))
            continue
        m = re.match(r"^(?:State|Состояние|State:)\s*:?\s*([A-Z]+)", line, re.IGNORECASE)
        if m and current_port is not None:
            result[current_port] = m.group(1).upper()
    return result


# ---- Профили, шаблоны, unactivated --------------------------------------

def parse_profile_list(text: str) -> list[dict]:
    rows: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("##"):
            continue
        cols = _COL_SPLIT.split(line)
        if len(cols) < 2:
            continue
        try:
            idx = int(cols[0])
        except ValueError:
            continue
        name = cols[1]
        description = cols[2] if len(cols) > 2 else ""
        rows.append({"index": idx, "name": name, "description": description})
    return rows


def parse_onts_unactivated(text: str) -> list[dict]:
    rows: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if _is_service_line(line):
            continue
        cols = _COL_SPLIT.split(line)
        if len(cols) < 4:
            continue
        if not cols[1].startswith("ELTX"):
            continue
        try:
            ont_id_raw = cols[2]
            ont_id = None if ont_id_raw.lower() == "n/a" else int(ont_id_raw)
            gpon_port = int(cols[3])
        except ValueError:
            continue

        status = cols[4] if len(cols) > 4 else "UNACTIVATED"
        rssi_raw = cols[5] if len(cols) > 5 else "n/a"
        version = cols[6] if len(cols) > 6 else None
        equipment_id = cols[7] if len(cols) > 7 else None
        description = " ".join(cols[8:]).strip() if len(cols) > 8 else None

        rssi_db: Optional[float] = None
        try:
            if rssi_raw.lower() != "n/a":
                rssi_db = float(rssi_raw)
        except ValueError:
            pass

        def _clean(v: Optional[str]) -> Optional[str]:
            if v is None or v == "" or v.lower() == "n/a":
                return None
            return v

        rows.append({
            "gpon_port": gpon_port, "ont_id": ont_id, "serial": cols[1],
            "status": status, "rssi_db": rssi_db,
            "version": _clean(version), "equipment_id": _clean(equipment_id),
            "description": _clean(description),
        })
    return rows


# ---- Полная конфигурация ONT --------------------------------------------

_RE_HEADER_ONT_CFG = re.compile(r"^\[ONT(\d+)/(\d+)\]\s+configuration")
_RE_SERVICE_MARK = re.compile(r"^Service\s+\[(\d+)\]:")
_RE_PORT_MARK = re.compile(r"^Port\s+\[(\d+)\]:")
_RE_KV_SIMPLE = re.compile(r"^([^:]+):\s*(.*)$")


@dataclass
class OntServiceConfig:
    service_id: int
    profile_cross_connect: str | None = None
    profile_cross_connect_desc: str | None = None
    profile_dba: str | None = None
    profile_dba_desc: str | None = None
    custom_cross_connect: str = "disabled"
    custom_svid: int | None = None
    custom_cvid: int | None = None
    custom_cos: int | None = None
    selective_tunnel_user_vlans: str | None = None


@dataclass
class OntPortConfig:
    port_id: int
    shutdown: bool = False
    poe_enable: bool = False
    poe_pse_class_control: int = 0
    poe_power_priority: str | None = None


@dataclass
class OntFullConfig:
    description: str | None = None
    enabled: bool = True
    serial: str | None = None
    password: str | None = None
    fec_up: bool = False
    easy_mode: bool = False
    downstream_broadcast: bool = False
    downstream_broadcast_filter: bool = False
    downstream_multicast_filter: bool = False
    ber_interval: str | None = None
    ber_update_period: int = 0
    rf_port_state: str | None = None
    omci_error_tolerant: bool = False

    services: list[OntServiceConfig] = field(default_factory=list)

    profile_shaping: str | None = None
    profile_ports: str | None = None
    profile_management: str | None = None
    profile_voice: str | None = None
    template: str | None = None

    pppoe_sessions_unlimited: bool = False
    collect_utilization_statistics: bool = False

    ports: list[OntPortConfig] = field(default_factory=list)


def _strip_quotes(s: str) -> str | None:
    s = s.strip()
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s or None


def _parse_bool(s: str) -> bool:
    return s.strip().lower() == "true"


def _split_kv_simple(line: str) -> tuple[str, str]:
    m = _RE_KV_SIMPLE.match(line)
    if not m:
        return line.strip(), ""
    return m.group(1).strip(), m.group(2).strip()


def _split_val_desc(v: str) -> tuple[str | None, str | None]:
    parts = _COL_SPLIT.split(v.strip())
    if len(parts) >= 2:
        return parts[0] or None, " ".join(parts[1:]).strip() or None
    return v.strip() or None, None


def _clean_name(v: str | None) -> str | None:
    if v is None or v == "" or v.lower() == "unassigned":
        return None
    return v


def parse_ont_config(text: str) -> OntFullConfig:
    cfg = OntFullConfig()
    current_service: OntServiceConfig | None = None
    current_port: OntPortConfig | None = None
    poe_context = False
    ports_block = False

    for raw in text.splitlines():
        if not raw.strip():
            continue
        if _RE_DASHES.match(raw.strip()):
            continue
        if _RE_HEADER_ONT_CFG.match(raw.strip()):
            continue

        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()

        m = _RE_SERVICE_MARK.match(stripped)
        if m:
            current_service = OntServiceConfig(service_id=int(m.group(1)))
            cfg.services.append(current_service)
            current_port = None
            poe_context = False
            ports_block = False
            continue

        if stripped == "Ports:":
            ports_block = True
            current_port = None
            current_service = None
            poe_context = False
            continue

        m = _RE_PORT_MARK.match(stripped)
        if m and ports_block:
            current_port = OntPortConfig(port_id=int(m.group(1)))
            cfg.ports.append(current_port)
            current_service = None
            poe_context = False
            continue

        if poe_context and current_port is not None and indent >= 16:
            key, val = _split_kv_simple(stripped)
            if key == "Enable":
                current_port.poe_enable = _parse_bool(val)
            elif key == "Pse class control":
                try:
                    current_port.poe_pse_class_control = int(val)
                except ValueError:
                    pass
            elif key == "Power priority":
                current_port.poe_power_priority = val
            continue

        if ports_block and current_port is not None and 12 <= indent < 16:
            if stripped == "PoE:":
                poe_context = True
                continue
            key, val = _split_kv_simple(stripped)
            if key == "shutdown":
                current_port.shutdown = _parse_bool(val)
                continue

        if current_service is not None and indent >= 12:
            key, val = _split_kv_simple(stripped)
            if key == "Custom s-vid":
                try: current_service.custom_svid = int(val)
                except ValueError: pass
                continue
            if key == "Custom c-vid":
                try: current_service.custom_cvid = int(val)
                except ValueError: pass
                continue
            if key == "Custom CoS":
                try: current_service.custom_cos = int(val)
                except ValueError: pass
                continue
            if key == "User vlans":
                current_service.selective_tunnel_user_vlans = _strip_quotes(val)
                continue
            continue

        if current_service is not None and indent >= 8:
            key, val = _split_kv_simple(stripped)
            if key == "Profile cross connect":
                name, desc = _split_val_desc(val)
                current_service.profile_cross_connect = _clean_name(name)
                current_service.profile_cross_connect_desc = desc
                continue
            if key == "Profile dba":
                name, desc = _split_val_desc(val)
                current_service.profile_dba = _clean_name(name)
                current_service.profile_dba_desc = desc
                continue
            if key == "Custom cross connect":
                current_service.custom_cross_connect = val.strip().lower()
                continue
            if stripped == "Selective-tunnel:":
                continue

        current_service = None
        current_port = None
        poe_context = False
        ports_block = False

        key, val = _split_kv_simple(stripped)
        if key == "Description":
            cfg.description = _strip_quotes(val)
        elif key == "Enabled":
            cfg.enabled = _parse_bool(val)
        elif key == "Serial":
            cfg.serial = _clean_name(val)
        elif key == "Password":
            cfg.password = _strip_quotes(val)
        elif key == "Fec up":
            cfg.fec_up = _parse_bool(val)
        elif key == "Easy mode":
            cfg.easy_mode = _parse_bool(val)
        elif key == "Downstream broadcast":
            cfg.downstream_broadcast = _parse_bool(val)
        elif key == "Downstream broadcast filter":
            cfg.downstream_broadcast_filter = _parse_bool(val)
        elif key == "Downstream multicast filter":
            cfg.downstream_multicast_filter = _parse_bool(val)
        elif key == "Ber interval":
            cfg.ber_interval = _clean_name(val)
        elif key == "Ber update period":
            try: cfg.ber_update_period = int(val)
            except ValueError: pass
        elif key == "Rf port state":
            cfg.rf_port_state = val
        elif key == "Omci error tolerant":
            cfg.omci_error_tolerant = _parse_bool(val)
        elif key == "Profile shaping":
            name, _ = _split_val_desc(val)
            cfg.profile_shaping = _clean_name(name)
        elif key == "Profile ports":
            name, _ = _split_val_desc(val)
            cfg.profile_ports = _clean_name(name)
        elif key == "Profile management":
            name, _ = _split_val_desc(val)
            cfg.profile_management = _clean_name(name)
        elif key == "Profile voice":
            name, _ = _split_val_desc(val)
            cfg.profile_voice = _clean_name(name)
        elif key == "Template":
            name, _ = _split_val_desc(val)
            cfg.template = _clean_name(name)
        elif key == "Pppoe sessions unlimited":
            cfg.pppoe_sessions_unlimited = _parse_bool(val)
        elif key == "Collect utilization statistics":
            cfg.collect_utilization_statistics = _parse_bool(val)

    return cfg


# ---- MAC-адреса ONT -----------------------------------------------------

_RE_ONT_MAC_HEADER = re.compile(
    r"^\[ONT(\d+)/(\d+)\]\s+MAC table(?:\s+\((\d+)\s+records?\))?"
)
_RE_MAC = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


@dataclass
class OntMacEntry:
    gpon_port: int
    ont_id: int
    gem: int | None = None
    uvid: int | None = None
    cvid: int | None = None
    svid: int | None = None
    mac: str = ""


def _to_int_or_none(v: str) -> int | None:
    v = v.strip()
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def parse_ont_macs(text: str) -> list[OntMacEntry]:
    entries: list[OntMacEntry] = []
    cur_port: int | None = None
    cur_ont: int | None = None
    header_positions: dict[str, int] | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        m = _RE_ONT_MAC_HEADER.match(line.strip())
        if m:
            cur_port = int(m.group(1))
            cur_ont = int(m.group(2))
            header_positions = None
            continue

        if "ONT not found" in line:
            cur_port = None
            cur_ont = None
            header_positions = None
            continue

        if cur_port is None or cur_ont is None:
            continue

        stripped = line.strip()
        if stripped.startswith("Total"):
            continue

        if "##" in stripped and "GEM" in stripped and "MAC" in stripped:
            header_positions = {
                "gem":  line.find("GEM"),
                "uvid": line.find("UVID"),
                "cvid": line.find("CVID"),
                "svid": line.find("SVID"),
                "mac":  line.find("MAC"),
            }
            continue

        if header_positions is None:
            continue

        mac_match = re.search(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", line)
        if not mac_match:
            continue
        mac_value = mac_match.group(0).upper()
        mac_start = mac_match.start()

        before = line[:mac_start]
        numbers = [(m.group(0), m.start()) for m in re.finditer(r"\d+", before)]
        if not numbers:
            continue
        values = numbers[1:]

        gem: int | None = None
        uvid: int | None = None
        cvid: int | None = None
        svid: int | None = None

        for val_str, val_pos in values:
            best_col = None
            best_dist = 999
            for col in ("gem", "uvid", "cvid", "svid"):
                hpos = header_positions.get(col, -1)
                if hpos < 0:
                    continue
                dist = abs(hpos - val_pos)
                if dist < best_dist:
                    best_dist = dist
                    best_col = col
            try:
                v = int(val_str)
            except ValueError:
                continue
            if best_col == "gem":
                gem = v
            elif best_col == "uvid":
                uvid = v
            elif best_col == "cvid":
                cvid = v
            elif best_col == "svid":
                svid = v

        entries.append(OntMacEntry(
            gpon_port=cur_port,
            ont_id=cur_ont,
            gem=gem, uvid=uvid, cvid=cvid, svid=svid,
            mac=mac_value,
        ))

    return entries


def parse_ont_macs_summary(text: str) -> dict[tuple[int, int], int]:
    result: dict[tuple[int, int], int] = {}
    cur_port: int | None = None
    cur_ont: int | None = None
    cur_count: int = 0
    is_not_found = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        m = _RE_ONT_MAC_HEADER.match(line)
        if m:
            if cur_port is not None and cur_ont is not None and not is_not_found:
                result[(cur_port, cur_ont)] = cur_count
            cur_port = int(m.group(1))
            cur_ont = int(m.group(2))
            cur_count = int(m.group(3)) if m.group(3) else 0
            is_not_found = False
            continue

        if "ONT not found" in line and cur_port is not None:
            is_not_found = True
            continue

    if cur_port is not None and cur_ont is not None and not is_not_found:
        result[(cur_port, cur_ont)] = cur_count

    return result


# ---- Состояние портов ONT -----------------------------------------------

_RE_UNI_MARK = re.compile(r"^UNI\s+##\s+(\d+)")


@dataclass
class OntPortState:
    port_id: int
    link: str | None = None
    speed: str | None = None
    duplex: str | None = None
    poe_state: str | None = None


def parse_ont_ports(text: str) -> list[OntPortState]:
    rows: list[OntPortState] = []
    cur: OntPortState | None = None
    poe_context = False

    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue

        if "ONT is not connected" in stripped:
            return []

        m = _RE_UNI_MARK.match(stripped)
        if m:
            if cur is not None:
                rows.append(cur)
            cur = OntPortState(port_id=int(m.group(1)))
            poe_context = False
            continue

        if cur is None:
            continue

        if stripped == "PoE:":
            poe_context = True
            continue

        key, val = _split_kv_simple(stripped)
        if key == "Link":
            cur.link = (val or "").lower() or None
        elif key == "Speed":
            cur.speed = val or None
        elif key == "Duplex":
            cur.duplex = val or None
        elif key == "State" and poe_context:
            cur.poe_state = val or None

    if cur is not None:
        rows.append(cur)

    return rows


# ---- Детали профилей (show profile <type> <name>) -----------------------

def _flatten_profile(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    context: list[str] = []
    context_indent: list[int] = []

    for raw in text.splitlines():
        if not raw.strip():
            continue
        if raw.lstrip().startswith("LTP-") and "# show" in raw:
            continue

        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()

        if stripped.endswith(":") and ":" not in stripped[:-1]:
            header = stripped[:-1].strip()
            while context_indent and context_indent[-1] >= indent:
                context.pop()
                context_indent.pop()
            context.append(header)
            context_indent.append(indent)
            continue

        if ":" not in stripped:
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        while context_indent and context_indent[-1] >= indent and context:
            context.pop()
            context_indent.pop()

        full_key = ".".join(context + [key])

        if full_key in result:
            n = 2
            while f"{full_key}[{n}]" in result:
                n += 1
            full_key = f"{full_key}[{n}]"

        stripped_val = _strip_quotes(value)
        result[full_key] = stripped_val if stripped_val is not None else value

    return result


def _pick(raw: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        if k in raw:
            return raw[k]
    return None


def _to_int_or_none_str(v: str | None) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _to_bool_str(v: str | None) -> bool | None:
    if v is None:
        return None
    low = v.strip().lower()
    if low == "true":
        return True
    if low == "false":
        return False
    return None


def parse_profile_cross_connect(text: str) -> dict:
    raw = _flatten_profile(text)
    return {
        "name": _pick(raw, "Name"),
        "description": _pick(raw, "Description"),
        "model": _pick(raw, "Model"),
        "bridge_group": _to_int_or_none_str(_pick(raw, "Bridge group")),
        "tag_mode": _pick(raw, "Tag mode"),
        "outer_vid": _to_int_or_none_str(_pick(raw, "Outer vid")),
        "outer_cos": _pick(raw, "Outer cos"),
        "inner_vid": _pick(raw, "Inner vid"),
        "u_vid": _pick(raw, "U vid"),
        "u_cos": _pick(raw, "U cos"),
        "mac_table_entry_limit": _pick(raw, "Mac table entry limit"),
        "type": _pick(raw, "Type"),
        "priority_queue": _to_int_or_none_str(_pick(raw, "Priority queue")),
    }


def parse_profile_dba(text: str) -> dict:
    raw = _flatten_profile(text)
    return {
        "name": _pick(raw, "Name"),
        "description": _pick(raw, "Description"),
        "service_class": _pick(raw, "Dba.Sla data.Service class"),
        "status_reporting": _pick(raw, "Dba.Sla data.Status reporting"),
        "alloc_size": _to_int_or_none_str(_pick(raw, "Dba.Sla data.Alloc size")),
        "alloc_period": _to_int_or_none_str(_pick(raw, "Dba.Sla data.Alloc period")),
        "fixed_bandwidth": _to_int_or_none_str(_pick(raw, "Dba.Sla data.Fixed bandwidth")),
        "guaranteed_bandwidth": _to_int_or_none_str(_pick(raw, "Dba.Sla data.Guaranteed bandwidth")),
        "besteffort_bandwidth": _to_int_or_none_str(_pick(raw, "Dba.Sla data.Besteffort bandwidth")),
        "tcont_allocation_scheme": _pick(raw, "T-CONT allocation scheme"),
    }


def parse_profile_ports(text: str) -> dict:
    raw = _flatten_profile(text)
    result: dict = {
        "name": _pick(raw, "Name"),
        "description": _pick(raw, "Description"),
        "multicast_ip_version": _pick(raw, "Multicast IP version"),
        "igmp_version": _pick(raw, "Igmp settings.Version"),
        "igmp_mode": _pick(raw, "Igmp settings.Mode"),
        "igmp_immediate_leave": _to_bool_str(_pick(raw, "Igmp settings.Immediate leave")),
        "igmp_robustness": _to_int_or_none_str(_pick(raw, "Igmp settings.Robustness")),
        "igmp_query_interval": _to_int_or_none_str(_pick(raw, "Igmp settings.Query interval")),
        "igmp_query_response_interval": _to_int_or_none_str(_pick(raw, "Igmp settings.Query response interval")),
        "mld_version": _pick(raw, "Mld settings.Version"),
        "mld_mode": _pick(raw, "Mld settings.Mode"),
        "ports": [],
    }
    for i in range(4):
        prefix = f"Port [{i}]"
        has = any(k.startswith(prefix + ".") for k in raw)
        if not has:
            continue
        result["ports"].append({
            "port_id": i,
            "speed": _pick(raw, f"{prefix}.Speed"),
            "duplex": _pick(raw, f"{prefix}.Duplex"),
            "bridge_group": _to_int_or_none_str(_pick(raw, f"{prefix}.Bridge group")),
            "multicast_enable": _to_bool_str(_pick(raw, f"{prefix}.Multicast enable")),
        })
    return result


def parse_profile_shaping(text: str) -> dict:
    raw = _flatten_profile(text)
    return {
        "name": _pick(raw, "Name"),
        "description": _pick(raw, "Description"),
        "downstream_one_policer": _to_bool_str(_pick(raw, "Downstream.One policer")),
        "policer0_enable": _to_bool_str(_pick(raw, "Downstream.Policer [0].Enable")),
        "policer0_peak_rate": _to_int_or_none_str(_pick(raw, "Downstream.Policer [0].Peak rate")),
        "storm_broadcast_threshold": _to_int_or_none_str(_pick(raw, "Upstream.Storm control.Broadcast threshold")),
        "storm_broadcast_logging": _to_bool_str(_pick(raw, "Upstream.Storm control.Broadcast logging")),
        "storm_broadcast_shutdown": _to_bool_str(_pick(raw, "Upstream.Storm control.Broadcast shutdown")),
        "storm_multicast_threshold": _to_int_or_none_str(_pick(raw, "Upstream.Storm control.Multicast threshold")),
        "storm_multicast_logging": _to_bool_str(_pick(raw, "Upstream.Storm control.Multicast logging")),
        "storm_multicast_shutdown": _to_bool_str(_pick(raw, "Upstream.Storm control.Multicast shutdown")),
    }


def parse_profile_management(text: str) -> dict:
    raw = _flatten_profile(text)
    return {
        "name": _pick(raw, "Name"),
        "description": _pick(raw, "Description"),
    }


# ---- Активные аварии ----------------------------------------------------

# Пример:
#   Active alarms (1):
#       ##     Type                   Severity     Description
#       0      Ont physical layer     Info         ONT0/21 (ELTX89043CD0) link down
#   No alarms

_RE_ALARM_HEADER = re.compile(r"^Active alarms\s*\((\d+)\)", re.IGNORECASE)
_RE_NO_ALARMS = re.compile(r"^\s*No alarms\s*$", re.IGNORECASE)
_RE_ONT_DESC = re.compile(r"^ONT(\d+)/(\d+)\s+\((\w+)\)\s*(.*)$")


def _column_positions(header: str, cols: list[str]) -> dict[str, int]:
    """Возвращает {col_name: position_in_header}."""
    positions: dict[str, int] = {}
    for c in cols:
        idx = header.find(c)
        if idx >= 0:
            positions[c] = idx
    return positions


def parse_alarm_active(text: str) -> list[dict]:
    """
    Парсит вывод `show alarm active all` (или severity-фильтр).

    Формат:
      Active alarms (N):
          ##     Type                   Severity     Description
          0      Ont physical layer     Info         ONT0/21 (ELTX89043CD0) link down

    Возвращает список:
      [{index, type, severity, severity_raw, description,
        ont_gpon_port, ont_id, ont_serial}, ...]
    """
    rows: list[dict] = []
    header_positions: dict[str, int] | None = None

    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = raw.strip()

        if _RE_NO_ALARMS.match(raw):
            return []

        if _RE_ALARM_HEADER.match(stripped):
            header_positions = None
            continue

        # Шапка таблицы: содержит "##" и "Type" и "Severity" и "Description"
        if "##" in stripped and "Type" in stripped and "Severity" in stripped:
            header_positions = _column_positions(
                raw, ["##", "Type", "Severity", "Description"]
            )
            continue

        if header_positions is None:
            continue

        # Парсим строку данных, используя позиции колонок
        def slice_col(col: str) -> str:
            pos = header_positions.get(col)
            if pos is None:
                return ""
            return raw[pos:].rstrip()

        # Идём от конца к началу — Description самый длинный
        desc_pos = header_positions.get("Description")
        sev_pos = header_positions.get("Severity")
        type_pos = header_positions.get("Type")
        idx_pos = header_positions.get("##")

        if None in (desc_pos, sev_pos, type_pos, idx_pos):
            continue

        # Индекс
        idx_part = raw[idx_pos:type_pos].strip()
        try:
            idx = int(idx_part)
        except ValueError:
            continue

        # Type
        type_part = raw[type_pos:sev_pos].strip()

        # Severity
        sev_part = raw[sev_pos:desc_pos].strip() if desc_pos > sev_pos else ""
        # Description
        desc_part = raw[desc_pos:].strip()

        # Если Description пустой (какой-то формат), fallback — взять всё после sev_pos
        if not desc_part and sev_pos is not None:
            # На случай, если между Severity и Description нет зазора в позициях
            after_sev = raw[sev_pos:].strip()
            # Отрезаем первый токен (severity)
            sp = after_sev.split(None, 1)
            desc_part = sp[1] if len(sp) > 1 else ""

        severity = sev_part.lower() or "info"

        # Пробуем распарсить description как ONT
        ont_gpon_port: int | None = None
        ont_id: int | None = None
        ont_serial: str | None = None

        m = _RE_ONT_DESC.match(desc_part)
        if m:
            ont_gpon_port = int(m.group(1))
            ont_id = int(m.group(2))
            ont_serial = m.group(3)

        rows.append({
            "index": idx,
            "type": type_part,
            "severity": severity,
            "severity_raw": sev_part,
            "description": desc_part,
            "ont_gpon_port": ont_gpon_port,
            "ont_id": ont_id,
            "ont_serial": ont_serial,
        })

    return rows
    
# ---- MAC-таблица коммутатора OLT (show mac) ----------------------------

_RE_MAC_ADDR = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
_RE_MAC_TOTAL = re.compile(r"^(\d+)\s+of\s+(\d+)\s+mac\s+entries", re.IGNORECASE)


def parse_mac_table(text: str) -> dict:
    """
    Парсит вывод `show mac` (в режиме switch).

    Формат:
       Mac table
       ~~~~~~~~~
    VID    MAC address         Interface                                  Type
    ----   -----------------   ----------------------------------------   --------
    9      2a:4f:1c:35:8a:3e   front-port 0                               Dynamic
    ...
    966 of 16384 mac entries is valid

    Возвращает: {"items": [...], "total": N, "limit": M}
      items: [{vid, mac, interface, type}]
    """
    items: list[dict] = []
    total = 0
    limit = 0

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        m = _RE_MAC_TOTAL.match(line)
        if m:
            total = int(m.group(1))
            limit = int(m.group(2))
            continue

        if line.startswith("Mac table") or line.startswith("~"):
            continue
        if line.startswith("VID") or line.startswith("----"):
            continue

        parts = line.split()
        if len(parts) < 4:
            continue

        # VID
        try:
            vid = int(parts[0])
        except ValueError:
            continue

        # MAC
        mac = parts[1]
        if not _RE_MAC_ADDR.match(mac):
            continue

        # Type — последний токен
        type_raw = parts[-1]
        if type_raw.lower() not in ("dynamic", "static"):
            continue

        # Interface — всё между MAC и Type (может содержать пробелы)
        iface = " ".join(parts[2:-1])

        items.append({
            "vid": vid,
            "mac": mac.lower(),
            "interface": iface,
            "type": type_raw.lower(),
        })

    return {"items": items, "total": total, "limit": limit}
    