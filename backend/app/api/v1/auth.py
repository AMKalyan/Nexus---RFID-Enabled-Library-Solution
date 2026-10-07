from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.auth import Principal, get_principal
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.core.security import revoke_refresh_token, rotate_refresh_token
from app.db.base import get_session
from app.services.users import authenticate_password, issue_tokens, role_of, token_response

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=20, max_length=128)


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class MeOut(BaseModel):
    id: str
    typ: str
    role: str
    permissions: list[str]


@router.post("/login", response_model=TokensOut)
@limiter.limit(get_settings().rate_limit_auth)
def login(request: Request, body: LoginIn, session: Session = Depends(get_session)) -> dict:
    ip = request.client.host if request.client else None
    try:
        typ, sub, role = authenticate_password(session, body.username, body.password)
    except AppError:
        session.rollback()
        # Never record the attempted username: it may be a mistyped password.
        audit(
            session,
            actor_type="external",
            actor_id=None,
            action="auth.login.failure",
            entity_type="session",
            details={"username_length": len(body.username)},
            ip=ip,
        )
        session.commit()
        raise
    tokens = issue_tokens(session, typ, sub, role)
    audit(
        session,
        actor_type="staff" if typ == "staff" else "member",
        actor_id=sub,
        action="auth.login.success",
        entity_type="session",
        details={"method": "password"},
        ip=ip,
    )
    session.commit()
    return tokens


@router.post("/refresh", response_model=TokensOut)
@limiter.limit(get_settings().rate_limit_auth)
def refresh(request: Request, body: RefreshIn, session: Session = Depends(get_session)) -> dict:
    typ, sub, new_refresh = rotate_refresh_token(session, body.refresh_token)
    out = token_response(sub, typ, role_of(session, typ, sub), new_refresh)
    session.commit()
    return out


@router.post("/logout", status_code=204)
def logout(
    body: RefreshIn, session: Session = Depends(get_session), principal: Principal = Depends(get_principal)
) -> None:
    revoke_refresh_token(session, body.refresh_token)
    audit(
        session,
        actor_type="staff" if principal.typ == "staff" else "member",
        actor_id=principal.id,
        action="auth.logout",
        entity_type="session",
    )
    session.commit()


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(get_principal)) -> MeOut:
    return MeOut(
        id=str(principal.id),
        typ=principal.typ,
        role=principal.role,
        permissions=sorted(principal.permissions),
    )
