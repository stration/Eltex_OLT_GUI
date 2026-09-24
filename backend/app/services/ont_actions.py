"""Действия над ONT через CLI: reconfigure, reset, restore, enable/disable,
replace-serial, delete. Все операции идут через 'configure terminal' при
необходимости и завершаются commit/save."""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Olt, Settings as SettingsModel
from ..security import decrypt
from .cli_service import run_script, CliError


ACTIONS = {
    "reconfigure",
    "reset",
    "restore",
    "enable",
    "disable",
    "replace-serial",
    "delete",
}


async def _load_olt_cfg(session: AsyncSession, olt_id: int) -> tuple[Olt, SettingsModel]:
    olt = await session.get(Olt, olt_id)
    if olt is None:
        raise CliError(f"OLT {olt_id} не найден")
    cfg = await session.get(SettingsModel, 1)
    if cfg is None or not cfg.cli_user or cfg.cli_password_enc is None:
        raise CliError("Не заданы учётки CLI")
    return olt, cfg


def _commands_for_action(action: str, port: int, ont_id: int,
                         new_serial: str | None) -> list[str]:
    """Возвращает список CLI-команд для действия."""
    ont_ref = f"{port}/{ont_id}"

    if action == "reconfigure":
        return [f"reconfigure interface ont {ont_ref}"]

    if action == "reset":
        return [f"send omci reset interface ont {ont_ref}"]

    if action == "restore":
        return [f"send omci restore interface ont {ont_ref}"]

    if action == "enable":
        return [
            "configure terminal",
            f"interface ont {ont_ref}",
            "no shutdown",
            "do commit",
            "do save",
            "exit",
            "exit",
        ]

    if action == "disable":
        return [
            "configure terminal",
            f"interface ont {ont_ref}",
            "shutdown",
            "do commit",
            "do save",
            "exit",
            "exit",
        ]

    if action == "replace-serial":
        if not new_serial:
            raise CliError("Не задан новый серийник")
        return [
            "configure terminal",
            f"interface ont {ont_ref}",
            f"serial {new_serial}",
            "do commit",
            "do save",
            "exit",
            "exit",
        ]

    if action == "delete":
        # Удаление ONT из конфигурации — команда ГЛОБАЛЬНОГО config view,
        # а не из контекста interface ont.
        return [
            "configure terminal",
            f"no interface ont {ont_ref}",
            "do commit",
            "do save",
            "exit",
        ]

    raise CliError(f"Неизвестное действие: {action}")


async def perform_action(
    session: AsyncSession,
    olt_id: int,
    port: int,
    ont_id: int,
    action: str,
    new_serial: str | None = None,
) -> dict:
    """Выполняет действие. Возвращает {ok, output, error}."""
    if action not in ACTIONS:
        return {"ok": False, "output": "", "error": f"Действие '{action}' не поддерживается"}

    olt, cfg = await _load_olt_cfg(session, olt_id)
    password = decrypt(cfg.cli_password_enc) or ""
    commands = _commands_for_action(action, port, ont_id, new_serial)

    logger.info(f"ONT action {action} {olt.ip} {port}/{ont_id}: {commands}")

    try:
        output = await run_script(
            cfg.default_transport, olt.ip, cfg.cli_user, password, commands,
            timeout=45.0,
        )
    except CliError as e:
        logger.warning(f"ONT action {action} {olt.ip} {port}/{ont_id}: {e}")
        return {"ok": False, "output": "", "error": str(e)}
    except Exception as e:
        logger.exception(f"ONT action {action} {olt.ip} {port}/{ont_id}")
        return {"ok": False, "output": "", "error": f"{type(e).__name__}: {e}"}

    # Эвристика «получилось»: ищем признаки ошибок в выводе CLI
    low = output.lower()
    error_markers = [
        "% invalid", "% incomplete", "% ambiguous",
        "% error", "invalid input", "incomplete command",
        "ambiguous command", "unknown command",
    ]
    detected_error = None
    for marker in error_markers:
        if marker in low:
            idx = low.find(marker)
            detected_error = output[max(0, idx - 40): idx + 160].strip()
            break

    if detected_error:
        return {"ok": False, "output": output, "error": detected_error}

    return {"ok": True, "output": output, "error": None}