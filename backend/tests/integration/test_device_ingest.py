import uuid

import pytest
from sqlalchemy import func, select

from app.db.models import AuditLog, DeviceEvent

pytestmark = pytest.mark.db


def _post(client, device, body):
    return client.post(
        f"/api/v1/devices/{device.code}/events", json=body, headers={"X-Device-Key": device.raw_key}
    )


def test_fr03_event_requires_device_key(client, device_hh, device_event):
    r = client.post(
        f"/api/v1/devices/{device_hh.code}/events", json=device_event(), headers={"X-Device-Key": "wrong"}
    )
    assert r.status_code == 401 and r.json()["code"] == "ERR_DEVICE_AUTH"
    assert (
        client.post(
            "/api/v1/devices/NOPE/events", json=device_event(), headers={"X-Device-Key": "x"}
        ).status_code
        == 401
    )


def test_fr03_duplicate_event_ignored(client, db_session, device_hh, device_event):
    body = device_event()
    assert _post(client, device_hh, body).status_code == 202
    second = _post(client, device_hh, body)
    assert second.status_code == 200 and second.json()["status"] == "duplicate"
    q = (
        select(func.count())
        .select_from(DeviceEvent)
        .where(DeviceEvent.event_id == uuid.UUID(body["event_id"]))
    )
    assert db_session.scalar(q) == 1


def test_fr03_heartbeat_marks_device_online(client, auth_headers, device_hh, device_event):
    _post(client, device_hh, device_event())
    devices = client.get("/api/v1/devices", headers=auth_headers("Librarian")).json()
    assert next(d for d in devices if d["code"] == device_hh.code)["status"] == "online"


def test_fr03_silent_device_is_offline(client, auth_headers, device_gate):
    devices = client.get("/api/v1/devices", headers=auth_headers("Librarian")).json()
    assert next(d for d in devices if d["code"] == device_gate.code)["status"] == "offline"


def test_fr03_malformed_epc_rejected(client, device_hh, device_event):
    assert _post(client, device_hh, device_event("TagsRead", epcs=["<bad>"])).status_code == 422


def test_fr03_device_type_must_match_registry(client, device_hh, device_event):
    r = _post(client, device_hh, device_event(device_type="gate"))
    assert r.status_code == 422 and r.json()["code"] == "DEVICE_TYPE_MISMATCH"


def test_fr03_unknown_event_type_rejected(client, device_hh, device_event):
    assert _post(client, device_hh, device_event("SelfDestruct")).status_code == 422


def test_fr03_event_without_handler_is_stored(client, db_session, device_hh, device_event):
    body = device_event("TagsRead", epcs=["E2801160600002000000AAAA"], mode="single")
    assert _post(client, device_hh, body).status_code == 202
    ev = db_session.scalars(
        select(DeviceEvent).where(DeviceEvent.event_id == uuid.UUID(body["event_id"]))
    ).one()
    assert ev.processed_at is not None and ev.payload["mode"] == "single"


def test_fr11_admin_registers_device_and_key_shown_once(client, db_session, auth_headers, device_event):
    h = auth_headers("Admin")
    body = {"code": "HH-09", "device_type": "handheld", "name": "Spare handheld", "location": "Stacks",
            "ip_address": "10.10.20.29"}  # fmt: skip
    r = client.post("/api/v1/devices", headers=h, json=body)
    assert r.status_code == 201 and len(r.json()["api_key"]) >= 24
    key = r.json()["api_key"]
    listed = client.get("/api/v1/devices", headers=h).json()
    assert "api_key" not in str(listed)
    ok = client.post("/api/v1/devices/HH-09/events", json=device_event(), headers={"X-Device-Key": key})
    assert ok.status_code == 202
    assert (
        db_session.scalars(select(AuditLog).where(AuditLog.action == "device.register")).first() is not None
    )


def test_nfr02_librarian_cannot_register_devices(client, auth_headers):
    body = {"code": "X-1", "device_type": "gate", "name": "x"}
    assert client.post("/api/v1/devices", headers=auth_headers("Librarian"), json=body).status_code == 403
