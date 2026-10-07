import pytest
from sqlalchemy import select

from app.db.models import AuditLog

pytestmark = pytest.mark.db


def test_fr04_block_and_unblock_member_audited(client, db_session, auth_headers, sample_member):
    h = auth_headers("Librarian")
    r = client.post(
        f"/api/v1/members/{sample_member.id}/block", headers=h, json={"reason": "Damaged two books"}
    )
    assert r.status_code == 200 and r.json()["status"] == "blocked"
    assert client.post(f"/api/v1/members/{sample_member.id}/unblock", headers=h).json()["status"] == "active"
    rows = db_session.scalars(select(AuditLog).where(AuditLog.entity_id == str(sample_member.id)))
    assert {"member.block", "member.unblock"} <= {a.action for a in rows}


def test_nfr02_clerk_cannot_block(client, auth_headers, sample_member):
    h = auth_headers("CirculationClerk")
    r = client.post(f"/api/v1/members/{sample_member.id}/block", headers=h, json={"reason": "x"})
    assert r.status_code == 403


def test_fr04_create_member_and_lookup_by_card(client, auth_headers):
    h = auth_headers("Librarian")
    body = {
        "card_no": "M900001",
        "full_name": "New Reader",
        "email": "reader@example.org",
        "category_code": "PG",
    }
    assert client.post("/api/v1/members", headers=h, json=body).status_code == 201
    found = client.get("/api/v1/members", headers=h, params={"q": "M900001"}).json()
    assert found[0]["full_name"] == "New Reader"


def test_fr04_duplicate_card_number_rejected(client, auth_headers, sample_member):
    body = {"card_no": sample_member.card_no, "full_name": "Dup", "category_code": "UG"}
    r = client.post("/api/v1/members", headers=auth_headers("Librarian"), json=body)
    assert r.status_code == 409 and r.json()["code"] == "CARD_EXISTS"


def test_nfr02_patron_reads_own_loans_not_others(
    client, patron_headers, sample_member, other_member, active_loan
):
    own = client.get(f"/api/v1/members/{sample_member.id}/loans", headers=patron_headers)
    assert own.status_code == 200 and len(own.json()) == 1
    assert client.get(f"/api/v1/members/{other_member.id}/loans", headers=patron_headers).status_code == 403
    assert client.get(f"/api/v1/members/{other_member.id}", headers=patron_headers).status_code == 403


def test_nfr02_auditor_sees_masked_member_contact(client, auth_headers, sample_member):
    masked = client.get(f"/api/v1/members/{sample_member.id}", headers=auth_headers("Auditor")).json()
    assert masked["email"] == "***" and masked["phone"] == "***"
    full = client.get(f"/api/v1/members/{sample_member.id}", headers=auth_headers("Librarian")).json()
    assert full["email"] == "member@example.org"


def test_fr04_patron_card_pdf(client, auth_headers, sample_member):
    r = client.get(f"/api/v1/members/{sample_member.id}/card.pdf", headers=auth_headers("Librarian"))
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_fr04_fines_pay_and_waive(client, auth_headers, member_with_fines):
    h = auth_headers("Librarian")
    f1 = member_with_fines.set_open_fines("20.00")
    f2 = member_with_fines.set_open_fines("5.00")
    assert client.post(f"/api/v1/fines/{f1.id}/pay", headers=h).json()["status"] == "paid"
    waived = client.post(f"/api/v1/fines/{f2.id}/waive", headers=h, json={"reason": "First offence"})
    assert waived.json()["status"] == "waived"
    assert client.post(f"/api/v1/fines/{f1.id}/pay", headers=h).json()["code"] == "FINE_NOT_OPEN"
