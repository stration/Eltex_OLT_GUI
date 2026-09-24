from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from loguru import logger

from ..db import get_session
from ..models import Settings as SettingsModel
from ..schemas import SettingsIn, SettingsOut, ConnectionTest
from ..security import encrypt, decrypt
from ..services.cli_service import test_cli

router = APIRouter(prefix="/api/settings", tags=["settings"])


async def _get_or_create(session: AsyncSession) -> SettingsModel:
    row = (await session.execute(
        select(SettingsModel).where(SettingsModel.id == 1)
    )).scalar_one_or_none()
    if row is None:
        row = SettingsModel(id=1)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


def _to_out(row: SettingsModel) -> SettingsOut:
    return SettingsOut(
        cli_user=row.cli_user,
        snmp_community_ro=row.snmp_community_ro,
        snmp_community_rw=row.snmp_community_rw,
        default_transport=row.default_transport,
        poll_interval_state_sec=row.poll_interval_state_sec,
        poll_interval_rssi_sec=row.poll_interval_rssi_sec,
        poll_interval_ping_sec=row.poll_interval_ping_sec,
        cli_password_set=row.cli_password_enc is not None,
        updated_at=row.updated_at,
    )


@router.get("", response_model=SettingsOut)
async def get_settings(session: AsyncSession = Depends(get_session)):
    return _to_out(await _get_or_create(session))


@router.put("", response_model=SettingsOut)
async def put_settings(payload: SettingsIn, session: AsyncSession = Depends(get_session)):
    row = await _get_or_create(session)
    row.cli_user = payload.cli_user
    if payload.cli_password:                      # пустая строка = не менять
        row.cli_password_enc = encrypt(payload.cli_password)
    row.snmp_community_ro = payload.snmp_community_ro
    row.snmp_community_rw = payload.snmp_community_rw
    row.default_transport = payload.default_transport
    row.poll_interval_state_sec = payload.poll_interval_state_sec
    row.poll_interval_rssi_sec = payload.poll_interval_rssi_sec
    row.poll_interval_ping_sec = payload.poll_interval_ping_sec
    await session.commit()
    await session.refresh(row)
    logger.info(f"Настройки сохранены: user={row.cli_user}, transport={row.default_transport}")
    return _to_out(row)


class _TestIn(BaseModel):
    ip: str
    transport: str | None = None


@router.post("/test-connection", response_model=ConnectionTest)
async def test_connection(payload: _TestIn, session: AsyncSession = Depends(get_session)):
    row = await _get_or_create(session)
    transport = payload.transport or row.default_transport

    if not row.cli_user or row.cli_password_enc is None:
        return ConnectionTest(
            ip=payload.ip, transport=transport, ok=False,
            error="Не заданы логин/пароль CLI. Сохраните настройки.",
        )

    try:
        password = decrypt(row.cli_password_enc) or ""
    except Exception as e:
        return ConnectionTest(
            ip=payload.ip, transport=transport, ok=False,
            error=f"Не удалось расшифровать пароль: {e}",
        )

    ok, err = await test_cli(payload.ip, transport, row.cli_user, password)
    logger.info(f"Проверка {transport} {payload.ip}: {'OK' if ok else 'FAIL: ' + str(err)}")
    return ConnectionTest(ip=payload.ip, transport=transport, ok=ok, error=err)