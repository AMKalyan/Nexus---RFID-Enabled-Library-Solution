import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import RefreshToken, SubjectType

Typ = Literal["staff", "patron"]

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
# Verified against when a username does not exist, so both paths cost the same time.
DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(sub: uuid.UUID, typ: Typ, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(sub),
        "typ": typ,
        "role": role,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "typ"]},
        )
    except jwt.PyJWTError as exc:
        raise AppError("ERR_TOKEN_INVALID", "Invalid or expired token", 401) from exc


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_refresh_token(
    session: Session, typ: Typ, sub: uuid.UUID, family_id: uuid.UUID | None = None
) -> str:
    raw = secrets.token_urlsafe(32)
    session.add(
        RefreshToken(
            family_id=family_id or uuid.uuid4(),
            subject_type=SubjectType(typ),
            subject_id=sub,
            token_hash=_digest(raw),
            expires_at=datetime.now(UTC) + timedelta(hours=get_settings().refresh_token_hours),
        )
    )
    return raw


def rotate_refresh_token(session: Session, raw: str) -> tuple[Typ, uuid.UUID, str]:
    """Exchange a refresh token for a new one. Reusing a spent token revokes its whole family."""
    row = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _digest(raw)))
    now = datetime.now(UTC)
    if row is None or row.expires_at < now:
        raise AppError("ERR_TOKEN_INVALID", "Invalid or expired token", 401)
    if row.revoked_at is not None:
        session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        session.commit()
        raise AppError("ERR_TOKEN_REUSED", "Token reuse detected", 401)
    row.revoked_at = now
    typ: Typ = row.subject_type.value  # type: ignore[assignment]
    return typ, row.subject_id, issue_refresh_token(session, typ, row.subject_id, row.family_id)


def revoke_refresh_token(session: Session, raw: str) -> None:
    row = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _digest(raw)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
