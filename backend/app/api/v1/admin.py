import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.auth import Principal, require
from app.core.errors import AppError
from app.db.base import get_session
from app.db.models import CircPolicy
from app.schemas.admin import AuditPage, RoleOut, SettingIn, UserIn, UserOut, UserPatch
from app.schemas.circulation import PolicyOut, PolicyPatch
from app.services.admin import AdminService
from app.services.common import Actor

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(
    session: Session = Depends(get_session), _: Principal = Depends(require("circulation.read"))
):
    return list(session.scalars(select(CircPolicy).order_by(CircPolicy.category_code)))


@router.patch("/policies/{category_code}", response_model=PolicyOut)
def update_policy(
    category_code: str,
    body: PolicyPatch,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("admin.policies.write")),
):
    policy = session.get(CircPolicy, category_code)
    if policy is None:
        raise AppError("CATEGORY_UNKNOWN", "Unknown member category", 404)
    changes = body.model_dump(exclude_unset=True)
    before = {k: str(getattr(policy, k)) for k in changes}
    for field, value in changes.items():
        setattr(policy, field, value)
    actor = Actor.from_principal(p, request)
    audit(
        session,
        actor_type=actor.type,
        actor_id=actor.id,
        action="policy.update",
        entity_type="circ_policy",
        entity_id=category_code,
        details={"before": before, "after": {k: str(v) for k, v in changes.items()}},
        ip=actor.ip,
    )
    session.commit()
    return policy


# --- users, roles, settings, audit (FR 11) -----------------------------------------------------------


@router.get("/users", response_model=list[UserOut])
def list_users(session: Session = Depends(get_session), _: Principal = Depends(require("admin.users.write"))):
    return AdminService(session).list_users()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("admin.users.write")),
):
    user = AdminService(session).create_user(body, Actor.from_principal(p, request))
    session.commit()
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserPatch,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("admin.users.write")),
):
    user = AdminService(session).update_user(user_id, body, Actor.from_principal(p, request))
    session.commit()
    return user


@router.get("/roles", response_model=list[RoleOut])
def list_roles(session: Session = Depends(get_session), _: Principal = Depends(require("admin.users.write"))):
    return AdminService(session).roles()


@router.get("/settings")
def get_settings_values(
    session: Session = Depends(get_session), _: Principal = Depends(require("admin.settings.write"))
) -> dict:
    return AdminService(session).settings()


@router.put("/settings/{key}")
def put_setting(
    key: str,
    body: SettingIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("admin.settings.write")),
) -> dict:
    result = AdminService(session).put_setting(key, body.value, Actor.from_principal(p, request))
    session.commit()
    return result


@router.get("/audit", response_model=AuditPage)
def audit_log(
    actor_id: uuid.UUID | None = None,
    action: str | None = Query(default=None, max_length=60),
    entity_id: str | None = Query(default=None, max_length=64),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: Principal = Depends(require("audit.read")),
) -> AuditPage:
    return AdminService(session).audit_page(
        actor_id=actor_id,
        action=action,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
