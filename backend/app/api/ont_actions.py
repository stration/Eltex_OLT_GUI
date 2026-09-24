import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from ..db import get_session
from ..services.ont_actions import perform_action, ACTIONS


router = APIRouter(prefix="/api/olts/{olt_id}/onts", tags=["ont-actions"])


class ActionRequest(BaseModel):
    confirm: bool = Field(..., description="true — подтверждение выполнения")


class ActionResponse(BaseModel):
    ok: bool
    output: str
    error: str | None = None


_SERIAL_PATTERNS = [
    re.compile(r"^[A-Z]{4}[0-9A-F]{8}$"),                  # ELTX62151198
    re.compile(r"^[0-9A-F]{16}$"),                          # 454C54580800F6B1
    re.compile(r"^([0-9A-F]{2}-){7}[0-9A-F]{2}$"),          # 45-4C-54-...
]


@router.post("/{port}/{ont_id}/actions/{action}", response_model=ActionResponse)
async def do_action(
    olt_id: int,
    port: int,
    ont_id: int,
    action: str,
    payload: ActionRequest,
    new_serial: str | None = Query(None, description="Только для action=replace-serial"),
    session: AsyncSession = Depends(get_session),
):
    if not payload.confirm:
        raise HTTPException(400, "Требуется confirm: true")
    if action not in ACTIONS:
        raise HTTPException(400, f"Недопустимое действие: {action}")

    if action == "replace-serial":
        if not new_serial:
            raise HTTPException(400, "Для replace-serial нужно указать new_serial")
        if not any(p.match(new_serial) for p in _SERIAL_PATTERNS):
            raise HTTPException(400, "Неверный формат серийного номера")

    result = await perform_action(
        session, olt_id, port, ont_id, action, new_serial=new_serial,
    )
    return ActionResponse(**result)