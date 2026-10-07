"""AC 04: block circulation for a reference item, a blocked member, or fines over a configurable limit."""

import pytest
from sqlalchemy import select

from app.db.models import AuditLog

pytestmark = [pytest.mark.db, pytest.mark.acceptance]


def _checkout(client, h, member, item):
    body = {"member_card_no": member.card_no, "item": item.accession_no}
    return client.post("/api/v1/circulation/checkout", headers=h, json=body)


def test_ac04_reference_item_blocked(client, auth_headers, sample_member, reference_item):
    r = _checkout(client, auth_headers("CirculationClerk"), sample_member, reference_item)
    assert r.status_code == 409 and r.json()["code"] == "ITEM_REFERENCE_ONLY"


def test_ac04_blocked_member_refused(client, auth_headers, blocked_member, tagged_item):
    r = _checkout(client, auth_headers("CirculationClerk"), blocked_member, tagged_item)
    assert r.status_code == 409 and r.json()["code"] == "MEMBER_BLOCKED"


def test_ac04_fine_limit_configurable(client, auth_headers, member_with_fines, tagged_item):
    member_with_fines.set_open_fines("120.00")  # UG limit is 100.00
    clerk, admin = auth_headers("CirculationClerk"), auth_headers("Admin")
    refused = _checkout(client, clerk, member_with_fines.member, tagged_item)
    assert refused.json()["code"] == "FINE_LIMIT_EXCEEDED"
    r = client.patch("/api/v1/admin/policies/UG", headers=admin, json={"fine_limit": "150.00"})
    assert r.status_code == 200 and r.json()["fine_limit"] == "150.00"
    assert _checkout(client, clerk, member_with_fines.member, tagged_item).status_code == 201


def test_ac04_refusals_are_audited(client, db_session, auth_headers, blocked_member, tagged_item):
    _checkout(client, auth_headers("CirculationClerk"), blocked_member, tagged_item)
    row = db_session.scalars(select(AuditLog).where(AuditLog.action == "circulation.refused")).one()
    assert row.details["code"] == "MEMBER_BLOCKED" and row.details["channel"] == "ui"


def test_ac04_only_admin_changes_policy(client, auth_headers):
    r = client.patch(
        "/api/v1/admin/policies/UG", headers=auth_headers("Librarian"), json={"fine_limit": "1.00"}
    )
    assert r.status_code == 403
