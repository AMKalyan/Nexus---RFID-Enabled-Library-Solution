import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import Principal, ensure_self_or, get_principal, require
from app.db.base import get_session
from app.db.models import Member
from app.schemas.circulation import (
    FineOut,
    LoanDetailOut,
    MemberIn,
    MemberOut,
    MemberPatch,
    MemberSummaryOut,
    ReasonIn,
)
from app.services.cards import patron_card_pdf
from app.services.common import Actor
from app.services.fines import FinesService
from app.services.members import MembersService

router = APIRouter(prefix="/members", tags=["members"])


def visible(member: Member | MemberSummaryOut, principal: Principal) -> MemberOut | MemberSummaryOut:
    """Contact details are masked unless the caller may read personal data or is the member."""
    out = member if isinstance(member, MemberSummaryOut) else MemberOut.model_validate(member)
    own = principal.typ == "patron" and principal.id == out.id
    if not own and "member.pii.read" not in principal.permissions:
        out = out.model_copy(
            update={"email": "***" if out.email else None, "phone": "***" if out.phone else None}
        )
    return out


@router.get("", response_model=list[MemberOut])
def search_members(
    q: str | None = Query(default=None, max_length=100),
    session: Session = Depends(get_session),
    p: Principal = Depends(require("members.read")),
) -> list:
    return [visible(m, p) for m in MembersService(session).search(q)]


@router.post("", response_model=MemberOut, status_code=201)
def create_member(
    body: MemberIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("members.write")),
):
    member = MembersService(session).create(body, Actor.from_principal(p, request))
    session.commit()
    return member


@router.get("/{member_id}", response_model=MemberSummaryOut)
def get_member(
    member_id: uuid.UUID, session: Session = Depends(get_session), p: Principal = Depends(get_principal)
):
    ensure_self_or(p, member_id, "members.read")
    service = MembersService(session)
    return visible(service.summary(service.get(member_id)), p)


@router.patch("/{member_id}", response_model=MemberOut)
def update_member(
    member_id: uuid.UUID,
    body: MemberPatch,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("members.write")),
):
    member = MembersService(session).update(member_id, body, Actor.from_principal(p, request))
    session.commit()
    return member


@router.post("/{member_id}/block", response_model=MemberOut)
def block_member(
    member_id: uuid.UUID,
    body: ReasonIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("members.block")),
):
    member = MembersService(session).block(member_id, body.reason, Actor.from_principal(p, request))
    session.commit()
    return member


@router.post("/{member_id}/unblock", response_model=MemberOut)
def unblock_member(
    member_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("members.block")),
):
    member = MembersService(session).unblock(member_id, Actor.from_principal(p, request))
    session.commit()
    return member


@router.get("/{member_id}/loans", response_model=list[LoanDetailOut])
def member_loans(
    member_id: uuid.UUID,
    history: bool = False,
    session: Session = Depends(get_session),
    p: Principal = Depends(get_principal),
) -> list[LoanDetailOut]:
    ensure_self_or(p, member_id, "circulation.read")
    return MembersService(session).loans(member_id, include_returned=history)


@router.get("/{member_id}/fines", response_model=list[FineOut])
def member_fines(
    member_id: uuid.UUID, session: Session = Depends(get_session), p: Principal = Depends(get_principal)
) -> list:
    ensure_self_or(p, member_id, "fines.read")
    return FinesService(session).list(member_id=member_id)


@router.get("/{member_id}/card.pdf")
def member_card(
    member_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: Principal = Depends(require("members.write")),
) -> Response:
    return Response(patron_card_pdf(MembersService(session).get(member_id)), media_type="application/pdf")
