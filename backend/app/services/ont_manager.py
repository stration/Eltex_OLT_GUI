"""Добавление ONT, управление автопоиском, чтение портов и MAC, конфигурация."""
import json as _json
import re
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Olt, Ont, Settings as SettingsModel,
    OntMacCache, OntPortCache, OntConfigCache,
)
from ..security import decrypt
from .cli_service import run_script, CliError
from .parsers import (
    parse_onts_unactivated,
    parse_profile_list,
    parse_profile_cross_connect,
    parse_profile_dba,
    parse_profile_ports,
    parse_profile_shaping,
    parse_profile_management,
    parse_ont_config,
    OntFullConfig,
    OntServiceConfig,
    parse_ont_macs,
    parse_ont_macs_summary,
    parse_ont_ports,
)
from .profiles_cache import get_or_fetch
from .snmp_ont import (
    snmp_get_ont_ports,
    snmp_walk_all_configs,
    snmp_walk_all_full_services,
    snmp_walk_all_custom_cc,
    snmp_walk_all_selective_tunnels,
    snmp_fetch_profile_names,
    config_from_raw,
)


PROFILE_TYPES = ("cross-connect", "dba", "ports", "management", "shaping", "voice")

PROFILE_PARSERS = {
    "cross-connect": parse_profile_cross_connect,
    "dba": parse_profile_dba,
    "ports": parse_profile_ports,
    "shaping": parse_profile_shaping,
    "management": parse_profile_management,
    "voice": lambda _text: {"name": None, "description": None},
}

_SERIAL_PATTERNS = [
    re.compile(r"^[A-Z]{4}[0-9A-F]{8}$"),
    re.compile(r"^[0-9A-F]{16}$"),
    re.compile(r"^([0-9A-F]{2}-){7}[0-9A-F]{2}$"),
]


def validate_serial(serial: str) -> bool:
    return any(p.match(serial) for p in _SERIAL_PATTERNS)


async def _load_olt_cfg(session: AsyncSession, olt_id: int) -> tuple[Olt, SettingsModel]:
    olt = await session.get(Olt, olt_id)
    if olt is None:
        raise CliError(f"OLT {olt_id} не найден")
    cfg = await session.get(SettingsModel, 1)
    if cfg is None or not cfg.cli_user or not cfg.cli_password_enc:
        raise CliError("Не заданы учётки CLI")
    return olt, cfg


async def _run_cli(session: AsyncSession, olt_id: int, commands: list[str]) -> str:
    olt, cfg = await _load_olt_cfg(session, olt_id)
    password = decrypt(cfg.cli_password_enc) or ""
    return await run_script(
        cfg.default_transport, olt.ip, cfg.cli_user, password, commands, timeout=45.0,
    )


def _max_port(olt: Olt) -> int:
    return 7 if (olt.model or "").endswith("8X") else 3


# ---- Autofind ------------------------------------------------------------

async def set_autofind(
    session: AsyncSession, olt_id: int, enable: bool, ports: list[int] | None = None
) -> dict:
    olt = await session.get(Olt, olt_id)
    if olt is None:
        return {"ok": False, "output": "", "error": "OLT не найден"}

    if ports is None:
        ports = list(range(_max_port(olt) + 1))

    cmds: list[str] = []
    for p in ports:
        if enable:
            cmds.append(f"ont autofind interface gpon-port {p}")
        else:
            cmds.append(f"no ont autofind interface gpon-port {p}")
    cmds += ["commit", "save"]

    try:
        output = await _run_cli(session, olt_id, cmds)
    except CliError as e:
        return {"ok": False, "output": "", "error": str(e)}
    except Exception as e:
        logger.exception(f"autofind {olt_id}")
        return {"ok": False, "output": "", "error": f"{type(e).__name__}: {e}"}

    low = output.lower()
    for marker in ("% invalid", "% incomplete", "% ambiguous", "% error"):
        if marker in low:
            idx = low.find(marker)
            return {"ok": False, "output": output,
                    "error": output[max(0, idx - 40): idx + 160].strip()}
    return {"ok": True, "output": output, "error": None}


# ---- Unactivated list ----------------------------------------------------

async def list_unactivated(session: AsyncSession, olt_id: int) -> list[dict]:
    olt = await session.get(Olt, olt_id)
    if olt is None:
        return []
    max_port = _max_port(olt)
    try:
        output = await _run_cli(
            session, olt_id, [f"show interface ont 0-{max_port} unactivated"]
        )
    except CliError as e:
        logger.warning(f"unactivated {olt_id}: {e}")
        return []
    return parse_onts_unactivated(output)


# ---- Add ONT -------------------------------------------------------------

def _escape_cli_value(v: str) -> str:
    """Экранирует кавычки внутри строкового значения для CLI."""
    return v.replace('"', '\\"')


def _commands_for_add(
    gpon_port: int, ont_id: int, serial: str,
    description: str | None,
    template: str | None,
    profile_cross_connect: str | None,
    profile_dba: str | None,
    profile_ports: str | None,
    profile_management: str | None,
) -> list[str]:
    """
    Формирует CLI-скрипт создания ONT.

    Порядок команд как в CLI:
      interface ont X/Y
        serial "..."
        description "..."          (если задано)
        service 0 profile cross-connect "..."   (если задан)
        service 0 profile dba "..."             (если задан)
        profile ports "..."         (если задан)
        profile management "..."    (если задан)
        template "..."              (если задан — и только он, без service/profile)
      exit
    """
    ref = f"{gpon_port}/{ont_id}"
    cmds = [
        "configure terminal",
        f"interface ont {ref}",
        f'serial "{serial}"',
    ]

    if description:
        cmds.append(f'description "{_escape_cli_value(description)}"')

    if template:
        # Шаблон применяется один — без service и остальных profile
        cmds.append(f'template "{template}"')
    else:
        if profile_cross_connect:
            cmds.append(
                f'service 0 profile cross-connect "{profile_cross_connect}"'
            )
        if profile_dba:
            cmds.append(
                f'service 0 profile dba "{profile_dba}"'
            )
        if profile_ports:
            cmds.append(f'profile ports "{profile_ports}"')
        if profile_management:
            cmds.append(f'profile management "{profile_management}"')

    cmds += ["do commit", "do save", "exit", "exit"]
    return cmds


async def add_ont(
    session: AsyncSession, olt_id: int,
    gpon_port: int, ont_id: int, serial: str,
    description: str | None = None,
    template: str | None = None,
    profile_cross_connect: str | None = None,
    profile_dba: str | None = None,
    profile_ports: str | None = None,
    profile_management: str | None = None,
) -> dict:
    if not validate_serial(serial):
        return {"ok": False, "output": "", "error": "Неверный формат серийного номера"}
    if not (0 <= gpon_port <= 7):
        return {"ok": False, "output": "", "error": "Неверный GPON-порт"}
    if not (0 <= ont_id <= 127):
        return {"ok": False, "output": "", "error": "Неверный ONT ID"}

    # Если задан шаблон — service и profile_* игнорируются
    if template:
        profile_cross_connect = None
        profile_dba = None
        profile_ports = None
        profile_management = None

    cmds = _commands_for_add(
        gpon_port, ont_id, serial,
        description,
        template,
        profile_cross_connect, profile_dba,
        profile_ports, profile_management,
    )
    logger.info(f"add ONT {olt_id} {gpon_port}/{ont_id} {serial}: {cmds}")
    try:
        output = await _run_cli(session, olt_id, cmds)
    except CliError as e:
        return {"ok": False, "output": "", "error": str(e)}
    except Exception as e:
        logger.exception(f"add_ont {olt_id}")
        return {"ok": False, "output": "", "error": f"{type(e).__name__}: {e}"}

    low = output.lower()
    for marker in ("% invalid", "% incomplete", "% ambiguous", "% error"):
        if marker in low:
            idx = low.find(marker)
            return {"ok": False, "output": output,
                    "error": output[max(0, idx - 40): idx + 160].strip()}
    return {"ok": True, "output": output, "error": None}


# ---- Next free ONT ID ----------------------------------------------------

async def next_free_id(session: AsyncSession, olt_id: int, gpon_port: int) -> int:
    used = set(
        (await session.execute(
            select(Ont.ont_id).where(Ont.olt_id == olt_id, Ont.gpon_port == gpon_port)
        )).scalars().all()
    )
    for i in range(1, 128):
        if i not in used:
            return i
    return 0


# ---- Profile / template lists (CLI, с кэшем) -----------------------------

async def fetch_profiles(session: AsyncSession, olt_id: int, ptype: str) -> list[dict]:
    if ptype not in PROFILE_TYPES:
        raise CliError(f"Недопустимый тип профиля: {ptype}")

    async def _load() -> list[dict]:
        output = await _run_cli(session, olt_id, [f"show profile {ptype}"])
        return parse_profile_list(output)

    return await get_or_fetch(olt_id, f"profile:{ptype}", _load)


async def fetch_profile_details(
    session: AsyncSession, olt_id: int, ptype: str, name: str,
) -> dict:
    if ptype not in PROFILE_TYPES:
        raise CliError(f"Недопустимый тип профиля: {ptype}")

    parser = PROFILE_PARSERS.get(ptype)
    if parser is None:
        raise CliError(f"Нет парсера для типа {ptype}")

    async def _load() -> dict:
        output = await _run_cli(
            session, olt_id, [f"show profile {ptype} {name}"],
        )
        return parser(output)

    return await get_or_fetch(
        olt_id, f"profile-detail:{ptype}:{name}", _load,
    )


async def fetch_templates(session: AsyncSession, olt_id: int) -> list[dict]:
    async def _load() -> list[dict]:
        output = await _run_cli(session, olt_id, ["show template"])
        return parse_profile_list(output)

    return await get_or_fetch(olt_id, "templates", _load)


# ---- Поиск ONT ----------------------------------------------------------

async def _get_ont(
    session: AsyncSession, olt_id: int, gpon_port: int, ont_id: int,
) -> Ont | None:
    return (await session.execute(
        select(Ont).where(
            Ont.olt_id == olt_id,
            Ont.gpon_port == gpon_port,
            Ont.ont_id == ont_id,
        )
    )).scalar_one_or_none()


async def _all_ont_serials(session: AsyncSession, olt_id: int) -> list[str]:
    rows = (await session.execute(
        select(Ont.serial).where(Ont.olt_id == olt_id)
    )).scalars().all()
    return [s for s in rows if s]


# ---- Конфигурация ONT: кэш БД → SNMP → CLI ------------------------------

def _config_from_cache(
    data: dict, ont: Ont, gpon_port: int, ont_id: int,
) -> OntFullConfig:
    services_data = data.get("services") or []
    services: list[OntServiceConfig] = []

    for svc in services_data:
        services.append(OntServiceConfig(
            service_id=int(svc.get("service_id", 0)),
            profile_cross_connect=svc.get("profile_cross_connect"),
            profile_cross_connect_desc=None,
            profile_dba=svc.get("profile_dba"),
            profile_dba_desc=None,
            custom_cross_connect=svc.get("custom_cross_connect") or "disabled",
            custom_svid=svc.get("custom_svid"),
            custom_cvid=svc.get("custom_cvid"),
            custom_cos=svc.get("custom_cos"),
            selective_tunnel_user_vlans=svc.get("selective_tunnel_uvid"),
        ))

    if not services:
        services = [OntServiceConfig(
            service_id=0,
            profile_cross_connect=data.get("profile_cross_connect_name"),
            profile_dba=None,
            custom_cross_connect="disabled",
        )]

    return OntFullConfig(
        description=data.get("description"),
        enabled=bool(data.get("enabled", True)),
        serial=ont.serial,
        password=data.get("password"),
        fec_up=bool(data.get("fec_up", False)),
        easy_mode=bool(data.get("easy_mode", False)),
        downstream_broadcast=True,
        downstream_broadcast_filter=bool(data.get("downstream_broadcast_filter", False)),
        downstream_multicast_filter=False,
        ber_interval=None,
        ber_update_period=0,
        rf_port_state=data.get("rf_port_state"),
        omci_error_tolerant=False,
        services=services,
        profile_shaping=data.get("profile_shaping_name"),
        profile_ports=data.get("profile_ports_name"),
        profile_management=data.get("profile_management_name"),
        profile_voice=data.get("profile_voice_name"),
        template=None,
        pppoe_sessions_unlimited=False,
        collect_utilization_statistics=False,
        ports=[],
    )


async def fetch_ont_config(
    session: AsyncSession, olt_id: int, gpon_port: int, ont_id: int,
) -> OntFullConfig:
    ont = await _get_ont(session, olt_id, gpon_port, ont_id)
    if ont is None or not ont.serial:
        raise CliError(f"ONT {gpon_port}/{ont_id} не найдена")

    cached = (await session.execute(
        select(OntConfigCache).where(
            OntConfigCache.olt_id == olt_id,
            OntConfigCache.serial == ont.serial,
        )
    )).scalar_one_or_none()

    if cached is not None:
        try:
            data = _json.loads(cached.config_json)
            return _config_from_cache(data, ont, gpon_port, ont_id)
        except Exception as e:
            logger.warning(f"fetch_ont_config: bad cache for {ont.serial}: {e}")

    olt, cfg = await _load_olt_cfg(session, olt_id)
    serial = ont.serial.strip().upper()

    if serial.startswith("ELTX") and len(serial) == 12:
        try:
            raw_map = await snmp_walk_all_configs(olt.ip, cfg.snmp_community_ro)
            candidates = [k for k in raw_map.keys() if serial.startswith(k)]

            all_serials = await _all_ont_serials(session, olt_id)
            matching_full = (
                [s for s in all_serials if s.startswith(candidates[0])]
                if candidates else []
            )

            if len(candidates) == 1 and len(matching_full) == 1:
                profile_names = await snmp_fetch_profile_names(olt.ip, cfg.snmp_community_ro)
                parsed = config_from_raw(raw_map[candidates[0]])

                cc = profile_names.get("cross-connect", {})
                pt = profile_names.get("ports", {})
                mg = profile_names.get("management", {})
                sh = profile_names.get("shaping", {})
                vo = profile_names.get("voice", {})

                parsed["profile_cross_connect_name"] = cc.get(parsed.get("profile_cc_idx_0"))
                parsed["profile_ports_name"] = pt.get(parsed.get("profile_ports_idx"))
                parsed["profile_management_name"] = mg.get(parsed.get("profile_management_idx"))
                parsed["profile_shaping_name"] = sh.get(parsed.get("profile_shaping_idx"))
                parsed["profile_voice_name"] = vo.get(parsed.get("profile_voice_idx"))

                try:
                    full_services = await snmp_walk_all_full_services(
                        olt.ip, cfg.snmp_community_ro
                    )
                    custom_cc = await snmp_walk_all_custom_cc(
                        olt.ip, cfg.snmp_community_ro
                    )
                    selective = await snmp_walk_all_selective_tunnels(
                        olt.ip, cfg.snmp_community_ro
                    )

                    from .ont_config_poller import _build_services
                    parsed["services"] = _build_services(
                        full_services=full_services.get(candidates[0], {}),
                        custom_cc=custom_cc.get(candidates[0], {}),
                        selective=selective.get(candidates[0], {}),
                        profile_names=profile_names,
                    )
                except Exception as e:
                    logger.warning(f"fetch_ont_config: services SNMP: {e}")
                    parsed["services"] = []

                return _config_from_cache(parsed, ont, gpon_port, ont_id)
            else:
                logger.debug(
                    f"fetch_ont_config: префикс {candidates} неоднозначен "
                    f"({len(matching_full)} ONT в БД), fallback CLI"
                )
        except Exception as e:
            logger.warning(
                f"fetch_ont_config SNMP {olt.ip} {serial}: {type(e).__name__}: {e}, "
                f"fallback CLI"
            )

    logger.debug(f"fetch_ont_config: fallback CLI для {serial}")
    output = await _run_cli(
        session, olt_id,
        [f"show interface ont {gpon_port}/{ont_id} configuration"],
    )
    return parse_ont_config(output)


# ---- MAC-адреса ONT: БД → CLI -------------------------------------------

async def fetch_ont_macs(
    session: AsyncSession, olt_id: int, gpon_port: int, ont_id: int,
) -> list[dict]:
    ont = await _get_ont(session, olt_id, gpon_port, ont_id)
    if ont is None or not ont.serial:
        return []

    cached = (await session.execute(
        select(OntMacCache).where(
            OntMacCache.olt_id == olt_id,
            OntMacCache.serial == ont.serial,
        )
    )).scalars().all()

    if cached:
        return [
            {
                "mac": c.mac,
                "gem": c.gem,
                "uvid": c.uvid,
                "cvid": c.cvid,
                "svid": c.svid,
                "gpon_port": gpon_port,
                "ont_id": ont_id,
            }
            for c in cached
        ]

    logger.debug(f"fetch_ont_macs: нет кэша для {ont.serial}, fallback CLI")
    try:
        output = await _run_cli(
            session, olt_id,
            [f"show mac interface ont {gpon_port}/{ont_id}"],
        )
    except CliError as e:
        logger.warning(f"mac {olt_id} {gpon_port}/{ont_id}: {e}")
        return []

    entries = parse_ont_macs(output)
    return [
        {
            "gpon_port": e.gpon_port, "ont_id": e.ont_id,
            "gem": e.gem, "uvid": e.uvid, "cvid": e.cvid, "svid": e.svid,
            "mac": e.mac,
        }
        for e in entries
    ]


async def fetch_onts_macs_summary(
    session: AsyncSession, olt_id: int,
) -> dict[str, list[str]]:
    onts = (await session.execute(
        select(Ont).where(Ont.olt_id == olt_id)
    )).scalars().all()

    if not onts:
        return {}

    serials = [o.serial for o in onts if o.serial]
    if not serials:
        return {}

    macs = (await session.execute(
        select(OntMacCache).where(
            OntMacCache.olt_id == olt_id,
            OntMacCache.serial.in_(serials),
        )
    )).scalars().all()

    by_serial: dict[str, list[str]] = {}
    for m in macs:
        by_serial.setdefault(m.serial, []).append(m.mac)

    result: dict[str, list[str]] = {}
    for o in onts:
        key = f"{o.gpon_port}/{o.ont_id}"
        result[key] = by_serial.get(o.serial, [])
    return result


# ---- Порты ONT: БД → SNMP → CLI -----------------------------------------

async def fetch_ont_ports(
    session: AsyncSession, olt_id: int, gpon_port: int, ont_id: int,
) -> list[dict]:
    ont = await _get_ont(session, olt_id, gpon_port, ont_id)
    if ont is None or not ont.serial:
        return []

    cached = (await session.execute(
        select(OntPortCache).where(
            OntPortCache.olt_id == olt_id,
            OntPortCache.serial == ont.serial,
        ).order_by(OntPortCache.port_id)
    )).scalars().all()

    if cached:
        return [
            {
                "port_id": c.port_id,
                "link": c.link,
                "speed": c.speed,
                "duplex": c.duplex,
                "poe_state": c.poe_state,
            }
            for c in cached
        ]

    olt, cfg = await _load_olt_cfg(session, olt_id)
    serial = ont.serial.strip().upper()

    if serial.startswith("ELTX") and len(serial) == 12:
        try:
            rows = await snmp_get_ont_ports(olt.ip, cfg.snmp_community_ro, serial)
            if rows:
                logger.debug(f"SNMP ports {olt.ip} {serial}: {len(rows)} портов")
                return rows
        except Exception as e:
            logger.warning(
                f"SNMP ports {olt.ip} {serial}: {type(e).__name__}: {e}, fallback CLI"
            )

    logger.debug(f"fetch_ont_ports: fallback CLI для {serial}")
    try:
        output = await _run_cli(
            session, olt_id,
            [f"show interface ont {gpon_port}/{ont_id} ports"],
        )
    except CliError as e:
        logger.warning(f"ports {olt_id} {gpon_port}/{ont_id}: {e}")
        return []

    entries = parse_ont_ports(output)
    return [
        {
            "port_id": e.port_id,
            "link": e.link,
            "speed": e.speed,
            "duplex": e.duplex,
            "poe_state": e.poe_state,
        }
        for e in entries
    ]


# ---- Обновление кэшей (используется поллерами) --------------------------

async def save_macs_cache(
    session: AsyncSession, olt_id: int, serial: str,
    macs: list[dict],
):
    await session.execute(
        delete(OntMacCache).where(
            OntMacCache.olt_id == olt_id,
            OntMacCache.serial == serial,
        )
    )
    for m in macs:
        session.add(OntMacCache(
            olt_id=olt_id,
            serial=serial,
            mac=m.get("mac"),
            gem=m.get("gem"),
            uvid=m.get("uvid"),
            cvid=m.get("cvid"),
            svid=m.get("svid"),
        ))


async def save_ports_cache(
    session: AsyncSession, olt_id: int, serial: str,
    ports: list[dict],
):
    await session.execute(
        delete(OntPortCache).where(
            OntPortCache.olt_id == olt_id,
            OntPortCache.serial == serial,
        )
    )
    for p in ports:
        session.add(OntPortCache(
            olt_id=olt_id,
            serial=serial,
            port_id=p.get("port_id"),
            link=p.get("link"),
            speed=p.get("speed"),
            duplex=p.get("duplex"),
            poe_state=p.get("poe_state"),
        ))