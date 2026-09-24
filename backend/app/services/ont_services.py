"""Управление сервисами ONT: cross-connect, dba, custom, selective-tunnel."""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from .cli_service import run_script, CliError
from .ont_manager import _load_olt_cfg, fetch_ont_config
from ..security import decrypt


def _diff_service_commands(cur_service, payload: dict) -> list[str]:
    """Генерирует CLI-команды для изменения одного сервиса."""
    cmds: list[str] = []
    sid = cur_service.service_id

    # profile cross-connect
    if "profile_cross_connect" in payload:
        new = (payload["profile_cross_connect"] or "").strip() or None
        old = cur_service.profile_cross_connect
        if new != old:
            if new:
                cmds.append(f"service {sid} profile cross-connect {new}")
            else:
                cmds.append(f"no service {sid} profile cross-connect")

    # profile dba
    if "profile_dba" in payload:
        new = (payload["profile_dba"] or "").strip() or None
        old = cur_service.profile_dba
        if new != old:
            if new:
                cmds.append(f"service {sid} profile dba {new}")
            else:
                cmds.append(f"no service {sid} profile dba")

    # custom cross-connect
    custom_keys = ("custom_enabled", "cvid", "svid", "cos")
    if any(k in payload for k in custom_keys):
        new_enabled = bool(payload.get("custom_enabled", False))
        old_enabled = cur_service.custom_cross_connect == "enabled"

        if not new_enabled and old_enabled:
            cmds.append(f"no service {sid} custom")
        elif new_enabled:
            # При включении командой `service N custom cvid/svid/cos`
            # custom активируется автоматически.
            for fld, cmd in (("cvid", "cvid"), ("svid", "svid"), ("cos", "cos")):
                if fld not in payload or payload[fld] is None:
                    continue
                cmds.append(f"service {sid} custom {cmd} {payload[fld]}")

    # selective-tunnel uvid (единым списком)
    if "selective_tunnel_uvid" in payload:
        new_uvid = (payload["selective_tunnel_uvid"] or "").strip()
        old_uvid = (cur_service.selective_tunnel_user_vlans or "").strip()
        if new_uvid != old_uvid:
            if old_uvid:
                cmds.append(f"no service {sid} selective-tunnel uvid")
            if new_uvid:
                cmds.append(f"service {sid} selective-tunnel uvid {new_uvid}")

    # utilization-enable (это флаг уровня ONT, но команда сервисная)
    if "utilization_enable" in payload:
        new = bool(payload["utilization_enable"])
        # Нужен доступ к текущему значению — передаётся отдельно в payload
        old = bool(payload.get("_current_utilization", False))
        if new != old:
            if new:
                cmds.append(f"service {sid} utilization-enable")
            else:
                cmds.append(f"no service {sid} utilization-enable")

    return cmds


async def update_service(
    session: AsyncSession, olt_id: int,
    port: int, ont_id: int, service_id: int, payload: dict,
) -> dict:
    """Применяет изменения одного сервиса."""
    try:
        cur = await fetch_ont_config(session, olt_id, port, ont_id)
    except CliError as e:
        return {"ok": False, "output": "", "error": f"Не удалось прочитать конфиг: {e}",
                "changes": []}

    cur_service = next((s for s in cur.services if s.service_id == service_id), None)
    if cur_service is None:
        return {"ok": False, "output": "",
                "error": f"Сервис {service_id} не найден в конфиге ONT",
                "changes": []}

    # utilization-флаг уровня ONT передаём в diff
    payload["_current_utilization"] = cur.collect_utilization_statistics

    cmds_inner = _diff_service_commands(cur_service, payload)
    if not cmds_inner:
        return {"ok": True, "output": "Нет изменений", "error": None, "changes": []}

    full = [
        "configure terminal",
        f"interface ont {port}/{ont_id}",
        *cmds_inner,
        "do commit",
        "do save",
        "exit",
        "exit",
    ]

    olt, cfg = await _load_olt_cfg(session, olt_id)
    password = decrypt(cfg.cli_password_enc) or ""

    logger.info(f"ONT svc edit {olt.ip} {port}/{ont_id} svc{service_id}: {cmds_inner}")
    try:
        output = await run_script(
            cfg.default_transport, olt.ip, cfg.cli_user, password,
            full, timeout=45.0,
        )
    except CliError as e:
        return {"ok": False, "output": "", "error": str(e), "changes": cmds_inner}
    except Exception as e:
        logger.exception(f"update_service {olt_id}")
        return {"ok": False, "output": "", "error": f"{type(e).__name__}: {e}",
                "changes": cmds_inner}

    low = output.lower()
    for marker in ("% invalid", "% incomplete", "% ambiguous", "% error"):
        if marker in low:
            idx = low.find(marker)
            return {"ok": False, "output": output,
                    "error": output[max(0, idx - 40): idx + 200].strip(),
                    "changes": cmds_inner}

    return {"ok": True, "output": output, "error": None, "changes": cmds_inner}


async def delete_service(
    session: AsyncSession, olt_id: int, port: int, ont_id: int, service_id: int,
) -> dict:
    full = [
        "configure terminal",
        f"interface ont {port}/{ont_id}",
        f"no service {service_id}",
        "do commit",
        "do save",
        "exit",
        "exit",
    ]

    olt, cfg = await _load_olt_cfg(session, olt_id)
    password = decrypt(cfg.cli_password_enc) or ""

    logger.info(f"ONT svc delete {olt.ip} {port}/{ont_id} svc{service_id}")
    try:
        output = await run_script(
            cfg.default_transport, olt.ip, cfg.cli_user, password,
            full, timeout=45.0,
        )
    except CliError as e:
        return {"ok": False, "output": "", "error": str(e)}
    except Exception as e:
        logger.exception(f"delete_service {olt_id}")
        return {"ok": False, "output": "", "error": f"{type(e).__name__}: {e}"}

    low = output.lower()
    for marker in ("% invalid", "% incomplete", "% ambiguous", "% error"):
        if marker in low:
            idx = low.find(marker)
            return {"ok": False, "output": output,
                    "error": output[max(0, idx - 40): idx + 200].strip()}
    return {"ok": True, "output": output, "error": None}