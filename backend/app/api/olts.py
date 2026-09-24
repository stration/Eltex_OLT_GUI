from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Olt, Settings as SettingsModel
from ..schemas import OltIn, OltPatch, OltOut, CheckResult, GponPortState
from ..services.checker import check_olt, check_many
from ..services.snmp_pon import snmp_get_pon_channels


router = APIRouter(prefix="/api/olts", tags=["olts"])


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


@router.get("", response_model=list[OltOut])
async def list_olts(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Olt).order_by(Olt.ip))).scalars().all()
    return rows


@router.post("", response_model=OltOut, status_code=201)
async def add_olt(payload: OltIn, session: AsyncSession = Depends(get_session)):
    ip = str(payload.ip)
    exists = (await session.execute(
        select(Olt).where(Olt.ip == ip)
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(409, f"OLT {ip} уже добавлен")
    olt = Olt(ip=ip, name=payload.name, notes=payload.notes, status="unknown")
    session.add(olt)
    await session.commit()
    await session.refresh(olt)
    return olt


@router.post("/check-all", response_model=list[CheckResult])
async def check_all(session: AsyncSession = Depends(get_session)):
    cfg = await _settings(session)
    rows = (await session.execute(select(Olt))).scalars().all()
    pairs = [(o.id, o.ip) for o in rows]
    results = await check_many(pairs, cfg.snmp_community_ro)

    by_id = {o.id: o for o in rows}
    out: list[CheckResult] = []
    for olt_id, res in results:
        o = by_id[olt_id]
        o.status = "online" if (res["ping_ok"] or res["snmp_ok"]) else "offline"
        o.last_ping_ms = res["ping_ms"]
        if o.status == "online":
            o.last_seen_at = datetime.utcnow()
        if res["model"]:
            o.model = res["model"]
        if res["hw_revision"]:
            o.hw_revision = res["hw_revision"]
        out.append(CheckResult(**res))
    await session.commit()
    return out


@router.get("/{olt_id}", response_model=OltOut)
async def get_olt(olt_id: int, session: AsyncSession = Depends(get_session)):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")
    return olt


@router.patch("/{olt_id}", response_model=OltOut)
async def patch_olt(
    olt_id: int, payload: OltPatch,
    session: AsyncSession = Depends(get_session),
):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")
    if payload.name is not None:
        olt.name = payload.name
    if payload.notes is not None:
        olt.notes = payload.notes
    await session.commit()
    await session.refresh(olt)
    return olt


@router.delete("/{olt_id}", status_code=204)
async def delete_olt(olt_id: int, session: AsyncSession = Depends(get_session)):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")
    await session.delete(olt)
    await session.commit()


@router.post("/{olt_id}/check", response_model=CheckResult)
async def check_one(olt_id: int, session: AsyncSession = Depends(get_session)):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")
    cfg = await _settings(session)
    res = await check_olt(olt.ip, cfg.snmp_community_ro)
    olt.status = "online" if (res["ping_ok"] or res["snmp_ok"]) else "offline"
    olt.last_ping_ms = res["ping_ms"]
    olt.last_seen_at = datetime.utcnow() if olt.status == "online" else olt.last_seen_at
    if res["model"]:
        olt.model = res["model"]
    if res["hw_revision"]:
        olt.hw_revision = res["hw_revision"]
    await session.commit()
    return CheckResult(**res)


@router.get("/{olt_id}/gpon-ports", response_model=list[GponPortState])
async def get_gpon_ports(
    olt_id: int, session: AsyncSession = Depends(get_session),
):
    olt = await session.get(Olt, olt_id)
    if not olt:
        raise HTTPException(404, "OLT не найден")
    cfg = await _settings(session)
    max_port = 7 if (olt.model or "").endswith("8X") else 3
    try:
        ports = await snmp_get_pon_channels(
            olt.ip, cfg.snmp_community_ro, max_port=max_port,
        )
    except Exception as e:
        logger.warning(f"SNMP gpon-ports {olt.ip}: {type(e).__name__}: {e}")
        raise HTTPException(502, f"SNMP: {type(e).__name__}: {e}")
    return ports