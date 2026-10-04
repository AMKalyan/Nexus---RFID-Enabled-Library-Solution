import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._types import NEXUS, pg_enum, uuid_pk


class Channel(StrEnum):
    email = "email"
    sms = "sms"
    print = "print"


class OutboxStatus(StrEnum):
    queued = "queued"
    sent = "sent"
    failed = "failed"


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    channel: Mapped[Channel] = mapped_column(pg_enum(Channel, "notify_channel"))
    recipient: Mapped[str] = mapped_column(Text)
    template: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    related_type: Mapped[str | None] = mapped_column(String(30))
    related_id: Mapped[str | None] = mapped_column(String(40), index=True)
    status: Mapped[OutboxStatus] = mapped_column(
        pg_enum(OutboxStatus, "outbox_status"), default=OutboxStatus.queued
    )
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
