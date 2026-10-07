"""User, role and setting administration (FR 11)."""

import re
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import AppError
from app.core.security import hash_password
from app.db.models import AppSetting, AuditLog, Role, RolePermission, StaffUser
from app.schemas.admin import AuditOut, AuditPage, RoleOut, UserIn, UserOut, UserPatch
from app.services.common import Actor

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _email_list(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > 20
        or not all(isinstance(v, str) and _EMAIL.match(v) for v in value)
    ):
        raise ValueError
    return value


def _short_text(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError
    return value


def _flag(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError
    return value


# Only these settings exist; each has a validator for its value.
SETTINGS = {
    "gate_alert_recipients": _email_list,
    "library_name": _short_text,
    "ui_banner": _short_text,
    "maintenance_notice": _short_text,
    "overdue_notices_enabled": _flag,
}


class AdminService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- users ---

    def _role_id(self, name: str) -> uuid.UUID:
        role_id = self.session.scalar(select(Role.id).where(Role.name == name, Role.name != "Patron"))
        if role_id is None:
            raise AppError("ROLE_UNKNOWN", "Unknown staff role", 422)
        return role_id

    def user_out(self, user: StaffUser) -> UserOut:
        role = self.session.get(Role, user.role_id)
        return UserOut(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            email=user.email,
            role=role.name if role else "",
            is_active=user.is_active,
            has_smartcard=user.smartcard_uid is not None,
            last_login_at=user.last_login_at,
        )

    def list_users(self) -> list[UserOut]:
        return [
            self.user_out(u) for u in self.session.scalars(select(StaffUser).order_by(StaffUser.username))
        ]

    def _check_card(self, uid: str | None, exclude: uuid.UUID | None = None) -> str | None:
        if uid is None:
            return None
        uid = uid.upper()
        clash = self.session.scalar(select(StaffUser.id).where(StaffUser.smartcard_uid == uid))
        if clash and clash != exclude:
            raise AppError("CARD_IN_USE", "Smart card already assigned", 409)
        return uid

    def create_user(self, data: UserIn, actor: Actor) -> UserOut:
        if self.session.scalar(select(StaffUser.id).where(StaffUser.username == data.username)):
            raise AppError("USERNAME_EXISTS", "Username already exists", 409)
        user = StaffUser(
            username=data.username,
            display_name=data.display_name,
            email=data.email,
            password_hash=hash_password(data.password),
            role_id=self._role_id(data.role),
            smartcard_uid=self._check_card(data.smartcard_uid),
        )
        self.session.add(user)
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="user.create",
            entity_type="staff_user",
            entity_id=str(user.id),
            details={"role": data.role},
            ip=actor.ip,
        )
        return self.user_out(user)

    def update_user(self, user_id: uuid.UUID, data: UserPatch, actor: Actor) -> UserOut:
        user = self.session.get(StaffUser, user_id)
        if user is None:
            raise AppError("USER_NOT_FOUND", "User not found", 404)
        changes = data.model_dump(exclude_unset=True)
        if "role" in changes:
            user.role_id = self._role_id(changes["role"])
        if changes.get("password"):
            user.password_hash = hash_password(changes["password"])
        if "smartcard_uid" in changes:
            user.smartcard_uid = self._check_card(changes["smartcard_uid"], exclude=user.id)
        for field in ("display_name", "email", "is_active"):
            if field in changes:
                setattr(user, field, changes[field])
        self.session.flush()
        fields = sorted(k for k in changes if k != "password") + (
            ["password"] if "password" in changes else []
        )
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="user.update",
            entity_type="staff_user",
            entity_id=str(user.id),
            details={"fields": fields, "role": changes.get("role")},
            ip=actor.ip,
        )
        return self.user_out(user)

    # --- roles ---

    def roles(self) -> list[RoleOut]:
        rows = self.session.execute(
            select(Role.name, RolePermission.permission_code)
            .outerjoin(RolePermission, RolePermission.role_id == Role.id)
            .order_by(Role.name, RolePermission.permission_code)
        ).all()
        grouped: dict[str, list[str]] = {}
        for name, code in rows:
            grouped.setdefault(name, [])
            if code:
                grouped[name].append(code)
        return [RoleOut(name=n, permissions=p) for n, p in grouped.items()]

    # --- settings ---

    def settings(self) -> dict[str, Any]:
        stored = {s.key: s.value for s in self.session.scalars(select(AppSetting))}
        return {key: stored.get(key) for key in SETTINGS}

    def put_setting(self, key: str, value: Any, actor: Actor) -> dict[str, Any]:
        validator = SETTINGS.get(key)
        if validator is None:
            raise AppError("SETTING_UNKNOWN", "Unknown setting", 422)
        try:
            value = validator(value)
        except ValueError as exc:
            raise AppError("SETTING_INVALID", "Invalid value for setting", 422) from exc
        row = self.session.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key)
            self.session.add(row)
        row.value, row.updated_by, row.updated_at = value, actor.id, datetime.now(UTC)
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="setting.update",
            entity_type="setting",
            entity_id=key,
            ip=actor.ip,
        )
        return {key: value}

    # --- audit log ---

    def audit_page(
        self,
        *,
        actor_id: uuid.UUID | None,
        action: str | None,
        entity_id: str | None,
        date_from: date | None,
        date_to: date | None,
        page: int,
        size: int,
    ) -> AuditPage:
        q = select(AuditLog)
        if actor_id:
            q = q.where(AuditLog.actor_id == actor_id)
        if action:
            q = q.where(AuditLog.action.startswith(action))
        if entity_id:
            q = q.where(AuditLog.entity_id == entity_id)
        if date_from:
            q = q.where(AuditLog.occurred_at >= datetime.combine(date_from, time.min, UTC))
        if date_to:
            q = q.where(AuditLog.occurred_at < datetime.combine(date_to + timedelta(days=1), time.min, UTC))
        total = self.session.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = self.session.scalars(q.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size))
        return AuditPage(total=total, page=page, size=size, items=[AuditOut.model_validate(r) for r in rows])
