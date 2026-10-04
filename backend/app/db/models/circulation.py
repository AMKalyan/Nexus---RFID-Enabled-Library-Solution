import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, func
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models._types import NEXUS, pg_enum, uuid_pk
from app.db.models.catalog import Item
from app.db.models.members import Member


class LoanChannel(StrEnum):
    ui = "ui"
    ncip = "ncip"
    sip2 = "sip2"


class FineReason(StrEnum):
    overdue = "overdue"
    lost = "lost"
    damage = "damage"
    manual = "manual"


class FineStatus(StrEnum):
    open = "open"
    paid = "paid"
    waived = "waived"


class Loan(Base):
    __tablename__ = "loan"
    __table_args__ = (
        Index("uq_loan_open_item", "item_id", unique=True, postgresql_where=sa_text("returned_at IS NULL")),
        Index("ix_loan_member_open", "member_id", "returned_at"),
        NEXUS,
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nexus.item.id"))
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nexus.member.id"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renew_count: Mapped[int] = mapped_column(default=0)
    channel: Mapped[LoanChannel] = mapped_column(pg_enum(LoanChannel, "loan_channel"))
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    returned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    item: Mapped[Item] = relationship()
    member: Mapped[Member] = relationship()


class Fine(Base):
    __tablename__ = "fine"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nexus.member.id"), index=True)
    loan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nexus.loan.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reason: Mapped[FineReason] = mapped_column(pg_enum(FineReason, "fine_reason"))
    status: Mapped[FineStatus] = mapped_column(pg_enum(FineStatus, "fine_status"), default=FineStatus.open)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
