"""API: MAC-таблица коммутатора OLT (CLI)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Olt
from ..services.cli_macs import fetch_mac_table


router = APIRouter(prefix="/api/olts", tags=["olts-macs"])


@router.get("/{olt_id}/macs")
async def get_olt_macs(
    olt_id: int,
    session: AsyncSession = Depends(get_session),
):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")

    result = await fetch_mac_table(session, olt_id)
    if result.get("error"):
        raise HTTPException(502, result["error"])

    return {
        "items": result["items"],
        "total": result["total"],
        "limit": result["limit"],
    }