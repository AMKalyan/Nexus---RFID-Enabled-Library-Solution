from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.auth import Principal, require
from app.core.errors import AppError
from app.db.base import get_session
from app.db.models import CircPolicy
from app.schemas.circulation import PolicyOut, PolicyPatch
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
