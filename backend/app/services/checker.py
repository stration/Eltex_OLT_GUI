"""Проверка доступности OLT: ping + SNMP-get + (опционально) CLI."""
import asyncio
from datetime import datetime
from icmplib import async_ping
from loguru import logger

from .snmp_service import check_olt_snmp, parse_model_from_descr


async def check_olt(ip: str, community: str, do_ping: bool = True) -> dict:
    ping_ok = False
    ping_ms: int | None = None

    if do_ping:
        try:
            host = await async_ping(ip, count=1, timeout=2, privileged=False)
            ping_ok = host.is_alive
            if ping_ok:
                ping_ms = int(host.avg_rtt)
        except Exception as e:
            logger.debug(f"ping {ip}: {e}")

    snmp_ok, descr, snmp_err = await check_olt_snmp(ip, community)
    model, rev = parse_model_from_descr(descr)

    return {
        "ip": ip,
        "ping_ok": ping_ok,
        "ping_ms": ping_ms,
        "snmp_ok": snmp_ok,
        "snmp_error": snmp_err,
        "model": model,
        "hw_revision": rev,
    }


async def check_many(items: list[tuple[int, str]], community: str,
                     concurrency: int = 5) -> list[tuple[int, dict]]:
    sem = asyncio.Semaphore(concurrency)
    results: list[tuple[int, dict]] = []

    async def one(olt_id: int, ip: str):
        async with sem:
            return olt_id, await check_olt(ip, community)

    tasks = [asyncio.create_task(one(i, ip)) for i, ip in items]
    for coro in asyncio.as_completed(tasks):
        results.append(await coro)
    return results