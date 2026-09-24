from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from ..db import get_session
from ..services.ont_services import update_service, delete_service


router = APIRouter(prefix="/api/olts/{olt_id}/onts", tags=["ont-services"])


class ServiceEditRequest(BaseModel):
    profile_cross_connect: str | None = None
    profile_dba: str | None = None
    custom_enabled: bool | None = None
    cvid: int | None = Field(None, ge=1, le=4094)
    svid: int | None = Field(None, ge=1, le=4094)
    cos: int | None = Field(None, ge=0, le=7)
    selective_tunnel_uvid: str | None = None
    utilization_enable: bool | None = None


class ServiceEditResponse(BaseModel):
    ok: bool
    output: str
    error: str | None = None
    changes: list[str] = []


@router.put(
    "/{port}/{ont_id}/services/{service_id}",
    response_model=ServiceEditResponse,
)
async def edit_service(
    olt_id: int, port: int, ont_id: int, service_id: int,
    payload: ServiceEditRequest,
    session: AsyncSession = Depends(get_session),
):
    if service_id < 0 or service_id > 28:
        raise HTTPException(400, "service_id должен быть в диапазоне 0..28")
    data = payload.model_dump(exclude_unset=True)
    result = await update_service(session, olt_id, port, ont_id, service_id, data)
    return ServiceEditResponse(**result)


@router.delete(
    "/{port}/{ont_id}/services/{service_id}",
    response_model=ServiceEditResponse,
)
async def remove_service(
    olt_id: int, port: int, ont_id: int, service_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await delete_service(session, olt_id, port, ont_id, service_id)
    return ServiceEditResponse(**result)