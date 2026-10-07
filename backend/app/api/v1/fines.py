import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.db.base import get_session
from app.db.models import FineStatus
from app.schemas.circulation import FineOut, ReasonIn
from app.services.common import Actor
from app.services.fines import FinesService

router = APIRouter(prefix="/fines", tags=["fines"])


@router.get("", response_model=list[FineOut])
def list_fines(
    status: FineStatus | None = None,
    session: Session = Depends(get_session),
    _: Principal = Depends(require("fines.read")),
) -> list:
    return FinesService(session).list(status=status)


@router.post("/{fine_id}/pay", response_model=FineOut)
def pay(
    fine_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("fines.write")),
):
    fine = FinesService(session).pay(fine_id, Actor.from_principal(p, request))
    session.commit()
    return fine


@router.post("/{fine_id}/waive", response_model=FineOut)
def waive(
    fine_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("fines.write")),
):
    fine = FinesService(session).waive(fine_id, body.reason, Actor.from_principal(p, request))
    session.commit()
    return fine
