import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.base import get_session
from app.db.models import Member, MemberStatus, Role, RolePermission, StaffUser


@dataclass(frozen=True)
class Principal:
    typ: str
    id: uuid.UUID
    role: str
    permissions: frozenset[str]


def _unauthenticated() -> AppError:
    return AppError("ERR_UNAUTHENTICATED", "Authentication required", 401)


def permissions_for_role(session: Session, role_name: str) -> frozenset[str]:
    query = (
        select(RolePermission.permission_code)
        .join(Role, Role.id == RolePermission.role_id)
        .where(Role.name == role_name)
    )
    return frozenset(session.scalars(query))


def get_principal(request: Request, session: Session = Depends(get_session)) -> Principal:
    """Resolve the caller from the bearer token. Role and permissions are re-read on every request."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise _unauthenticated()
    return principal_from_token(session, header[7:])


def principal_from_token(session: Session, token: str) -> Principal:
    claims = decode_access_token(token)
    try:
        sub = uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise _unauthenticated() from exc

    if claims["typ"] == "staff":
        user = session.get(StaffUser, sub)
        if user is None or not user.is_active:
            raise _unauthenticated()
        role = session.get(Role, user.role_id)
        role_name = role.name if role else ""
    elif claims["typ"] == "patron":
        member = session.get(Member, sub)
        if member is None or member.status == MemberStatus.expired:
            raise _unauthenticated()
        role_name = "Patron"
    else:
        raise _unauthenticated()
    return Principal(claims["typ"], sub, role_name, permissions_for_role(session, role_name))


def require(permission: str) -> Callable[..., Principal]:
    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if permission not in principal.permissions:
            raise AppError("ERR_FORBIDDEN", "Not permitted", 403)
        return principal

    return dependency


def ensure_self_or(principal: Principal, member_id: uuid.UUID, permission: str) -> None:
    """IDOR guard: patrons may act on their own record; staff need the permission."""
    if principal.typ == "patron" and principal.id == member_id:
        return
    if permission in principal.permissions:
        return
    raise AppError("ERR_FORBIDDEN", "Not permitted", 403)
