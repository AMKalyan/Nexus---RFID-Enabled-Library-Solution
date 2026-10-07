"""Check-out, renewal, check-in and due-date enquiry (FR 04).

The UI, NCIP and SIP2 adapters all call this service, so rules, security-bit handling and the audit trail
are identical on every channel (AC 03, AC 04).
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import AppError
from app.db.models import CircPolicy, Fine, Item, ItemStatus, Loan, LoanChannel, Member, RfidTag, TagStatus
from app.services.catalog import CatalogService
from app.services.common import Actor
from app.services.fines import FinesService
from app.services.members import MembersService
from app.services.notifications import NotificationsService
from app.services.policy import PolicyEngine

REFUSAL_MESSAGES = {
    "ITEM_REFERENCE_ONLY": "Reference items cannot be borrowed",
    "MEMBER_BLOCKED": "Member is blocked",
    "MEMBER_EXPIRED": "Membership has expired",
    "FINE_LIMIT_EXCEEDED": "Outstanding fines exceed the member's limit",
    "MAX_ITEMS_REACHED": "Member has reached the loan limit",
    "MAX_RENEWALS_REACHED": "Loan has reached the renewal limit",
    "ITEM_NOT_AVAILABLE": "Item is not available for loan",
    "ITEM_NOT_ON_LOAN": "Item is not on loan",
}


class CirculationRefused(AppError):
    def __init__(self, code: str) -> None:
        super().__init__(code, REFUSAL_MESSAGES.get(code, "Circulation refused"), 409)


@dataclass
class CheckinResult:
    loan: Loan
    fine: Fine | None


@dataclass
class DueInfo:
    item: Item
    loan: Loan | None


@contextmanager
def keep_refusal_audit(session: Session) -> Iterator[None]:
    """Commit the audit entry written for a refusal before the error propagates."""
    try:
        yield
    except CirculationRefused:
        session.commit()
        raise


class CirculationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog = CatalogService(session)
        self.members = MembersService(session)
        self.fines = FinesService(session)

    # --- helpers ---

    def _locked_item(self, item_ref: str) -> Item:
        item = self.catalog.get_item_by_ref(item_ref)
        # Row lock: a concurrent check-out of the same item waits here and then sees it on loan.
        self.session.refresh(item, with_for_update=True)
        return item

    def _policy(self, member: Member) -> CircPolicy:
        policy = self.session.get(CircPolicy, member.category_code)
        if policy is None:
            raise AppError("CATEGORY_UNKNOWN", "Unknown member category", 422)
        return policy

    def _set_security_bit(self, item_id: uuid.UUID, value: bool) -> None:
        self.session.execute(
            update(RfidTag)
            .where(RfidTag.item_id == item_id, RfidTag.status == TagStatus.active)
            .values(security_bit=value)
        )

    def _audit(
        self,
        actor: Actor,
        action: str,
        channel: LoanChannel,
        item: Item,
        member: Member | None,
        **extra: object,
    ) -> None:
        details = {
            "channel": channel.value,
            "item": item.accession_no,
            "member": member.card_no if member else None,
        }
        details.update({k: str(v) if v is not None else None for k, v in extra.items()})
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action=action,
            entity_type="item",
            entity_id=str(item.id),
            details=details,
            ip=actor.ip,
        )

    def _refuse(
        self, code: str, actor: Actor, channel: LoanChannel, item: Item, member: Member | None, operation: str
    ) -> None:
        self._audit(actor, "circulation.refused", channel, item, member, code=code, operation=operation)
        raise CirculationRefused(code)

    def open_loan_for_item(self, item_id: uuid.UUID, lock: bool = False) -> Loan | None:
        query = select(Loan).where(Loan.item_id == item_id, Loan.returned_at.is_(None))
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    # --- operations ---

    def checkout(self, *, member_card_no: str, item_ref: str, channel: LoanChannel, actor: Actor) -> Loan:
        member = self.members.get_by_card(member_card_no)
        item = self._locked_item(item_ref)
        policy = self._policy(member)
        code = PolicyEngine.evaluate_checkout(
            member, item, policy, self.fines.open_total(member.id), self.members.open_loan_count(member.id)
        )
        if code:
            self._refuse(code, actor, channel, item, member, "checkout")

        now = datetime.now(UTC)
        loan = Loan(
            item_id=item.id,
            member_id=member.id,
            issued_at=now,
            due_at=now + timedelta(days=policy.loan_days),
            channel=channel,
            issued_by=actor.id if actor.type == "staff" else None,
        )
        try:
            with self.session.begin_nested():
                self.session.add(loan)
                self.session.flush()
        except IntegrityError:  # the open-loan unique index is the final guard
            self._refuse("ITEM_NOT_AVAILABLE", actor, channel, item, member, "checkout")
        item.status = ItemStatus.on_loan
        self._set_security_bit(item.id, False)
        self.session.flush()
        self._audit(actor, "circulation.checkout", channel, item, member, due_at=loan.due_at.isoformat())
        return loan

    def find_open_loan(self, *, item_ref: str | None = None, loan_id: uuid.UUID | None = None) -> Loan:
        if loan_id is not None:
            loan = self.session.get(Loan, loan_id)
            if loan is None:
                raise AppError("LOAN_NOT_FOUND", "Loan not found", 404)
        else:
            item = self.catalog.get_item_by_ref(item_ref or "")
            found = self.open_loan_for_item(item.id)
            if found is None:
                raise CirculationRefused("ITEM_NOT_ON_LOAN")
            loan = found
        if loan.returned_at is not None:
            raise CirculationRefused("ITEM_NOT_ON_LOAN")
        return loan

    def renew(self, loan: Loan, *, channel: LoanChannel, actor: Actor) -> Loan:
        self.session.refresh(loan, with_for_update=True)
        member, item = loan.member, loan.item
        policy = self._policy(member)
        code = PolicyEngine.evaluate_renewal(
            member, policy, self.fines.open_total(member.id), loan.renew_count
        )
        if code:
            self._refuse(code, actor, channel, item, member, "renew")
        loan.due_at = max(datetime.now(UTC), loan.due_at) + timedelta(days=policy.loan_days)
        loan.renew_count += 1
        self.session.flush()
        self._audit(
            actor,
            "circulation.renew",
            channel,
            item,
            member,
            due_at=loan.due_at.isoformat(),
            renew_count=loan.renew_count,
        )
        return loan

    def checkin(self, *, item_ref: str, channel: LoanChannel, actor: Actor) -> CheckinResult:
        item = self._locked_item(item_ref)
        loan = self.open_loan_for_item(item.id, lock=True)
        if loan is None:
            self._refuse("ITEM_NOT_ON_LOAN", actor, channel, item, None, "checkin")
            raise AssertionError("unreachable")
        now = datetime.now(UTC)
        loan.returned_at = now
        loan.returned_by = actor.id if actor.type == "staff" else None
        item.status = ItemStatus.available
        self._set_security_bit(item.id, True)
        policy = self._policy(loan.member)
        days = PolicyEngine.days_overdue(loan.due_at, now)
        fine = self.fines.raise_overdue(loan, PolicyEngine.overdue_fine(days, policy.fine_per_day), actor)
        notifier = NotificationsService(self.session)
        if fine and notifier.setting("overdue_notices_enabled", True):
            notifier.queue_for_member(
                loan.member,
                "overdue_notice",
                {
                    "title": item.bib.title,
                    "accession_no": item.accession_no,
                    "days": days,
                    "amount": fine.amount,
                },
            )
        self.session.flush()
        self._audit(
            actor,
            "circulation.checkin",
            channel,
            item,
            loan.member,
            days_overdue=days,
            fine=fine.amount if fine else None,
        )
        return CheckinResult(loan=loan, fine=fine)

    def due(self, item_ref: str) -> DueInfo:
        item = self.catalog.get_item_by_ref(item_ref)
        return DueInfo(item=item, loan=self.open_loan_for_item(item.id))
