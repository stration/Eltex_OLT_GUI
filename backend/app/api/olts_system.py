"""API: системная информация OLT (SNMP)."""
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Olt, Settings as SettingsModel
from ..schemas import OltSystemInfo
from ..services.snmp_system import snmp_get_system


router = APIRouter(prefix="/api/olts", tags=["olts-system"])


async def _settings(session: AsyncSession) -> SettingsModel:
    row = (await session.execute(
        select(SettingsModel).where(SettingsModel.id == 1)
    )).scalar_one_or_none()
    if row is None:
        row = SettingsModel(id=1)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


@router.get("/{olt_id}/system", response_model=OltSystemInfo)
async def get_olt_system(
    olt_id: int,
    session: AsyncSession = Depends(get_session),
):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")
    cfg = await _settings(session)

    try:
        data = await snmp_get_system(olt.ip, cfg.snmp_community_ro)
    except Exception as e:
        logger.warning(f"SNMP system {olt.ip}: {type(e).__name__}: {e}")
        raise HTTPException(502, f"SNMP: {type(e).__name__}: {e}")

    return OltSystemInfo(**data)