import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.db.base import get_session
from app.services.common import Actor
from app.services.inventory import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])


class StartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shelf_code: str = Field(min_length=1, max_length=20)
    device_code: str = Field(min_length=1, max_length=20)


@router.post("/sessions", status_code=201)
def start(
    body: StartIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("inventory.write")),
) -> dict:
    service = InventoryService(session)
    inv = service.start(body.shelf_code, body.device_code, Actor.from_principal(p, request))
    session.commit()
    return service.summary(inv.id)


@router.get("/sessions/{session_id}")
def get_session_summary(
    session_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: Principal = Depends(require("inventory.read")),
) -> dict:
    return InventoryService(session).summary(session_id)


@router.post("/sessions/{session_id}/close")
def close(
    session_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("inventory.write")),
) -> dict:
    report = InventoryService(session).close(session_id, Actor.from_principal(p, request))
    session.commit()
    return report


@router.post("/sessions/{session_id}/mark-missing")
def mark_missing(
    session_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("inventory.write")),
) -> dict:
    marked = InventoryService(session).mark_missing(session_id, Actor.from_principal(p, request))
    session.commit()
    return {"marked": marked}
