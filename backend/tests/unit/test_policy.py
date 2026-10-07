from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from app.services.policy import PolicyEngine

POL = NS(can_borrow_reference=False, fine_limit=Decimal("100"), max_items=4)


def m(status="active"):
    return NS(status=status)


def i(status="available", item_type="lending"):
    return NS(status=status, item_type=item_type)


@pytest.mark.parametrize(
    "member,item,fines,loans,expected",
    [
        (m(), i(), Decimal(0), 0, None),
        (m("blocked"), i(item_type="reference"), Decimal(500), 9, "MEMBER_BLOCKED"),
        (m("expired"), i(), Decimal(0), 0, "MEMBER_EXPIRED"),
        (m(), i(item_type="reference"), Decimal(0), 0, "ITEM_REFERENCE_ONLY"),
        (m(), i(), Decimal("100.01"), 0, "FINE_LIMIT_EXCEEDED"),
        (m(), i(), Decimal("100.00"), 0, None),
        (m(), i(), Decimal(0), 4, "MAX_ITEMS_REACHED"),
        (m(), i("on_loan"), Decimal(0), 0, "ITEM_NOT_AVAILABLE"),
    ],
)
def test_ac04_policy_rules(member, item, fines, loans, expected):
    assert PolicyEngine.evaluate_checkout(member, item, POL, fines, loans) == expected


def test_ac04_reference_allowed_when_policy_permits():
    faculty = NS(can_borrow_reference=True, fine_limit=Decimal("500"), max_items=15)
    assert PolicyEngine.evaluate_checkout(m(), i(item_type="reference"), faculty, Decimal(0), 0) is None


def test_fr04_overdue_days_count_calendar_days():
    due = datetime(2026, 10, 1, 18, 0, tzinfo=UTC)
    assert PolicyEngine.days_overdue(due, due + timedelta(hours=1)) == 0
    assert PolicyEngine.days_overdue(due, due + timedelta(days=5, minutes=3)) == 5
    assert PolicyEngine.days_overdue(due, due - timedelta(days=2)) == 0
