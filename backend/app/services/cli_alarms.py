"""Получение активных аварий OLT через CLI."""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from .cli_service import CliError
from .ont_manager import _run_cli  # переиспользуем готовый helper
from .parsers import parse_alarm_active


async def fetch_active_alarms(
    session: AsyncSession, olt_id: int,
) -> dict:
    """
    Возвращает активные аварии OLT через `show alarm active all`.

    Формат ответа:
      {"items": [...], "total": N, "error": None}
    """
    try:
        output = await _run_cli(
            session, olt_id, ["show alarm active all"],
        )
    except CliError as e:
        logger.warning(f"alarms {olt_id}: {e}")
        return {"items": [], "total": 0, "error": str(e)}
    except Exception as e:
        logger.exception(f"alarms {olt_id}")
        return {"items": [], "total": 0, "error": f"{type(e).__name__}: {e}"}

    try:
        items = parse_alarm_active(output)
    except Exception as e:
        logger.exception(f"alarms parse {olt_id}")
        return {"items": [], "total": 0, "error": f"parse: {e}"}

    return {"items": items, "total": len(items), "error": None}