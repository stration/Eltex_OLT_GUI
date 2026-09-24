"""SNMP v2c через асинхронный API pysnmp 6.2.x (hlapi.asyncio)."""
import re
from loguru import logger
from pysnmp.hlapi.asyncio import (
    SnmpEngine,
    CommunityData,
    UdpTransportTarget,
    ContextData,
    ObjectType,
    ObjectIdentity,
    getCmd,
)

OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"


async def snmp_get(ip: str, community: str, oid: str, timeout: float = 1.5) -> str | None:
    """Асинхронный GET. Возвращает значение или None (ошибку пишет в DEBUG)."""
    try:
        transport = UdpTransportTarget((ip, 161), timeout=timeout, retries=1)
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),   # v2c
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if errorIndication:
            logger.debug(f"SNMP {ip} {oid}: {errorIndication}")
            return None
        if errorStatus:
            logger.debug(f"SNMP {ip} {oid}: {errorStatus.prettyPrint()}")
            return None
        for _, val in varBinds:
            return str(val)
    except Exception as e:
        logger.debug(f"SNMP {ip} {oid}: {type(e).__name__}: {e}")
    return None


async def check_olt_snmp(ip: str, community: str) -> tuple[bool, str | None, str | None]:
    """Возвращает (ok, sys_descr, error)."""
    try:
        transport = UdpTransportTarget((ip, 161), timeout=1.5, retries=1)
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),   # v2c
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(OID_SYS_DESCR)),
        )
        if errorIndication:
            return False, None, str(errorIndication)
        if errorStatus:
            return False, None, errorStatus.prettyPrint()
        for _, val in varBinds:
            return True, str(val), None
        return False, None, "пустой varBind"
    except Exception as e:
        return False, None, f"{type(e).__name__}: {e}"


import re  # положите наверху файла рядом с другими импортами


def parse_model_from_descr(descr: str | None) -> tuple[str | None, str | None]:
    """Из sysDescr вытащить модель и ревизию.

    Примеры: 'ELTEX LTP-4X:rev.B', 'Eltex LTP-8X rev.C software version ...',
             'Eltex LTP-4X rev.D ...'
    """
    if not descr:
        return None, None

    model = None
    for m in ("LTP-8X", "LTP-4X"):
        if m in descr:
            model = m
            break

    rev = None
    # Ищем 'rev.X' или 'rev.Xxx' с любым разделителем: точкой, двоеточием, пробелом.
    match = re.search(r"rev[.:\s]\s*([A-Za-z0-9]+)", descr)
    if match:
        rev = "rev." + match.group(1).upper()

    return model, rev