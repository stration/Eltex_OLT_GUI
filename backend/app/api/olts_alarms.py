"""API: активные аварии OLT (CLI)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Olt
from ..services.cli_alarms import fetch_active_alarms


router = APIRouter(prefix="/api/olts", tags=["olts-alarms"])


@router.get("/{olt_id}/alarms")
async def get_olt_alarms(
    olt_id: int,
    session: AsyncSession = Depends(get_session),
):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")

    result = await fetch_active_alarms(session, olt_id)
    if result.get("error"):
        raise HTTPException(502, result["error"])

    return {"items": result["items"], "total": result["total"]}