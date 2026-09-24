from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..db import get_session
from ..services.ont_edit import update_ont_general


router = APIRouter(prefix="/api/olts/{olt_id}/onts", tags=["ont-edit"])


class OntGeneralEditRequest(BaseModel):
    # Все поля опциональные — применяются только переданные
    description: str | None = None
    password: str | None = None
    fec_up: bool | None = None
    easy_mode: bool | None = None
    downstream_broadcast: bool | None = None
    downstream_broadcast_filter: bool | None = None
    downstream_multicast_filter: bool | None = None
    omci_error_tolerant: bool | None = None
    rf_port_state: str | None = None
    profile_ports: str | None = None
    profile_management: str | None = None
    profile_shaping: str | None = None
    profile_voice: str | None = None
    template: str | None = None


class OntGeneralEditResponse(BaseModel):
    ok: bool
    output: str
    error: str | None = None
    changes: list[str] = []


@router.put("/{port}/{ont_id}/general", response_model=OntGeneralEditResponse)
async def edit_general(
    olt_id: int, port: int, ont_id: int,
    payload: OntGeneralEditRequest,
    session: AsyncSession = Depends(get_session),
):
    data = payload.model_dump(exclude_unset=True)
    result = await update_ont_general(session, olt_id, port, ont_id, data)
    return OntGeneralEditResponse(**result)