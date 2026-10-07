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
from app.db.models import Device, DeviceType
from app.services.smartcard import challenges
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


# --- smart-card sign-in (AC 07) ----------------------------------------------------------------------


class ChallengeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reader_code: str = Field(min_length=1, max_length=20)


class ChallengeOut(BaseModel):
    challenge_id: str
    expires_in: int


class CardLoginIn(ChallengeIn):
    challenge_id: str = Field(min_length=10, max_length=64)


@router.post("/smartcard/challenge", response_model=ChallengeOut)
@limiter.limit(get_settings().rate_limit_auth)
def smartcard_challenge(
    request: Request, body: ChallengeIn, session: Session = Depends(get_session)
) -> ChallengeOut:
    reader = session.get(Device, body.reader_code)
    if reader is None or reader.device_type != DeviceType.smartcard_reader:
        raise AppError("READER_NOT_FOUND", "Unknown card reader", 404)
    return ChallengeOut(challenge_id=challenges.open(body.reader_code), expires_in=60)


@router.post("/smartcard", response_model=TokensOut)
@limiter.limit(get_settings().rate_limit_auth)
def smartcard_login(request: Request, body: CardLoginIn, session: Session = Depends(get_session)) -> dict:
    ip = request.client.host if request.client else None
    try:
        identity = challenges.consume(body.reader_code, body.challenge_id)
    except AppError as exc:
        if exc.code == "CARD_UNKNOWN":
            audit(
                session,
                actor_type="external",
                actor_id=None,
                action="auth.login.failure",
                entity_type="session",
                details={"method": "smartcard", "reader": body.reader_code},
                ip=ip,
            )
            session.commit()
        raise
    tokens = issue_tokens(session, "staff", identity.user_id, identity.role)
    audit(
        session,
        actor_type="staff",
        actor_id=identity.user_id,
        action="auth.login.success",
        entity_type="session",
        details={"method": "smartcard", "reader": body.reader_code},
        ip=ip,
    )
    session.commit()
    return tokens
