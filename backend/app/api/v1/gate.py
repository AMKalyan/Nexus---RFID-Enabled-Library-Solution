import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import AppError
from app.core.logging import mask_pii
from app.db.base import get_session
from app.db.models import GateEvent, OutboxStatus
from app.services.gate import GateService
from app.services.notifications import NotificationsService

router = APIRouter(tags=["security gate"])


class GateEventOut(BaseModel):
    id: uuid.UUID
    device_code: str
    epc: str
    item_id: uuid.UUID | None
    accession_no: str | None
    direction: str
    authorised: bool
    alarm: bool
    offline_decision: bool
    notified: bool
    has_photo: bool
    occurred_at: datetime


class OutboxOut(BaseModel):
    id: uuid.UUID
    channel: str
    recipient: str
    template: str
    subject: str | None
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None


def gate_out(e: GateEvent) -> GateEventOut:
    return GateEventOut(
        id=e.id,
        device_code=e.device_code,
        epc=e.epc,
        item_id=e.item_id,
        accession_no=e.accession_no,
        direction=e.direction,
        authorised=e.authorised,
        alarm=e.alarm,
        offline_decision=e.offline_decision,
        notified=e.notified,
        has_photo=e.photo_jpeg is not None,
        occurred_at=e.occurred_at,
    )


@router.get("/gate/events", response_model=list[GateEventOut])
def gate_events(
    alarm: bool | None = None,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    session: Session = Depends(get_session),
    _: Principal = Depends(require("gate.read")),
) -> list[GateEventOut]:
    return [
        gate_out(e) for e in GateService(session).events(alarm=alarm, date_from=date_from, date_to=date_to)
    ]


@router.get("/gate/events/{event_id}/photo")
def gate_photo(
    event_id: uuid.UUID, session: Session = Depends(get_session), _: Principal = Depends(require("gate.read"))
) -> Response:
    event = session.get(GateEvent, event_id)
    if event is None or event.photo_jpeg is None:
        raise AppError("PHOTO_NOT_FOUND", "No snapshot for this event", 404)
    return Response(
        event.photo_jpeg, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"}
    )


@router.get("/notifications/outbox", response_model=list[OutboxOut])
def outbox(
    status: OutboxStatus | None = None,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("notifications.read")),
) -> list[OutboxOut]:
    mask = "member.pii.read" not in p.permissions
    return [
        OutboxOut(
            id=r.id,
            channel=r.channel.value,
            recipient=mask_pii(r.recipient) if mask else r.recipient,
            template=r.template,
            subject=r.subject,
            status=r.status.value,
            attempts=r.attempts,
            last_error=r.last_error,
            created_at=r.created_at,
            sent_at=r.sent_at,
        )
        for r in NotificationsService(session).outbox(status)
    ]
