from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from ..db import get_session
from ..services.ont_manager import (
    set_autofind, list_unactivated, add_ont, next_free_id,
    fetch_profiles, fetch_templates, fetch_profile_details,
    PROFILE_TYPES,
)
from ..services.profiles_cache import invalidate


router = APIRouter(prefix="/api/olts/{olt_id}", tags=["ont-manage"])


class AutofindRequest(BaseModel):
    enable: bool
    ports: list[int] | None = None


class CliResult(BaseModel):
    ok: bool
    output: str
    error: str | None = None


@router.post("/autofind", response_model=CliResult)
async def autofind(olt_id: int, payload: AutofindRequest,
                   session: AsyncSession = Depends(get_session)):
    result = await set_autofind(session, olt_id, payload.enable, payload.ports)
    if result.get("ok"):
        invalidate(olt_id, "unactivated")
    return CliResult(**result)


@router.get("/onts/unactivated")
async def unactivated(olt_id: int, session: AsyncSession = Depends(get_session)):
    rows = await list_unactivated(session, olt_id)
    return {"items": rows, "total": len(rows)}


@router.get("/onts/next-free-id")
async def get_next_free(olt_id: int, gpon_port: int = Query(..., ge=0, le=7),
                        session: AsyncSession = Depends(get_session)):
    return {"ont_id": await next_free_id(session, olt_id, gpon_port)}


class OntAddRequest(BaseModel):
    gpon_port: int = Field(..., ge=0, le=7)
    ont_id: int = Field(..., ge=0, le=127)
    serial: str
    description: str | None = None
    template: str | None = None
    profile_cross_connect: str | None = None
    profile_dba: str | None = None
    profile_ports: str | None = None
    profile_management: str | None = None


@router.post("/onts", response_model=CliResult)
async def add(olt_id: int, payload: OntAddRequest,
              session: AsyncSession = Depends(get_session)):
    result = await add_ont(
        session, olt_id,
        gpon_port=payload.gpon_port,
        ont_id=payload.ont_id,
        serial=payload.serial.strip().upper(),
        description=payload.description or None,
        template=payload.template or None,
        profile_cross_connect=payload.profile_cross_connect or None,
        profile_dba=payload.profile_dba or None,
        profile_ports=payload.profile_ports or None,
        profile_management=payload.profile_management or None,
    )
    return CliResult(**result)


@router.get("/profiles/{ptype}")
async def profiles(olt_id: int, ptype: str,
                   session: AsyncSession = Depends(get_session)):
    if ptype not in PROFILE_TYPES:
        raise HTTPException(400, f"Недопустимый тип: {ptype}")
    rows = await fetch_profiles(session, olt_id, ptype)
    return {"items": rows}


@router.get("/profiles/{ptype}/{name}")
async def profile_details(olt_id: int, ptype: str, name: str,
                          session: AsyncSession = Depends(get_session)):
    if ptype not in PROFILE_TYPES:
        raise HTTPException(400, f"Недопустимый тип: {ptype}")
    try:
        data = await fetch_profile_details(session, olt_id, ptype, name)
    except Exception as e:
        raise HTTPException(502, f"CLI: {type(e).__name__}: {e}")
    return {"params": data}


@router.get("/templates")
async def templates(olt_id: int, session: AsyncSession = Depends(get_session)):
    rows = await fetch_templates(session, olt_id)
    return {"items": rows}