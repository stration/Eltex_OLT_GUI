from datetime import datetime
from pydantic import BaseModel, Field, IPvAnyAddress


class SettingsIn(BaseModel):
    cli_user: str | None = None
    cli_password: str | None = None
    snmp_community_ro: str = "public"
    snmp_community_rw: str | None = None
    default_transport: str = Field("telnet", pattern="^(ssh|telnet)$")
    poll_interval_state_sec: int = 15
    poll_interval_rssi_sec: int = 60
    poll_interval_ping_sec: int = 60


class SettingsOut(BaseModel):
    cli_user: str | None
    snmp_community_ro: str
    snmp_community_rw: str | None
    default_transport: str
    poll_interval_state_sec: int
    poll_interval_rssi_sec: int
    poll_interval_ping_sec: int
    cli_password_set: bool
    updated_at: datetime | None


class OltIn(BaseModel):
    ip: IPvAnyAddress
    name: str | None = None
    notes: str | None = None


class OltPatch(BaseModel):
    name: str | None = None
    notes: str | None = None


class OltOut(BaseModel):
    id: int
    ip: str
    name: str | None
    model: str | None
    hw_revision: str | None
    status: str
    last_ping_ms: int | None
    last_seen_at: datetime | None
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class CheckResult(BaseModel):
    ip: str
    ping_ok: bool
    ping_ms: int | None
    snmp_ok: bool
    snmp_error: str | None = None
    model: str | None = None
    hw_revision: str | None = None


class ConnectionTest(BaseModel):
    ip: str
    transport: str
    ok: bool
    error: str | None = None
class GponPortState(BaseModel):
    gpon_port: int
    state: str
    state_num: int | None = None
    ont_count: int | None = None
    sfp_vendor: str | None = None
    sfp_product_number: str | None = None
    sfp_revision: str | None = None
    tx_power_dbm: float | None = None
    temperature_c: int | None = None
    voltage_v: float | None = None
    tx_bias_ma: float | None = None

class OltPsuInfo(BaseModel):
    index: int
    name: str | None = None
    type: str | None = None            # "AC" | "DC" | None
    intact: bool | None = None


class OltSystemInfo(BaseModel):
    uptime_sec: int | None = None
    firmware_rev: str | None = None
    hardware_rev: str | None = None
    mac: str | None = None

    cpu_load_1m: int | None = None
    cpu_load_5m: int | None = None
    cpu_load_15m: int | None = None

    ram_free_bytes: int | None = None
    disk_free_kb: int | None = None

    fan0_rpm: int | None = None
    fan1_rpm: int | None = None
    sensor1_temp: int | None = None
    sensor2_temp: int | None = None

    psu: list[OltPsuInfo] = []