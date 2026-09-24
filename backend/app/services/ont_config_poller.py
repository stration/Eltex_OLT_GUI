"""Периодический поллер конфигурации ONT через SNMP.

Раз в 15 минут:
1. Справочники профилей (index → name).
2. Общие параметры ONT (ltp8xONTConfigTable).
3. Сервисы: FullServices + CustomCrossConnect + SelectiveTunnel.
4. Сохраняет собранный JSON в ont_config_cache.

Важные соглашения:
- SNMP-таблицы сервисов (FullServices, CustomCrossConnect, SelectiveTunnel)
  используют 1-based индексацию service_id. CLI показывает 0-based (Service [0]).
  При сборке списка сервисов делаем сдвиг: cli_id = snmp_id - 1.
- Индексы профилей CC/DBA и в SNMP FullServices, и в справочниках
  ltp8xONT*ProfileTable совпадают (оба 0-based). Сдвиг не нужен.
"""
import asyncio
import json
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Olt, Ont, Settings as SettingsModel, OntConfigCache
from .snmp_ont import (
    snmp_walk_all_configs,
    snmp_walk_all_full_services,
    snmp_walk_all_custom_cc,
    snmp_walk_all_selective_tunnels,
    snmp_fetch_profile_names,
    config_from_raw,
)


async def _load_cfg(session: AsyncSession) -> SettingsModel | None:
    return (await session.execute(
        select(SettingsModel).where(SettingsModel.id == 1)
    )).scalar_one_or_none()


def _resolve_name_shifted(names: dict[int, str], idx: int | None) -> str | None:
    """
    Индексы профилей в SNMP-таблицах ltp8xONT*ProfileTable совпадают
    с индексами в SNMP FullServices (0-based).
    Справочник читаем как есть, без сдвига.
    """
    if idx is None:
        return None
    return names.get(idx)


def _build_services(
    full_services: dict[int, dict],
    custom_cc: dict[int, dict],
    selective: dict[int, list[int]],
    profile_names: dict[str, dict[int, str]],
) -> list[dict]:
    """
    Собирает список сервисов. На входе SNMP-индексы (1-based),
    на выходе cli_service_id (0-based).

    Все три таблицы (FullServices, CustomCC, SelectiveTunnel)
    используют один и тот же 1-based snmp_id.
    """
    cc_names = profile_names.get("cross-connect", {})
    dba_names = profile_names.get("dba", {})

    # Все snmp_id, упомянутые хотя бы в одной таблице
    all_ids: set[int] = set()
    all_ids.update(full_services.keys())
    all_ids.update(selective.keys())
    all_ids.update(custom_cc.keys())

    if not all_ids:
        all_ids = {1}

    services: list[dict] = []
    for snmp_id in sorted(all_ids):
        cli_id = snmp_id - 1
        if cli_id < 0:
            continue

        svc_full = full_services.get(snmp_id, {})
        cc_idx = svc_full.get("cc_idx")
        dba_idx = svc_full.get("dba_idx")

        # Custom — тот же snmp_id, без сдвига
        custom = custom_cc.get(snmp_id, {}) or {}
        custom_enabled = custom.get("enabled", "disabled")
        custom_cvid = custom.get("cvid") if custom_enabled == "enabled" else None
        custom_svid = custom.get("svid") if custom_enabled == "enabled" else None
        custom_cos = custom.get("cos") if custom_enabled == "enabled" else None

        # Selective-tunnel — тот же snmp_id
        uvids = selective.get(snmp_id)
        uvid_str = ",".join(str(u) for u in sorted(uvids)) if uvids else None

        cc_name = _resolve_name_shifted(cc_names, cc_idx)
        dba_name = _resolve_name_shifted(dba_names, dba_idx)

        services.append({
            "service_id": cli_id,
            "profile_cross_connect": cc_name,
            "profile_dba": dba_name,
            "custom_cross_connect": custom_enabled,
            "custom_cvid": custom_cvid,
            "custom_svid": custom_svid,
            "custom_cos": custom_cos,
            "selective_tunnel_uvid": uvid_str,
        })

    return services


async def poll_one_olt(session: AsyncSession, olt_id: int) -> dict:
    olt = await session.get(Olt, olt_id)
    if olt is None:
        return {"configs_updated": 0, "error": "OLT не найден"}

    cfg = await _load_cfg(session)
    if cfg is None:
        return {"configs_updated": 0, "error": "Настройки не заданы"}

    onts = (await session.execute(
        select(Ont).where(Ont.olt_id == olt_id)
    )).scalars().all()
    if not onts:
        return {"configs_updated": 0, "error": None}

    serials = [o.serial for o in onts if o.serial]
    if not serials:
        return {"configs_updated": 0, "error": None}

    community = cfg.snmp_community_ro

    # 1. Справочники профилей
    try:
        profile_names = await snmp_fetch_profile_names(olt.ip, community)
    except Exception as e:
        logger.exception(f"poll config: profiles {olt.ip}: {e}")
        profile_names = {}

    logger.debug(
        f"poll config {olt.ip}: справочники "
        f"{ {k: len(v) for k, v in profile_names.items()} }"
    )

    # 2. Общие параметры
    try:
        raw_by_serial = await snmp_walk_all_configs(olt.ip, community)
    except Exception as e:
        logger.exception(f"poll config: configs {olt.ip}: {e}")
        return {"configs_updated": 0, "error": str(e)}

    # 3. FullServices
    try:
        full_services = await snmp_walk_all_full_services(olt.ip, community)
    except Exception as e:
        logger.warning(f"poll config: full_services {olt.ip}: {e}")
        full_services = {}

    # 4. CustomCrossConnect
    try:
        custom_cc = await snmp_walk_all_custom_cc(olt.ip, community)
    except Exception as e:
        logger.warning(f"poll config: custom_cc {olt.ip}: {e}")
        custom_cc = {}

    # 5. SelectiveTunnel
    try:
        selective = await snmp_walk_all_selective_tunnels(olt.ip, community)
    except Exception as e:
        logger.warning(f"poll config: selective {olt.ip}: {e}")
        selective = {}

    # Диагностика: сколько сервисов нашли для первых нескольких ONT
    for sample_key in list(raw_by_serial.keys())[:3]:
        fs = full_services.get(sample_key, {})
        ccc = custom_cc.get(sample_key, {})
        st = selective.get(sample_key, {})
        logger.debug(
            f"poll config {olt.ip} sample {sample_key}: "
            f"full_services={len(fs)} custom_cc={len(ccc)} selective={len(st)}"
        )

    # Сопоставление
    updated = 0
    skipped_ambiguous = 0

    for human_key, raw in raw_by_serial.items():
        candidates = [s for s in serials if s.startswith(human_key)]
        if not candidates:
            continue
        if len(candidates) > 1:
            skipped_ambiguous += len(candidates)
            continue

        matched_serial = candidates[0]
        parsed = config_from_raw(raw)

        # Имена профилей верхнего уровня (0-based, без сдвига)
        cc_names = profile_names.get("cross-connect", {})
        pt_names = profile_names.get("ports", {})
        mg_names = profile_names.get("management", {})
        sh_names = profile_names.get("shaping", {})
        vo_names = profile_names.get("voice", {})

        parsed["profile_cross_connect_name"] = cc_names.get(parsed.get("profile_cc_idx_0"))
        parsed["profile_ports_name"] = pt_names.get(parsed.get("profile_ports_idx"))
        parsed["profile_management_name"] = mg_names.get(parsed.get("profile_management_idx"))
        parsed["profile_shaping_name"] = sh_names.get(parsed.get("profile_shaping_idx"))
        parsed["profile_voice_name"] = vo_names.get(parsed.get("profile_voice_idx"))

        # Сервисы
        parsed["services"] = _build_services(
            full_services=full_services.get(human_key, {}),
            custom_cc=custom_cc.get(human_key, {}),
            selective=selective.get(human_key, {}),
            profile_names=profile_names,
        )

        await _replace_config(session, olt_id, matched_serial, parsed)
        updated += 1

    await session.commit()

    if skipped_ambiguous:
        logger.info(
            f"poll config {olt.ip}: обновлено {updated} ONT, "
            f"пропущено {skipped_ambiguous} (неоднозначные префиксы)"
        )
    else:
        logger.info(f"poll config {olt.ip}: обновлено {updated} ONT")

    return {"configs_updated": updated, "error": None}


async def _replace_config(
    session: AsyncSession, olt_id: int, serial: str, data: dict,
):
    await session.execute(
        delete(OntConfigCache).where(
            OntConfigCache.olt_id == olt_id,
            OntConfigCache.serial == serial,
        )
    )
    session.add(OntConfigCache(
        olt_id=olt_id,
        serial=serial,
        config_json=json.dumps(data, ensure_ascii=False, default=str),
    ))


async def poll_all(session_maker, concurrency: int = 1) -> dict:
    async with session_maker() as session:
        olts = (await session.execute(select(Olt))).scalars().all()
        olt_ids = [o.id for o in olts]

    if not olt_ids:
        return {}

    sem = asyncio.Semaphore(concurrency)

    async def one(olt_id: int):
        async with sem:
            try:
                async with session_maker() as session:
                    return olt_id, await poll_one_olt(session, olt_id)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"ont_config_poller one {olt_id}: {e}")
                return olt_id, {"configs_updated": 0, "error": str(e)}

    results = await asyncio.gather(*(one(i) for i in olt_ids))
    results = [r for r in results if r is not None]
    total = sum(r[1].get("configs_updated", 0) for r in results)
    if total:
        logger.info(f"Config-поллер: обновлено для {total} ONT")
    return dict(results)