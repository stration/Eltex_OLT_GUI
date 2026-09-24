from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta
from dataclasses import asdict

from ..db import get_session
from ..models import Olt, Ont, RssiHistory
from ..services.ont_manager import (
    fetch_ont_macs,
    fetch_onts_macs_summary,
    fetch_ont_config,
    fetch_ont_ports,
)
from ..services.macs_cache import invalidate_olt as _invalidate_macs_cache
from ..services.cli_service import CliError


router = APIRouter(prefix="/api/olts/{olt_id}/onts", tags=["onts"])


class OntOut(BaseModel):
    id: int
    olt_id: int
    gpon_port: int
    ont_id: int
    serial: str
    status: str
    rssi_db: float | None
    version: str | None
    equipment_id: str | None
    description: str | None
    last_seen_at: datetime | None
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---- Список ONT ----------------------------------------------------------

@router.get("", response_model=list[OntOut])
async def list_onts(
    olt_id: int,
    status: str | None = Query(None),
    gpon_port: int | None = None,
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    olt = await session.get(Olt, olt_id)
    if olt is None:
        raise HTTPException(404, "OLT не найден")

    q = select(Ont).where(Ont.olt_id == olt_id)
    if status:
        q = q.where(Ont.status == status)
    if gpon_port is not None:
        q = q.where(Ont.gpon_port == gpon_port)
    q = q.order_by(Ont.gpon_port, Ont.ont_id)

    rows = (await session.execute(q)).scalars().all()

    if search:
        needle = search.lower()
        rows = [
            r for r in rows
            if needle in (r.serial or "").lower()
            or needle in (r.description or "").lower()
            or needle in (r.equipment_id or "").lower()
        ]
    return rows


# ---- Сводка --------------------------------------------------------------

@router.get("/summary")
async def summary(olt_id: int, session: AsyncSession = Depends(get_session)):
    olt = await session.get(Olt, olt_id)
    if olt is None:
        raise HTTPException(404, "OLT не найден")

    rows = (await session.execute(
        select(Ont).where(Ont.olt_id == olt_id)
    )).scalars().all()

    by_status: dict[str, int] = {}
    by_port: dict[int, dict[str, int]] = {}
    max_port = 7 if (olt.model or "").endswith("8X") else 3
    for p in range(max_port + 1):
        by_port[p] = {}

    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        port_map = by_port.setdefault(r.gpon_port, {})
        port_map[r.status] = port_map.get(r.status, 0) + 1

    return {"total": len(rows), "by_status": by_status, "by_port": by_port}


# ---- Автообнаружение ----------------------------------------------------

@router.get("/unactivated")
async def unactivated(
    olt_id: int,
    session: AsyncSession = Depends(get_session),
):
    from ..services.ont_manager import list_unactivated
    rows = await list_unactivated(session, olt_id)
    return {"items": rows, "total": len(rows)}


@router.get("/next-free-id")
async def next_free(
    olt_id: int, gpon_port: int = Query(..., ge=0, le=7),
    session: AsyncSession = Depends(get_session),
):
    from ..services.ont_manager import next_free_id
    return {"ont_id": await next_free_id(session, olt_id, gpon_port)}


# ---- MAC-адреса ----------------------------------------------------------

@router.get("/macs-summary")
async def macs_summary(
    olt_id: int, session: AsyncSession = Depends(get_session),
):
    """
    Возвращает MAC-адреса всех ONT OLT.
    Формат: {"by_ont": {"0/1": ["2C:4D:54:83:8B:70"], "0/2": [...], ...}}
    """
    olt = await session.get(Olt, olt_id)
    if olt is None:
        raise HTTPException(404, "OLT не найден")
    data = await fetch_onts_macs_summary(session, olt_id)
    return {"by_ont": data}


@router.post("/macs-cache/clear")
async def clear_macs_cache(
    olt_id: int, session: AsyncSession = Depends(get_session),
):
    olt = await session.get(Olt, olt_id)
    if olt is None:
        raise HTTPException(404, "OLT не найден")
    _invalidate_macs_cache(olt_id)
    return {"ok": True}


# ---- Карточка ONT -------------------------------------------------------

@router.get("/{gpon_port}/{ont_id}", response_model=OntOut)
async def get_ont(
    olt_id: int, gpon_port: int, ont_id: int,
    session: AsyncSession = Depends(get_session),
):
    row = (await session.execute(
        select(Ont).where(
            Ont.olt_id == olt_id,
            Ont.gpon_port == gpon_port,
            Ont.ont_id == ont_id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "ONT не найден")
    return row


@router.get("/{gpon_port}/{ont_id}/rssi-history")
async def rssi_history(
    olt_id: int, gpon_port: int, ont_id: int,
    hours: int = Query(24, ge=1, le=24 * 30),
    session: AsyncSession = Depends(get_session),
):
    ont = (await session.execute(
        select(Ont).where(
            Ont.olt_id == olt_id,
            Ont.gpon_port == gpon_port,
            Ont.ont_id == ont_id,
        )
    )).scalar_one_or_none()
    if ont is None:
        raise HTTPException(404, "ONT не найден")

    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (await session.execute(
        select(RssiHistory)
        .where(RssiHistory.ont_pk == ont.id, RssiHistory.ts >= since)
        .order_by(RssiHistory.ts)
    )).scalars().all()

    return {
        "ont_id": ont_id,
        "gpon_port": gpon_port,
        "hours": hours,
        "points": [{"ts": r.ts.isoformat(), "rssi_db": r.rssi_db} for r in rows],
    }


@router.get("/{gpon_port}/{ont_id}/configuration")
async def get_ont_configuration(
    olt_id: int, gpon_port: int, ont_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        cfg = await fetch_ont_config(session, olt_id, gpon_port, ont_id)
    except CliError as e:
        raise HTTPException(502, f"OLT не отвечает: {e}")
    return asdict(cfg)


@router.get("/{gpon_port}/{ont_id}/macs")
async def ont_macs(
    olt_id: int, gpon_port: int, ont_id: int,
    session: AsyncSession = Depends(get_session),
):
    rows = await fetch_ont_macs(session, olt_id, gpon_port, ont_id)
    return {"items": rows, "total": len(rows)}


@router.get("/{gpon_port}/{ont_id}/ports")
async def ont_ports(
    olt_id: int, gpon_port: int, ont_id: int,
    session: AsyncSession = Depends(get_session),
):
    rows = await fetch_ont_ports(session, olt_id, gpon_port, ont_id)
    return {"items": rows, "total": len(rows)}