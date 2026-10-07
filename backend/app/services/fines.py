import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import AppError
from app.db.models import Fine, FineReason, FineStatus, Loan
from app.services.common import Actor


class FinesService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def open_total(self, member_id: uuid.UUID) -> Decimal:
        total = self.session.scalar(
            select(func.coalesce(func.sum(Fine.amount), 0)).where(
                Fine.member_id == member_id, Fine.status == FineStatus.open
            )
        )
        return Decimal(total or 0)

    def raise_overdue(self, loan: Loan, amount: Decimal, actor: Actor) -> Fine | None:
        if amount <= 0:
            return None
        fine = Fine(member_id=loan.member_id, loan_id=loan.id, amount=amount, reason=FineReason.overdue)
        self.session.add(fine)
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="fine.raise",
            entity_type="fine",
            entity_id=str(fine.id),
            details={"amount": str(amount), "loan_id": str(loan.id)},
            ip=actor.ip,
        )
        return fine

    def list(self, status: FineStatus | None = None, member_id: uuid.UUID | None = None) -> list[Fine]:
        query = select(Fine).order_by(Fine.created_at.desc()).limit(500)
        if status:
            query = query.where(Fine.status == status)
        if member_id:
            query = query.where(Fine.member_id == member_id)
        return list(self.session.scalars(query))

    def _settle(self, fine_id: uuid.UUID, status: FineStatus, actor: Actor, reason: str | None) -> Fine:
        fine = self.session.get(Fine, fine_id, with_for_update=True)
        if fine is None:
            raise AppError("FINE_NOT_FOUND", "Fine not found", 404)
        if fine.status != FineStatus.open:
            raise AppError("FINE_NOT_OPEN", "Fine is already settled", 409)
        fine.status = status
        fine.settled_at = datetime.now(UTC)
        fine.settled_by = actor.id
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action=f"fine.{status.value}",
            entity_type="fine",
            entity_id=str(fine.id),
            details={"amount": str(fine.amount), "reason": reason},
            ip=actor.ip,
        )
        return fine

    def pay(self, fine_id: uuid.UUID, actor: Actor) -> Fine:
        return self._settle(fine_id, FineStatus.paid, actor, None)

    def waive(self, fine_id: uuid.UUID, reason: str, actor: Actor) -> Fine:
        return self._settle(fine_id, FineStatus.waived, actor, reason)
