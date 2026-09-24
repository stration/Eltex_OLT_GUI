"""Простой TTL-кэш для MAC-адресов ONT.

`show mac interface ont ...` на LTP-X занимает несколько секунд.
Кэшируем ответы на 30 секунд — этого достаточно, чтобы
мгновенно отвечать на повторные запросы из UI.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any

_TTL_SUMMARY = timedelta(seconds=30)
_TTL_SINGLE = timedelta(seconds=60)

_summary_cache: dict[int, tuple[datetime, Any]] = {}
_single_cache: dict[str, tuple[datetime, Any]] = {}
_lock = asyncio.Lock()


async def get_summary(olt_id: int) -> Any | None:
    async with _lock:
        entry = _summary_cache.get(olt_id)
        if entry and entry[0] > datetime.utcnow():
            return entry[1]
    return None


async def set_summary(olt_id: int, data: Any) -> None:
    async with _lock:
        _summary_cache[olt_id] = (datetime.utcnow() + _TTL_SUMMARY, data)


async def get_single(key: str) -> Any | None:
    async with _lock:
        entry = _single_cache.get(key)
        if entry and entry[0] > datetime.utcnow():
            return entry[1]
    return None


async def set_single(key: str, data: Any) -> None:
    async with _lock:
        _single_cache[key] = (datetime.utcnow() + _TTL_SINGLE, data)


def invalidate_olt(olt_id: int) -> None:
    """Сбросить весь кэш (MAC + портов) для OLT."""
    _summary_cache.pop(olt_id, None)
    for k in list(_single_cache.keys()):
        if k.startswith(f"{olt_id}:"):
            _single_cache.pop(k, None)
        elif k.startswith(f"ports:{olt_id}:"):
            _single_cache.pop(k, None)