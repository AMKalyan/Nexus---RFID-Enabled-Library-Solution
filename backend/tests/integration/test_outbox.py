from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models import NotificationOutbox
from app.integrations.notify_mock import MockEmail
from app.services.notifications import NotificationsService
from app.worker import run_once

pytestmark = pytest.mark.db

GATE_CONTEXT = {"accession_no": "ACC-000001", "title": "T", "gate": "GATE-01", "time": "now"}


@pytest.fixture(autouse=True)
def outbox_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("OUTBOX_DIR", str(tmp_path))
    MockEmail.reset()
    return tmp_path


@pytest.fixture
def queued_email(db_session):
    rows = NotificationsService(db_session).queue(
        "email", "gate_alert", ["desk@example.org"], GATE_CONTEXT, ("gate_event", "x")
    )
    db_session.flush()
    return rows[0]


def test_fr09_outbox_retries_then_sends(db_session, queued_email, monkeypatch, outbox_dir):
    monkeypatch.setenv("MOCK_EMAIL_FAIL_FIRST", "1")
    now = datetime.now(UTC)
    assert run_once(db_session, now) == 0
    db_session.refresh(queued_email)
    assert queued_email.attempts == 1 and queued_email.status == "queued" and queued_email.last_error
    assert run_once(db_session, now) == 0  # backoff: not due yet
    assert run_once(db_session, now + timedelta(seconds=5)) == 1
    db_session.refresh(queued_email)
    assert queued_email.status == "sent" and queued_email.sent_at is not None
    assert list((outbox_dir / "email").glob("*.eml"))


def test_fr09_gives_up_after_five_attempts(db_session, queued_email, monkeypatch):
    monkeypatch.setenv("MOCK_EMAIL_FAIL_FIRST", "99")
    when = datetime.now(UTC)
    for _ in range(6):
        run_once(db_session, when)
        when += timedelta(minutes=5)
    db_session.refresh(queued_email)
    assert queued_email.status == "failed" and queued_email.attempts == 5


def test_fr09_member_preferences_respected(db_session, sample_member):
    sample_member.notify_email, sample_member.notify_sms, sample_member.notify_print = True, True, False
    context = {"title": "X", "due": "2026-10-10"}
    rows = NotificationsService(db_session).queue_for_member(sample_member, "due_reminder", context)
    assert sorted(r.channel for r in rows) == ["email", "sms"]
    assert {r.recipient for r in rows} == {sample_member.email, sample_member.phone}


def test_fr09_overdue_checkin_queues_notice(client, db_session, auth_headers, overdue_loan):
    h = auth_headers("CirculationClerk")
    client.post("/api/v1/circulation/checkin", headers=h, json={"item": overdue_loan.item.accession_no})
    rows = db_session.scalars(
        select(NotificationOutbox).where(NotificationOutbox.template == "overdue_notice")
    ).all()
    assert len(rows) == 1 and "10.00" in rows[0].body


def test_fr09_outbox_listing_masks_recipients(client, auth_headers, queued_email):
    rows = client.get("/api/v1/notifications/outbox", headers=auth_headers("Auditor")).json()
    assert rows[0]["recipient"] != "desk@example.org" and rows[0]["recipient"].endswith("@example.org")


def test_fr09_print_channel_produces_pdf(db_session, outbox_dir):
    rows = NotificationsService(db_session).queue(
        "print", "due_reminder", ["PRN-01"], {"title": "T", "due": "D"}
    )
    db_session.flush()
    assert run_once(db_session, datetime.now(UTC)) == 1
    pdf = next((outbox_dir / "print").glob("*.pdf"))
    assert pdf.read_bytes()[:4] == b"%PDF" and rows[0].status == "sent"
