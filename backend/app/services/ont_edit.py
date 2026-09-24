"""Редактирование общих параметров ONT через CLI.

Собирает diff между текущим конфигом и переданным payload,
генерирует список CLI-команд и выполняет одну сессию configure terminal.
"""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Olt, Settings as SettingsModel
from ..security import decrypt
from .cli_service import run_script, CliError
from .ont_manager import _load_olt_cfg, fetch_ont_config


# --------------------------------------------------------------
# Генерация CLI-команд из diff
# --------------------------------------------------------------

def _q(s: str) -> str:
    """Экранирует значение в двойные кавычки для CLI."""
    # Простая защита: убираем сами кавычки
    s = s.replace('"', '')
    return f'"{s}"'


def _diff_to_commands(cur, payload: dict) -> list[str]:
    """Возвращает список команд для применения изменений.

    cur — OntFullConfig (текущее состояние).
    payload — dict с полями, которые пришли из UI.
    """
    cmds: list[str] = []

    # description
    new_desc = (payload.get("description") or "").strip()
    cur_desc = (cur.description or "").strip()
    if new_desc != cur_desc:
        if new_desc:
            cmds.append(f"description {_q(new_desc)}")
        else:
            cmds.append("no description")

    # password (только если передано непустое новое значение)
    new_pwd = (payload.get("password") or "").strip()
    cur_pwd = (cur.password or "").strip()
    if new_pwd and new_pwd != cur_pwd:
        cmds.append(f"password {new_pwd}")

    # boolean toggle — (command_on, command_off)
    bool_fields = [
        ("fec_up",                     "fec",                        "no fec"),
        ("easy_mode",                  "easy-mode",                  "no easy-mode"),
        ("downstream_broadcast",       "broadcast-downstream enable", "no broadcast-downstream enable"),
        ("downstream_broadcast_filter","broadcast-downstream filter", "no broadcast-downstream filter"),
        ("downstream_multicast_filter","multicast-downstream filter", "no multicast-downstream filter"),
        ("omci_error_tolerant",        "omci-error-tolerant",        "no omci-error-tolerant"),
    ]
    for field, on_cmd, off_cmd in bool_fields:
        if field not in payload:
            continue
        old = bool(getattr(cur, field))
        new = bool(payload[field])
        if old != new:
            cmds.append(on_cmd if new else off_cmd)

    # rf_port_state — строка
    if "rf_port_state" in payload:
        new_rf = (payload["rf_port_state"] or "").lower()
        old_rf = (cur.rf_port_state or "").lower()
        if new_rf in ("enabled", "disabled", "no-change") and new_rf != old_rf:
            cmds.append(f"rf-port-state {new_rf}")

    # профили
    profile_fields = [
        ("profile_ports",      "profile ports"),
        ("profile_management", "profile management"),
        ("profile_shaping",    "profile shaping"),
        ("profile_voice",      "profile voice"),
    ]
    for field, cmd in profile_fields:
        if field not in payload:
            continue
        new_val = (payload[field] or "").strip()
        old_val = (getattr(cur, field) or "").strip()
        if new_val == old_val:
            continue
        if new_val:
            cmds.append(f"{cmd} {new_val}")
        else:
            # Предположение: 'no <cmd>' снимает назначение
            cmds.append(f"no {cmd}")

    # template
    if "template" in payload:
        new_t = (payload["template"] or "").strip()
        old_t = (cur.template or "").strip()
        if new_t != old_t:
            if new_t:
                cmds.append(f"template {new_t}")
            else:
                cmds.append("no template")

    return cmds


# --------------------------------------------------------------
# Публичная функция
# --------------------------------------------------------------

async def update_ont_general(
    session: AsyncSession,
    olt_id: int,
    port: int,
    ont_id: int,
    payload: dict,
) -> dict:
    """Применяет изменения. Возвращает {ok, output, error, changes}."""
    try:
        cur = await fetch_ont_config(session, olt_id, port, ont_id)
    except CliError as e:
        return {"ok": False, "output": "", "error": f"Не удалось прочитать конфиг: {e}"}
    except Exception as e:
        logger.exception(f"update_ont_general: read {olt_id} {port}/{ont_id}")
        return {"ok": False, "output": "", "error": f"{type(e).__name__}: {e}"}

    cmds_inner = _diff_to_commands(cur, payload)

    if not cmds_inner:
        return {"ok": True, "output": "Нет изменений", "error": None, "changes": []}

    # Оборачиваем в configure terminal
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

    logger.info(f"ONT edit {olt.ip} {port}/{ont_id}: {cmds_inner}")
    try:
        output = await run_script(
            cfg.default_transport, olt.ip, cfg.cli_user, password,
            full, timeout=45.0,
        )
    except CliError as e:
        return {"ok": False, "output": "", "error": str(e), "changes": cmds_inner}
    except Exception as e:
        logger.exception(f"update_ont_general: apply {olt_id} {port}/{ont_id}")
        return {"ok": False, "output": "", "error": f"{type(e).__name__}: {e}",
                "changes": cmds_inner}

    low = output.lower()
    for marker in ("% invalid", "% incomplete", "% ambiguous", "% error"):
        if marker in low:
            idx = low.find(marker)
            return {
                "ok": False, "output": output,
                "error": output[max(0, idx - 40): idx + 200].strip(),
                "changes": cmds_inner,
            }

    return {"ok": True, "output": output, "error": None, "changes": cmds_inner}