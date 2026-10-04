import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Identity, String, Text, func
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._types import NEXUS, pg_enum, uuid_pk


class BatchStatus(StrEnum):
    staged = "staged"
    validated = "validated"
    committed = "committed"
    rolled_back = "rolled_back"
    failed = "failed"


class AuditLog(Base):
    """Append-only: the application role has INSERT and SELECT only."""

    __tablename__ = "audit_log"
    __table_args__ = NEXUS

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_type: Mapped[str] = mapped_column(String(10))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=sa_text("'{}'::jsonb"))
    ip: Mapped[str | None] = mapped_column(String(45))
    correlation_id: Mapped[str | None] = mapped_column(String(64))


class AppSetting(Base):
    __tablename__ = "app_setting"
    __table_args__ = NEXUS

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict | list | str | int | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class AppVersion(Base):
    __tablename__ = "app_version"
    __table_args__ = NEXUS

    version: Mapped[str] = mapped_column(String(20), primary_key=True)
    alembic_rev: Mapped[str] = mapped_column(String(40))
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)


class MigrationBatch(Base):
    __tablename__ = "migration_batch"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    source_file: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[BatchStatus] = mapped_column(
        pg_enum(BatchStatus, "batch_status"), default=BatchStatus.staged
    )
    rows_total: Mapped[int] = mapped_column(default=0)
    rows_valid: Mapped[int] = mapped_column(default=0)
    rows_rejected: Mapped[int] = mapped_column(default=0)
    rows_duplicate: Mapped[int] = mapped_column(default=0)
    rows_committed: Mapped[int] = mapped_column(default=0)
    backup_file: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
