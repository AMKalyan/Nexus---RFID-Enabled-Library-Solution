import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Integer, LargeBinary, String, Text, func
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._types import NEXUS, pg_enum, uuid_pk


class DeviceType(StrEnum):
    staff_station = "staff_station"
    handheld = "handheld"
    gate = "gate"
    smartcard_reader = "smartcard_reader"
    printer = "printer"
    camera = "camera"


class InventoryResult(StrEnum):
    found = "found"
    misplaced = "misplaced"
    unknown = "unknown"


class Device(Base):
    __tablename__ = "device"
    __table_args__ = NEXUS

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    device_type: Mapped[DeviceType] = mapped_column(pg_enum(DeviceType, "device_type"))
    name: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=sa_text("'{}'::jsonb"))
    api_key_hash: Mapped[str] = mapped_column(String(64))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceEvent(Base):
    __tablename__ = "device_event"
    __table_args__ = NEXUS

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True)
    device_code: Mapped[str] = mapped_column(ForeignKey("nexus.device.code"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=sa_text("'{}'::jsonb"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)


class GateEvent(Base):
    __tablename__ = "gate_event"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    device_code: Mapped[str] = mapped_column(ForeignKey("nexus.device.code"))
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    epc: Mapped[str] = mapped_column(String(32))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nexus.item.id"))
    accession_no: Mapped[str | None] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(3))
    authorised: Mapped[bool]
    alarm: Mapped[bool]
    offline_decision: Mapped[bool] = mapped_column(default=False)
    photo_jpeg: Mapped[bytes | None] = mapped_column(LargeBinary)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    notified: Mapped[bool] = mapped_column(default=False)


class Footfall(Base):
    __tablename__ = "footfall"
    __table_args__ = NEXUS

    device_code: Mapped[str] = mapped_column(ForeignKey("nexus.device.code"), primary_key=True)
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    in_count: Mapped[int] = mapped_column(Integer, default=0)
    out_count: Mapped[int] = mapped_column(Integer, default=0)


class InventorySession(Base):
    __tablename__ = "inventory_session"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    shelf_code: Mapped[str] = mapped_column(ForeignKey("nexus.shelf.code"))
    device_code: Mapped[str] = mapped_column(ForeignKey("nexus.device.code"))
    started_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="open")


class InventoryRead(Base):
    __tablename__ = "inventory_read"
    __table_args__ = NEXUS

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nexus.inventory_session.id", ondelete="CASCADE"), primary_key=True
    )
    epc: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nexus.item.id"))
    result: Mapped[InventoryResult] = mapped_column(pg_enum(InventoryResult, "inventory_result"))
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Agency(Base):
    """An external system allowed to call the NCIP endpoint (e.g. a self-check kiosk or partner ILMS)."""

    __tablename__ = "agency"
    __table_args__ = NEXUS

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    api_key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
