import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    DUMMY_HASH,
    Typ,
    create_access_token,
    issue_refresh_token,
    verify_password,
)
from app.db.models import Member, MemberStatus, Role, StaffUser


def _invalid() -> AppError:
    return AppError("INVALID_CREDENTIALS", "Invalid username or password", 401)


def authenticate_password(session: Session, username: str, password: str) -> tuple[Typ, uuid.UUID, str]:
    """Staff log in with their username, patrons with their card number."""
    user = session.scalar(select(StaffUser).where(StaffUser.username == username))
    if user is not None:
        if not (verify_password(user.password_hash, password) and user.is_active):
            raise _invalid()
        user.last_login_at = datetime.now(UTC)
        role = session.get(Role, user.role_id)
        return "staff", user.id, role.name if role else ""

    member = session.scalar(select(Member).where(Member.card_no == username))
    if member is None or member.password_hash is None:
        verify_password(DUMMY_HASH, password)
        raise _invalid()
    if not verify_password(member.password_hash, password) or member.status == MemberStatus.expired:
        raise _invalid()
    return "patron", member.id, "Patron"


def token_response(sub: uuid.UUID, typ: Typ, role: str, refresh_token: str) -> dict:
    return {
        "access_token": create_access_token(sub, typ, role),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": get_settings().access_token_minutes * 60,
    }


def issue_tokens(session: Session, typ: Typ, sub: uuid.UUID, role: str) -> dict:
    return token_response(sub, typ, role, issue_refresh_token(session, typ, sub))


def role_of(session: Session, typ: Typ, sub: uuid.UUID) -> str:
    if typ == "patron":
        return "Patron"
    user = session.get(StaffUser, sub)
    if user is None or not user.is_active:
        raise AppError("ERR_TOKEN_INVALID", "Invalid or expired token", 401)
    role = session.get(Role, user.role_id)
    return role.name if role else ""
