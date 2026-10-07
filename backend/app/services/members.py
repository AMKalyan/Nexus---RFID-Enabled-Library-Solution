import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import AppError
from app.db.models import CircPolicy, Item, Loan, Member, MemberStatus
from app.schemas.circulation import LoanDetailOut, LoanOut, MemberIn, MemberOut, MemberPatch, MemberSummaryOut
from app.services.common import Actor
from app.services.fines import FinesService


class MembersService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, member_id: uuid.UUID) -> Member:
        member = self.session.get(Member, member_id)
        if member is None:
            raise AppError("MEMBER_NOT_FOUND", "Member not found", 404)
        return member

    def get_by_card(self, card_no: str) -> Member:
        member = self.session.scalar(select(Member).where(Member.card_no == card_no))
        if member is None:
            raise AppError("MEMBER_NOT_FOUND", "Member not found", 404)
        return member

    def search(self, q: str | None, limit: int = 25) -> list[Member]:
        query = select(Member).order_by(Member.card_no).limit(limit)
        if q:
            query = query.where(or_(Member.card_no == q, Member.full_name.ilike(f"%{q}%")))
        return list(self.session.scalars(query))

    def _policy(self, category_code: str) -> CircPolicy:
        policy = self.session.get(CircPolicy, category_code)
        if policy is None:
            raise AppError("CATEGORY_UNKNOWN", "Unknown member category", 422)
        return policy

    def create(self, data: MemberIn, actor: Actor) -> Member:
        self._policy(data.category_code)
        if self.session.scalar(select(Member.id).where(Member.card_no == data.card_no)):
            raise AppError("CARD_EXISTS", "Card number already exists", 409)
        member = Member(**data.model_dump())
        self.session.add(member)
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="member.create",
            entity_type="member",
            entity_id=str(member.id),
            details={"card_no": member.card_no},
            ip=actor.ip,
        )
        return member

    def update(self, member_id: uuid.UUID, data: MemberPatch, actor: Actor) -> Member:
        member = self.get(member_id)
        changes = data.model_dump(exclude_unset=True)
        if "category_code" in changes:
            self._policy(changes["category_code"])
        for field, value in changes.items():
            setattr(member, field, value)
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="member.update",
            entity_type="member",
            entity_id=str(member.id),
            details={"fields": sorted(changes)},
            ip=actor.ip,
        )
        return member

    def block(self, member_id: uuid.UUID, reason: str, actor: Actor) -> Member:
        member = self.get(member_id)
        member.status, member.block_reason = MemberStatus.blocked, reason
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="member.block",
            entity_type="member",
            entity_id=str(member.id),
            details={"reason": reason},
            ip=actor.ip,
        )
        return member

    def unblock(self, member_id: uuid.UUID, actor: Actor) -> Member:
        member = self.get(member_id)
        member.status, member.block_reason = MemberStatus.active, None
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="member.unblock",
            entity_type="member",
            entity_id=str(member.id),
            ip=actor.ip,
        )
        return member

    def open_loan_count(self, member_id: uuid.UUID) -> int:
        q = (
            select(func.count())
            .select_from(Loan)
            .where(Loan.member_id == member_id, Loan.returned_at.is_(None))
        )
        return self.session.scalar(q) or 0

    def summary(self, member: Member) -> MemberSummaryOut:
        policy = self._policy(member.category_code)
        base = MemberOut.model_validate(member).model_dump()
        return MemberSummaryOut(
            **base,
            open_fines=FinesService(self.session).open_total(member.id),
            fine_limit=policy.fine_limit,
            open_loans=self.open_loan_count(member.id),
            max_items=policy.max_items,
        )

    def loans(self, member_id: uuid.UUID, include_returned: bool = False) -> list[LoanDetailOut]:
        query = (
            select(Loan, Item)
            .join(Item, Item.id == Loan.item_id)
            .where(Loan.member_id == member_id)
            .order_by(Loan.issued_at.desc())
        )
        if not include_returned:
            query = query.where(Loan.returned_at.is_(None))
        rows = self.session.execute(query.limit(200)).all()
        return [
            LoanDetailOut(
                **LoanOut.model_validate(loan).model_dump(),
                accession_no=item.accession_no,
                title=item.bib.title,
            )
            for loan, item in rows
        ]
