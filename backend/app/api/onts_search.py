"""API: глобальный поиск ONT по всем OLT.

Поиск по serial / description / equipment_id, case-insensitive.
Данные берутся из БД (ONT-поллер их регулярно обновляет),
никаких SNMP/CLI не дёргаем.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Olt, Ont


router = APIRouter(prefix="/api/onts", tags=["onts-search"])


@router.get("/search")
async def global_search(
    q: str = Query(..., min_length=2, description="Строка поиска (мин. 2 символа)"),
    limit: int = Query(200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    """
    Глобальный поиск ONT по всем OLT.

    Ищет подстроку `q` (case-insensitive) в:
      - serial
      - description
      - equipment_id

    Возвращает первые `limit` совпадений + общее количество найденных.
    Сортировка — по имени OLT, затем по gpon_port и ont_id.
    """
    needle = f"%{q.strip().lower()}%"

    stmt = (
        select(Ont, Olt)
        .join(Olt, Olt.id == Ont.olt_id)
        .where(
            or_(
                func.lower(Ont.serial).like(needle),
                func.lower(Ont.description).like(needle),
                func.lower(Ont.equipment_id).like(needle),
            )
        )
        .order_by(Olt.name, Ont.gpon_port, Ont.ont_id)
    )

    rows = (await session.execute(stmt)).all()
    total = len(rows)
    rows = rows[:limit]

    items = [
        {
            "olt_id": olt.id,
            "olt_name": olt.name or olt.ip,
            "olt_ip": olt.ip,
            "gpon_port": ont.gpon_port,
            "ont_id": ont.ont_id,
            "serial": ont.serial,
            "status": ont.status,
            "rssi_db": ont.rssi_db,
            "version": ont.version,
            "equipment_id": ont.equipment_id,
            "description": ont.description,
            "last_seen_at": ont.last_seen_at.isoformat() if ont.last_seen_at else None,
        }
        for ont, olt in rows
    ]

    return {"items": items, "total": total, "limit": limit}