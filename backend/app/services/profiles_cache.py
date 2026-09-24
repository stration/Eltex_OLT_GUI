"""Простой TTL-кэш для списков профилей/шаблонов.

CLI-команды `show profile X` медленные (~1 сек). Кэшируем ответы на 5 минут.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

_TTL = timedelta(minutes=5)
_cache: dict[int, dict[str, tuple[datetime, Any]]] = {}
_lock = asyncio.Lock()


async def get_or_fetch(
    olt_id: int, key: str, fetch: Callable[[], Awaitable[Any]]
) -> Any:
    async with _lock:
        bucket = _cache.setdefault(olt_id, {})
        entry = bucket.get(key)
        if entry and entry[0] > datetime.utcnow():
            return entry[1]

    data = await fetch()

    async with _lock:
        _cache.setdefault(olt_id, {})[key] = (datetime.utcnow() + _TTL, data)
    return data


def invalidate(olt_id: int, key: str | None = None):
    if key is None:
        _cache.pop(olt_id, None)
    else:
        _cache.get(olt_id, {}).pop(key, None)