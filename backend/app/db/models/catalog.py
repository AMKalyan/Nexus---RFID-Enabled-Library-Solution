import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models._types import NEXUS, pg_enum, uuid_pk


class RecordSource(StrEnum):
    legacy = "legacy"
    nexus = "nexus"
    migration = "migration"


class ItemType(StrEnum):
    lending = "lending"
    reference = "reference"


class ItemStatus(StrEnum):
    available = "available"
    on_loan = "on_loan"
    missing = "missing"
    in_repair = "in_repair"
    withdrawn = "withdrawn"


class TagTarget(StrEnum):
    item = "item"
    member = "member"


class TagStatus(StrEnum):
    active = "active"
    retired = "retired"


class Bib(Base):
    __tablename__ = "bib"
    __table_args__ = (Index("ix_bib_search", "search_tsv", postgresql_using="gin"), NEXUS)

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    isbn: Mapped[str | None] = mapped_column(String(17))
    publisher: Mapped[str | None] = mapped_column(Text)
    pub_year: Mapped[int | None]
    edition: Mapped[str | None] = mapped_column(Text)
    subjects: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[RecordSource] = mapped_column(pg_enum(RecordSource, "record_source"))
    legacy_ref: Mapped[str | None] = mapped_column(String(40), index=True)
    migration_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    search_tsv: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["Item"]] = relationship(back_populates="bib")


class Shelf(Base):
    __tablename__ = "shelf"
    __table_args__ = NEXUS

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    call_no_from: Mapped[str | None] = mapped_column(String(40))
    call_no_to: Mapped[str | None] = mapped_column(String(40))


class Item(Base):
    __tablename__ = "item"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    bib_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nexus.bib.id"), index=True)
    accession_no: Mapped[str] = mapped_column(String(20), unique=True)
    barcode: Mapped[str] = mapped_column(String(32), unique=True)
    call_no: Mapped[str | None] = mapped_column(String(40))
    shelf_code: Mapped[str | None] = mapped_column(ForeignKey("nexus.shelf.code"), index=True)
    item_type: Mapped[ItemType] = mapped_column(pg_enum(ItemType, "item_type"))
    status: Mapped[ItemStatus] = mapped_column(
        pg_enum(ItemStatus, "item_status"), default=ItemStatus.available
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    acquired_on: Mapped[date | None]
    legacy_ref: Mapped[str | None] = mapped_column(String(40), index=True)
    migration_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)

    bib: Mapped[Bib] = relationship(back_populates="items")


class RfidTag(Base):
    __tablename__ = "rfid_tag"
    __table_args__ = (
        Index("uq_tag_active_item", "item_id", unique=True, postgresql_where=sa_text("status = 'active'")),
        Index(
            "uq_tag_active_member", "member_id", unique=True, postgresql_where=sa_text("status = 'active'")
        ),
        NEXUS,
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    epc: Mapped[str] = mapped_column(String(32), unique=True)
    target_type: Mapped[TagTarget] = mapped_column(pg_enum(TagTarget, "tag_target"))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nexus.item.id"))
    member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nexus.member.id"))
    security_bit: Mapped[bool] = mapped_column(default=True)
    status: Mapped[TagStatus] = mapped_column(pg_enum(TagStatus, "tag_status"), default=TagStatus.active)
    encoded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    encoded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retire_reason: Mapped[str | None] = mapped_column(Text)
