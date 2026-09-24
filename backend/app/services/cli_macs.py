"""Получение MAC-таблицы коммутатора OLT через CLI (show mac)."""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from .cli_service import CliError
from .ont_manager import _run_cli
from .parsers import parse_mac_table


async def fetch_mac_table(session: AsyncSession, olt_id: int) -> dict:
    """
    Возвращает MAC-таблицу коммутатора OLT.

    Заходим в switch-view, выполняем show mac, выходим обратно.
    """
    try:
        output = await _run_cli(session, olt_id, ["switch", "show mac", "exit"])
    except CliError as e:
        logger.warning(f"macs {olt_id}: {e}")
        return {"items": [], "total": 0, "limit": 0, "error": str(e)}
    except Exception as e:
        logger.exception(f"macs {olt_id}")
        return {"items": [], "total": 0, "limit": 0, "error": f"{type(e).__name__}: {e}"}

    try:
        data = parse_mac_table(output)
    except Exception as e:
        logger.exception(f"macs parse {olt_id}")
        return {"items": [], "total": 0, "limit": 0, "error": f"parse: {e}"}

    return {**data, "error": None}