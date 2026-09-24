from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Olt, Settings as SettingsModel
from ..security import decrypt
from ..services.cli_service import ssh_run_cmd, telnet_run_cmd, CliError


router = APIRouter(prefix="/api/olts/{olt_id}", tags=["olt-backup"])


async def _load(session: AsyncSession, olt_id: int):
    olt = await session.get(Olt, olt_id)
    if olt is None:
        raise HTTPException(404, "OLT не найден")
    cfg = await session.get(SettingsModel, 1)
    if cfg is None or not cfg.cli_user or cfg.cli_password_enc is None:
        raise HTTPException(400, "Не заданы учётные данные CLI")
    return olt, cfg


async def _run_show(olt, cfg, command: str) -> str:
    password = decrypt(cfg.cli_password_enc) or ""
    try:
        if cfg.default_transport == "ssh":
            return await ssh_run_cmd(
                olt.ip, cfg.cli_user, password, command, timeout=60,
            )
        else:
            return await telnet_run_cmd(
                olt.ip, cfg.cli_user, password, command, timeout=60,
            )
    except CliError as e:
        raise HTTPException(502, f"OLT не отвечает: {e}")


@router.get("/running-config", response_class=PlainTextResponse)
async def get_running_config(
    olt_id: int, session: AsyncSession = Depends(get_session),
):
    olt, cfg = await _load(session, olt_id)
    text = await _run_show(olt, cfg, "show running-config")
    return PlainTextResponse(text)


@router.get("/running-config/download")
async def download_running_config(
    olt_id: int, session: AsyncSession = Depends(get_session),
):
    olt, cfg = await _load(session, olt_id)
    text = await _run_show(olt, cfg, "show running-config")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_ip = olt.ip.replace(":", "_").replace("/", "_")
    filename = f"ltp-{safe_ip}-running-config-{ts}.txt"

    return Response(
        content=text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )