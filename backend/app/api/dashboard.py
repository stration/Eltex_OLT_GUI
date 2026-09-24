"""API: сводные метрики для главной страницы."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Olt, Ont


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(session: AsyncSession = Depends(get_session)):
    """
    Сводка по всем OLT и ONT.

    Возвращает:
      olts_total, olts_online, olts_offline,
      onts_total, onts_ok, onts_offline, onts_other
    """
    # OLT
    olts_total = (await session.execute(
        select(func.count()).select_from(Olt)
    )).scalar_one()

    olts_online = (await session.execute(
        select(func.count()).select_from(Olt).where(Olt.status == "online")
    )).scalar_one()

    olts_offline = olts_total - olts_online

    # ONT
    onts_total = (await session.execute(
        select(func.count()).select_from(Ont)
    )).scalar_one()

    onts_ok = (await session.execute(
        select(func.count()).select_from(Ont).where(Ont.status == "OK")
    )).scalar_one()

    onts_offline = (await session.execute(
        select(func.count()).select_from(Ont).where(Ont.status == "OFFLINE")
    )).scalar_one()

    onts_other = onts_total - onts_ok - onts_offline

    return {
        "olts_total": olts_total,
        "olts_online": olts_online,
        "olts_offline": olts_offline,
        "onts_total": onts_total,
        "onts_ok": onts_ok,
        "onts_offline": onts_offline,
        "onts_other": onts_other,
    }