import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._types import pg_enum


class ImportStatus(StrEnum):
    pending = "pending"
    valid = "valid"
    rejected = "rejected"
    duplicate = "duplicate"


class ImportRow(Base):
    __tablename__ = "import_row"
    __table_args__ = {"schema": "staging"}

    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    row_no: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    raw: Mapped[dict] = mapped_column(JSONB)
    accession_no: Mapped[str | None] = mapped_column(String(40))
    barcode: Mapped[str | None] = mapped_column(String(40))
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    isbn: Mapped[str | None] = mapped_column(String(20))
    publisher: Mapped[str | None] = mapped_column(Text)
    pub_year: Mapped[int | None]
    edition: Mapped[str | None] = mapped_column(Text)
    subjects: Mapped[str | None] = mapped_column(Text)
    call_no: Mapped[str | None] = mapped_column(String(40))
    shelf_code: Mapped[str | None] = mapped_column(String(20))
    item_type: Mapped[str | None] = mapped_column(String(20))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    acquired_on: Mapped[date | None]
    status: Mapped[ImportStatus] = mapped_column(
        pg_enum(ImportStatus, "import_status", schema="staging"), default=ImportStatus.pending
    )
    reasons: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    duplicate_of: Mapped[str | None] = mapped_column(String(40))
