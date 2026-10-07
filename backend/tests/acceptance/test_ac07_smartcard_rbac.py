"""AC 07: staff smart-card login through a mock credential provider, with role-based permissions enforced."""

import pytest
from sqlalchemy import select

from app.db.models import AuditLog, DeviceEvent
from app.middleware_rfid.live_hub import hub
from tests.factories import make_staff

pytestmark = [pytest.mark.db, pytest.mark.acceptance]


def tap(client, reader, device_event, uid):
    body = device_event("CardTapped", device_type="smartcard_reader", card_uid=uid)
    return client.post(
        f"/api/v1/devices/{reader.code}/events", json=body, headers={"X-Device-Key": reader.raw_key}
    )


def card_login(client, reader, device_event, uid):
    challenge = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": reader.code}).json()
    tap(client, reader, device_event, uid)
    body = {"reader_code": reader.code, "challenge_id": challenge["challenge_id"]}
    return client.post("/api/v1/auth/smartcard", json=body)


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_ac07_card_login_and_role_enforcement(client, db_session, device_card, device_event):
    make_staff(db_session, "CirculationClerk", username="clerkcard", smartcard_uid="04A1B2C3")
    make_staff(db_session, "Auditor", username="audcard", smartcard_uid="04D4E5F6")
    clerk = card_login(client, device_card, device_event, "04A1B2C3")
    assert clerk.status_code == 200
    auditor = card_login(client, device_card, device_event, "04d4e5f6")  # readers may send lower case
    assert auditor.status_code == 200
    assert client.get("/api/v1/auth/me", headers=bearer(clerk)).json()["role"] == "CirculationClerk"
    assert client.get("/api/v1/admin/users", headers=bearer(clerk)).status_code == 403
    assert client.post("/api/v1/migration/batches", headers=bearer(clerk)).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=bearer(auditor)).status_code == 200
    checkout = {"member_card_no": "x", "item": "y"}
    assert (
        client.post("/api/v1/circulation/checkout", headers=bearer(auditor), json=checkout).status_code == 403
    )


def test_ac07_unknown_card_rejected_and_audited_without_uid(client, db_session, device_card, device_event):
    r = card_login(client, device_card, device_event, "DEADBEEF")
    assert r.status_code == 401 and r.json()["code"] == "CARD_UNKNOWN"
    rows = db_session.scalars(select(AuditLog).where(AuditLog.action.like("auth.card%"))).all()
    assert rows and all("DEADBEEF" not in str(row.details) for row in rows)
    stored = db_session.scalars(select(DeviceEvent).where(DeviceEvent.event_type == "CardTapped")).all()
    assert all("DEADBEEF" not in str(e.payload) for e in stored)


def test_ac07_deactivated_staff_card_rejected(client, db_session, device_card, device_event):
    user = make_staff(db_session, "Librarian", username="gone", smartcard_uid="04BBBBBB")
    user.is_active = False
    db_session.flush()
    assert card_login(client, device_card, device_event, "04BBBBBB").json()["code"] == "CARD_UNKNOWN"


def test_ac07_challenge_single_use(client, db_session, device_card, device_event):
    make_staff(db_session, "Librarian", username="libcard", smartcard_uid="04AAAAAA")
    challenge = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": device_card.code}).json()
    tap(client, device_card, device_event, "04AAAAAA")
    body = {"reader_code": device_card.code, "challenge_id": challenge["challenge_id"]}
    assert client.post("/api/v1/auth/smartcard", json=body).status_code == 200
    again = client.post("/api/v1/auth/smartcard", json=body)
    assert again.status_code == 401 and again.json()["code"] == "CARD_CHALLENGE_INVALID"


def test_ac07_completing_before_tap_is_pending(client, device_card):
    challenge = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": device_card.code}).json()
    body = {"reader_code": device_card.code, "challenge_id": challenge["challenge_id"]}
    r = client.post("/api/v1/auth/smartcard", json=body)
    assert r.status_code == 409 and r.json()["code"] == "CARD_NOT_TAPPED"


def test_ac07_challenge_bound_to_its_reader(client, db_session, device_card, device_event):
    from tests.factories import make_device

    other = make_device(db_session, "CARD-02", "smartcard_reader")
    make_staff(db_session, "Librarian", username="libcard2", smartcard_uid="04CCCCCC")
    challenge = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": device_card.code}).json()
    tap(client, other, device_event, "04CCCCCC")  # tapped on a different reader
    body = {"reader_code": device_card.code, "challenge_id": challenge["challenge_id"]}
    assert client.post("/api/v1/auth/smartcard", json=body).json()["code"] == "CARD_NOT_TAPPED"


def test_ac07_tap_is_published_for_the_waiting_login_page(client, db_session, device_card, device_event):
    make_staff(db_session, "Librarian", username="libcard3", smartcard_uid="04DDDDDD")
    challenge = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": device_card.code}).json()
    tap(client, device_card, device_event, "04DDDDDD")
    event = hub.recent("auth.card")[-1]["data"]
    assert event == {"reader_code": device_card.code, "challenge_id": challenge["challenge_id"], "ok": True}


def test_ac07_challenge_for_unknown_reader_rejected(client):
    r = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": "NOPE"})
    assert r.status_code == 404 and r.json()["code"] == "READER_NOT_FOUND"
