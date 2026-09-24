"""API: VLAN OLT (SNMP)."""
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Olt, Settings as SettingsModel
from ..services.snmp_vlan import snmp_get_vlans


router = APIRouter(prefix="/api/olts", tags=["olts-vlans"])


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


@router.get("/{olt_id}/vlans")
async def get_olt_vlans(
    olt_id: int,
    session: AsyncSession = Depends(get_session),
):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")
    cfg = await _settings(session)

    try:
        data = await snmp_get_vlans(
            olt.ip, cfg.snmp_community_ro, model=olt.model,
        )
    except Exception as e:
        logger.warning(f"SNMP vlans {olt.ip}: {type(e).__name__}: {e}")
        raise HTTPException(502, f"SNMP: {type(e).__name__}: {e}")

    return data