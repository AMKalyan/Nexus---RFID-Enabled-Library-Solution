import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models._types import NEXUS, pg_enum, uuid_pk


class SubjectType(StrEnum):
    staff = "staff"
    patron = "patron"


class Role(Base):
    __tablename__ = "role"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(40), unique=True)


class Permission(Base):
    __tablename__ = "permission"
    __table_args__ = NEXUS

    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)


class RolePermission(Base):
    __tablename__ = "role_permission"
    __table_args__ = NEXUS

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nexus.role.id", ondelete="CASCADE"), primary_key=True
    )
    permission_code: Mapped[str] = mapped_column(
        ForeignKey("nexus.permission.code", ondelete="CASCADE"), primary_key=True
    )


class StaffUser(Base):
    __tablename__ = "staff_user"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    smartcard_uid: Mapped[str | None] = mapped_column(String(32), unique=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nexus.role.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    __tablename__ = "refresh_token"
    __table_args__ = NEXUS

    id: Mapped[uuid.UUID] = uuid_pk()
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    subject_type: Mapped[SubjectType] = mapped_column(pg_enum(SubjectType, "subject_type"))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
