import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._types import NEXUS, pg_enum, uuid_pk


class MemberStatus(StrEnum):
    active = "active"
    blocked = "blocked"
    expired = "expired"


class CircPolicy(Base):
    __tablename__ = "circ_policy"
    __table_args__ = NEXUS

    category_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    loan_days: Mapped[int]
    max_items: Mapped[int]
    max_renewals: Mapped[int]
    fine_per_day: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    fine_limit: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    can_borrow_reference: Mapped[bool] = mapped_column(default=False)


class Member(Base):
    __tablename__ = "member"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    card_no: Mapped[str] = mapped_column(String(20), unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    category_code: Mapped[str] = mapped_column(ForeignKey("nexus.circ_policy.category_code"))
    status: Mapped[MemberStatus] = mapped_column(
        pg_enum(MemberStatus, "member_status"), default=MemberStatus.active
    )
    block_reason: Mapped[str | None] = mapped_column(Text)
    smartcard_uid: Mapped[str | None] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    notify_email: Mapped[bool] = mapped_column(default=True)
    notify_sms: Mapped[bool] = mapped_column(default=False)
    notify_print: Mapped[bool] = mapped_column(default=False)
    legacy_ref: Mapped[str | None] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
