"""Circulation rules (FR 04, AC 04). Pure functions so every channel applies them identically."""

from datetime import datetime
from decimal import Decimal
from typing import Any


class PolicyEngine:
    @staticmethod
    def evaluate_checkout(
        member: Any, item: Any, policy: Any, open_fines: Decimal, open_loans: int
    ) -> str | None:
        """Return the refusal code for a check-out, or None if it is allowed. The first matching rule wins."""
        if member.status == "blocked":
            return "MEMBER_BLOCKED"
        if member.status == "expired":
            return "MEMBER_EXPIRED"
        if item.status != "available":
            return "ITEM_NOT_AVAILABLE"
        if item.item_type == "reference" and not policy.can_borrow_reference:
            return "ITEM_REFERENCE_ONLY"
        if open_fines > policy.fine_limit:
            return "FINE_LIMIT_EXCEEDED"
        if open_loans >= policy.max_items:
            return "MAX_ITEMS_REACHED"
        return None

    @staticmethod
    def evaluate_renewal(member: Any, policy: Any, open_fines: Decimal, renew_count: int) -> str | None:
        if member.status == "blocked":
            return "MEMBER_BLOCKED"
        if member.status == "expired":
            return "MEMBER_EXPIRED"
        if open_fines > policy.fine_limit:
            return "FINE_LIMIT_EXCEEDED"
        if renew_count >= policy.max_renewals:
            return "MAX_RENEWALS_REACHED"
        return None

    @staticmethod
    def days_overdue(due_at: datetime, returned_at: datetime) -> int:
        """Whole calendar days between the due date and the return date."""
        return max(0, (returned_at.date() - due_at.date()).days)

    @staticmethod
    def overdue_fine(days: int, fine_per_day: Decimal) -> Decimal:
        return (Decimal(days) * fine_per_day).quantize(Decimal("0.01"))
