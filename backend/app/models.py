from datetime import datetime
from sqlalchemy import String, Integer, DateTime, LargeBinary, ForeignKey, Text, UniqueConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Settings(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    cli_user: Mapped[str | None] = mapped_column(String(64))
    cli_password_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    snmp_community_ro: Mapped[str] = mapped_column(String(64), default="public")
    snmp_community_rw: Mapped[str | None] = mapped_column(String(64))
    default_transport: Mapped[str] = mapped_column(String(8), default="telnet")
    poll_interval_state_sec: Mapped[int] = mapped_column(Integer, default=15)
    poll_interval_rssi_sec: Mapped[int] = mapped_column(Integer, default=60)
    poll_interval_ping_sec: Mapped[int] = mapped_column(Integer, default=60)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Olt(Base):
    __tablename__ = "olts"
    id: Mapped[int] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(String(45), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(16))
    hw_revision: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    last_ping_ms: Mapped[int | None] = mapped_column(Integer)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ports: Mapped[list["GponPort"]] = relationship(back_populates="olt", cascade="all,delete-orphan")


class GponPort(Base):
    __tablename__ = "gpon_ports"
    __table_args__ = (UniqueConstraint("olt_id", "port", name="uq_olt_port"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"), index=True)
    port: Mapped[int] = mapped_column(Integer)
    state: Mapped[str | None] = mapped_column(String(16))
    sfp_vendor: Mapped[str | None] = mapped_column(String(64))
    sfp_part: Mapped[str | None] = mapped_column(String(64))
    sfp_revision: Mapped[str | None] = mapped_column(String(32))
    rx_power: Mapped[float | None]
    tx_power: Mapped[float | None]
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    olt: Mapped[Olt] = relationship(back_populates="ports")


# ---- ONT и история RSSI -------------------------------------------------

class Ont(Base):
    __tablename__ = "onts"
    __table_args__ = (
        UniqueConstraint("olt_id", "gpon_port", "ont_id", name="uq_olt_port_ont"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(
        ForeignKey("olts.id", ondelete="CASCADE"), index=True
    )
    gpon_port: Mapped[int] = mapped_column(Integer)
    ont_id: Mapped[int] = mapped_column(Integer)
    serial: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16))
    rssi_db: Mapped[float | None]
    version: Mapped[str | None] = mapped_column(String(32))
    equipment_id: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(128))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RssiHistory(Base):
    __tablename__ = "rssi_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    ont_pk: Mapped[int] = mapped_column(
        ForeignKey("onts.id", ondelete="CASCADE"), index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    rssi_db: Mapped[float]


# ---- SNMP-кэш портов и MAC-адресов --------------------------------------

class OntPortCache(Base):
    __tablename__ = "ont_ports_cache"
    __table_args__ = (
        UniqueConstraint("olt_id", "serial", "port_id", name="uq_port_cache"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(
        ForeignKey("olts.id", ondelete="CASCADE"), index=True
    )
    serial: Mapped[str] = mapped_column(String(32), index=True)
    port_id: Mapped[int] = mapped_column(Integer)
    link: Mapped[str | None] = mapped_column(String(8))
    speed: Mapped[str | None] = mapped_column(String(8))
    duplex: Mapped[str | None] = mapped_column(String(8))
    poe_state: Mapped[str | None] = mapped_column(String(8))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class OntMacCache(Base):
    __tablename__ = "ont_macs_cache"
    __table_args__ = (
        UniqueConstraint("olt_id", "serial", "mac", name="uq_mac_cache"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(
        ForeignKey("olts.id", ondelete="CASCADE"), index=True
    )
    serial: Mapped[str] = mapped_column(String(32), index=True)
    mac: Mapped[str] = mapped_column(String(32))
    gem: Mapped[int | None] = mapped_column(Integer)
    uvid: Mapped[int | None] = mapped_column(Integer)
    cvid: Mapped[int | None] = mapped_column(Integer)
    svid: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---- Кэш конфигурации ONT (общие параметры) ------------------------------

class OntConfigCache(Base):
    """
    Кэш общих параметров ONT, полученных через SNMP (этап 1).
    Хранит JSON со всеми общими параметрами + время обновления.
    Сервисы (cross-connect, dba, custom, selective-tunnel) — пока не входят,
    они будут добавлены на этапе 2.
    """
    __tablename__ = "ont_config_cache"
    __table_args__ = (
        UniqueConstraint("olt_id", "serial", name="uq_ont_config_cache"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(
        ForeignKey("olts.id", ondelete="CASCADE"), index=True
    )
    serial: Mapped[str] = mapped_column(String(32), index=True)
    config_json: Mapped[str] = mapped_column(Text)   # JSON-строка
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )