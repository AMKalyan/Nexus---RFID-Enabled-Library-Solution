"""AC 06: an unauthorised-removal event from the gate mock records the accession number, attaches a mock
CCTV image and queues an email notification."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db.models import AuditLog, GateEvent, NotificationOutbox
from app.middleware_rfid.live_hub import hub

pytestmark = [pytest.mark.db, pytest.mark.acceptance]


def _pass(client, gate, device_event, epc, direction="out", offline=False, **kw):
    body = device_event(
        "GatePassage",
        device_type="gate",
        epcs=[epc],
        direction=direction,
        security_bit=True,
        offline_decision=offline,
        **kw,
    )
    return client.post(
        f"/api/v1/devices/{gate.code}/events", json=body, headers={"X-Device-Key": gate.raw_key}
    )


def test_ac06_unissued_item_triggers_alarm_photo_and_email(
    client, db_session, auth_headers, device_gate, camera, tagged_item, device_event
):
    assert _pass(client, device_gate, device_event, tagged_item.active_epc).status_code == 202
    ge = db_session.scalars(select(GateEvent)).one()
    assert ge.alarm and not ge.authorised and ge.accession_no == tagged_item.accession_no
    assert ge.photo_jpeg[:2] == b"\xff\xd8" and ge.notified
    out = db_session.scalars(
        select(NotificationOutbox).where(NotificationOutbox.related_id == str(ge.id))
    ).all()
    assert [o.channel for o in out] == ["email"] and out[0].status == "queued"
    assert tagged_item.accession_no in out[0].body
    photo = client.get(f"/api/v1/gate/events/{ge.id}/photo", headers=auth_headers("Librarian"))
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert hub.recent("gate.alert")[-1]["data"]["accession_no"] == tagged_item.accession_no
    assert db_session.scalars(select(AuditLog).where(AuditLog.action == "gate.alarm")).first() is not None


def test_ac06_issued_item_passes_silently(client, db_session, device_gate, camera, active_loan, device_event):
    _pass(client, device_gate, device_event, active_loan.item_epc)
    ge = db_session.scalars(select(GateEvent)).one()
    assert ge.authorised and not ge.alarm and ge.photo_jpeg is None
    assert db_session.scalar(select(func.count()).select_from(NotificationOutbox)) == 0


def test_ac06_unknown_tag_alarms(client, db_session, device_gate, camera, device_event):
    _pass(client, device_gate, device_event, "E2800000000000000000BEEF")
    ge = db_session.scalars(select(GateEvent)).one()
    assert ge.alarm and ge.item_id is None and ge.accession_no is None


def test_ac06_inbound_passage_does_not_alarm(
    client, db_session, device_gate, camera, tagged_item, device_event
):
    _pass(client, device_gate, device_event, tagged_item.active_epc, direction="in")
    assert db_session.scalars(select(GateEvent)).one().alarm is False


def test_ac06_alert_recipients_are_configurable(
    client, db_session, auth_headers, device_gate, camera, tagged_item, device_event
):
    value = {"value": ["desk@example.org", "security@example.org"]}
    client.put("/api/v1/admin/settings/gate_alert_recipients", headers=auth_headers("Admin"), json=value)
    _pass(client, device_gate, device_event, tagged_item.active_epc)
    recipients = sorted(o.recipient for o in db_session.scalars(select(NotificationOutbox)))
    assert recipients == ["desk@example.org", "security@example.org"]


def test_fr07_offline_replay_out_of_order(
    client, db_session, auth_headers, device_gate, camera, tagged_item, device_event
):
    early_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    _pass(client, device_gate, device_event, tagged_item.active_epc, occurred_at=now)
    replay = {"occurred_at": now - timedelta(minutes=10), "offline": True, "event_id": early_id}
    _pass(client, device_gate, device_event, tagged_item.active_epc, **replay)  # replay arrives later
    _pass(client, device_gate, device_event, tagged_item.active_epc, **replay)  # duplicate replay
    events = client.get("/api/v1/gate/events", headers=auth_headers("Librarian")).json()
    assert len(events) == 2 and events[0]["occurred_at"] > events[1]["occurred_at"]
    assert [e["offline_decision"] for e in events] == [False, True]
    assert db_session.scalar(select(func.count()).select_from(NotificationOutbox)) == 2


def test_fr07_footfall_counts_accumulate(client, auth_headers, device_gate, device_event):
    for _ in range(2):
        body = device_event("Footfall", device_type="gate", in_count=3, out_count=1, window_s=60)
        headers = {"X-Device-Key": device_gate.raw_key}
        client.post(f"/api/v1/devices/{device_gate.code}/events", json=body, headers=headers)
    d = client.get("/api/v1/reports/dashboard", headers=auth_headers("Librarian")).json()
    assert d["footfall_today"] == {"in": 6, "out": 2}


def test_nfr02_patron_cannot_see_gate_events(client, patron_headers):
    assert client.get("/api/v1/gate/events", headers=patron_headers).status_code == 403
