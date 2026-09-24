"""Диагностика: SNMP-данные сервисов для конкретной ONT."""
import asyncio
from app.services.snmp_ont import (
    snmp_walk_all_full_services,
    snmp_walk_all_custom_cc,
    snmp_walk_all_selective_tunnels,
    snmp_fetch_profile_names,
)
from app.services.ont_config_poller import _build_services

IP = "10.10.1.105"
COMMUNITY = "public"

# ELTX890DD7BC → 'ELTX890DD7' (обрезанный)
SERIAL_KEY = "ELTX890DD7"


async def main():
    print(f"=== Probe для {SERIAL_KEY} на {IP} ===\n")

    # Профили
    profile_names = await snmp_fetch_profile_names(IP, COMMUNITY)
    print("Справочники профилей:")
    for ptype, names in profile_names.items():
        print(f"  {ptype}: {names}")
    print()

    # FullServices
    fs_all = await snmp_walk_all_full_services(IP, COMMUNITY)
    fs = fs_all.get(SERIAL_KEY, {})
    print(f"FullServices для {SERIAL_KEY}: {len(fs)} сервисов")
    for sid in sorted(fs.keys()):
        print(f"  snmp_id={sid} (cli_id={sid-1}): {fs[sid]}")
    print()

    # CustomCC
    cc_all = await snmp_walk_all_custom_cc(IP, COMMUNITY)
    cc = cc_all.get(SERIAL_KEY, {})
    print(f"CustomCC для {SERIAL_KEY}: {len(cc)} записей")
    for cid in sorted(cc.keys())[:5]:
        print(f"  custom_id={cid}: {cc[cid]}")
    print()

    # SelectiveTunnel
    st_all = await snmp_walk_all_selective_tunnels(IP, COMMUNITY)
    st = st_all.get(SERIAL_KEY, {})
    print(f"SelectiveTunnel для {SERIAL_KEY}: {len(st)} сервисов")
    for sid in sorted(st.keys())[:5]:
        print(f"  service_id={sid}: {st[sid]}")
    print()

    # Сборка сервисов
    services = _build_services(
        full_services=fs,
        custom_cc=cc,
        selective=st,
        profile_names=profile_names,
    )
    print(f"=== Собранные сервисы: {len(services)} ===")
    for svc in services:
        print(f"  Service [{svc['service_id']}]: "
              f"CC={svc['profile_cross_connect']!r} "
              f"DBA={svc['profile_dba']!r} "
              f"custom={svc['custom_cross_connect']!r} "
              f"uvid={svc['selective_tunnel_uvid']!r}")


asyncio.run(main())