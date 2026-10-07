from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import Principal, ensure_self_or, get_principal, require
from app.db.base import get_session
from app.db.models import LoanChannel
from app.schemas.circulation import CheckinOut, CheckoutIn, DueOut, FineOut, ItemRefIn, LoanOut, RenewIn
from app.services.circulation import CirculationService, keep_refusal_audit
from app.services.common import Actor

router = APIRouter(prefix="/circulation", tags=["circulation"])


@router.post("/checkout", response_model=LoanOut, status_code=201)
def checkout(
    body: CheckoutIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("circulation.checkout")),
):
    with keep_refusal_audit(session):
        loan = CirculationService(session).checkout(
            member_card_no=body.member_card_no,
            item_ref=body.item,
            channel=LoanChannel.ui,
            actor=Actor.from_principal(p, request),
        )
    session.commit()
    return loan


@router.post("/renew", response_model=LoanOut)
def renew(
    body: RenewIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(get_principal),
):
    service = CirculationService(session)
    with keep_refusal_audit(session):
        loan = service.find_open_loan(item_ref=body.item, loan_id=body.loan_id)
        ensure_self_or(p, loan.member_id, "circulation.renew")
        loan = service.renew(loan, channel=LoanChannel.ui, actor=Actor.from_principal(p, request))
    session.commit()
    return loan


@router.post("/checkin", response_model=CheckinOut)
def checkin(
    body: ItemRefIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("circulation.checkin")),
) -> CheckinOut:
    with keep_refusal_audit(session):
        result = CirculationService(session).checkin(
            item_ref=body.item, channel=LoanChannel.ui, actor=Actor.from_principal(p, request)
        )
    session.commit()
    return CheckinOut(
        loan=LoanOut.model_validate(result.loan),
        fine=FineOut.model_validate(result.fine) if result.fine else None,
    )


@router.get("/due", response_model=DueOut)
def due(
    item: str = Query(min_length=1, max_length=40),
    session: Session = Depends(get_session),
    _: Principal = Depends(require("circulation.read")),
) -> DueOut:
    info = CirculationService(session).due(item)
    due_at = info.loan.due_at if info.loan else None
    return DueOut(
        item_id=info.item.id,
        accession_no=info.item.accession_no,
        on_loan=info.loan is not None,
        due_at=due_at,
        overdue=bool(due_at and due_at < datetime.now(UTC)),
    )
