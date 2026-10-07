"""AC 05: use a handheld-reader mock to inventory a shelf and report missing and misplaced items with
visible and audible confirmation events."""

import pytest

from app.middleware_rfid.commands import bus
from app.middleware_rfid.live_hub import hub

pytestmark = [pytest.mark.db, pytest.mark.acceptance]


def _start(client, h, device, shelf="A-01"):
    r = client.post(
        "/api/v1/inventory/sessions", headers=h, json={"shelf_code": shelf, "device_code": device.code}
    )
    assert r.status_code == 201
    return r.json()


def _sweep(client, device, device_event, session_id, epcs):
    body = device_event("TagsRead", device_type="handheld", epcs=epcs, session_id=session_id, mode="bulk")
    return client.post(
        f"/api/v1/devices/{device.code}/events", json=body, headers={"X-Device-Key": device.raw_key}
    )


def test_ac05_shelf_inventory_reports_missing_and_misplaced(
    client, auth_headers, device_hh, shelf_world, device_event
):
    h = auth_headers("Librarian")
    bus.poll(device_hh.code)  # start with an empty command queue
    sess = _start(client, h, device_hh)
    assert sess["expected"] == 6
    present, foreign = shelf_world.a01_epcs[:-2], shelf_world.b01_epcs[0]  # two left off; one from B-01
    assert _sweep(client, device_hh, device_event, sess["id"], [*present, foreign]).status_code == 202

    live = client.get(f"/api/v1/inventory/sessions/{sess['id']}", headers=h).json()
    confirmations = {r["epc"]: (r["light"], r["beep"]) for r in live["reads"]}
    assert confirmations[present[0]] == ("green", "ok")
    assert confirmations[foreign] == ("amber", "warn")

    report = client.post(f"/api/v1/inventory/sessions/{sess['id']}/close", headers=h).json()
    assert sorted(m["epc"] for m in report["missing"]) == sorted(shelf_world.a01_epcs[-2:])
    assert report["misplaced"][0]["epc"] == foreign and report["misplaced"][0]["home_shelf"] == "B-01"
    assert len(report["found"]) == 4


def test_ac05_handheld_receives_audible_and_visible_commands(
    client, auth_headers, device_hh, shelf_world, device_event
):
    bus.poll(device_hh.code)
    sess = _start(client, auth_headers("Librarian"), device_hh)
    _sweep(
        client,
        device_hh,
        device_event,
        sess["id"],
        [shelf_world.a01_epcs[0], shelf_world.b01_epcs[0], "E2800000000000000000DEAD"],
    )
    commands = [(c.command, c.params) for c in bus.poll(device_hh.code)]
    assert ("Beep", {"pattern": "ok"}) in commands
    assert ("Beep", {"pattern": "warn"}) in commands
    assert ("Beep", {"pattern": "error"}) in commands
    assert ("Light", {"color": "amber", "ms": 400}) in commands


def test_ac05_reads_are_published_live(client, auth_headers, device_hh, shelf_world, device_event):
    sess = _start(client, auth_headers("Librarian"), device_hh)
    _sweep(client, device_hh, device_event, sess["id"], shelf_world.a01_epcs[:1])
    last = hub.recent("inventory.read")[-1]["data"]
    assert last["session_id"] == sess["id"] and last["result"] == "found" and last["light"] == "green"


def test_fr06_repeat_reads_counted_once(client, auth_headers, device_hh, shelf_world, device_event):
    h = auth_headers("Librarian")
    sess = _start(client, h, device_hh)
    for _ in range(2):
        _sweep(client, device_hh, device_event, sess["id"], shelf_world.a01_epcs[:1])
    assert len(client.get(f"/api/v1/inventory/sessions/{sess['id']}", headers=h).json()["reads"]) == 1


def test_fr06_items_on_loan_are_not_reported_missing(
    client, auth_headers, device_hh, shelf_world, device_event, db_session
):
    from app.db.models import ItemStatus

    shelf_world.a01_items[0].status = ItemStatus.on_loan
    db_session.flush()
    h = auth_headers("Librarian")
    sess = _start(client, h, device_hh)
    _sweep(client, device_hh, device_event, sess["id"], shelf_world.a01_epcs[1:])
    report = client.post(f"/api/v1/inventory/sessions/{sess['id']}/close", headers=h).json()
    assert report["missing"] == []


def test_fr06_mark_missing_updates_item_status(
    client, auth_headers, device_hh, shelf_world, device_event, db_session
):
    h = auth_headers("Librarian")
    sess = _start(client, h, device_hh)
    _sweep(client, device_hh, device_event, sess["id"], shelf_world.a01_epcs[:-1])
    client.post(f"/api/v1/inventory/sessions/{sess['id']}/close", headers=h)
    r = client.post(f"/api/v1/inventory/sessions/{sess['id']}/mark-missing", headers=h)
    assert r.json()["marked"] == 1
    db_session.refresh(shelf_world.a01_items[-1])
    assert shelf_world.a01_items[-1].status == "missing"


def test_fr06_closed_session_rejects_reads(client, auth_headers, device_hh, shelf_world, device_event):
    h = auth_headers("Librarian")
    sess = _start(client, h, device_hh)
    client.post(f"/api/v1/inventory/sessions/{sess['id']}/close", headers=h)
    r = _sweep(client, device_hh, device_event, sess["id"], shelf_world.a01_epcs[:1])
    assert r.status_code == 202 and r.json()["result"]["error"] == "INVENTORY_CLOSED"


def test_fr06_session_needs_a_handheld(client, auth_headers, device_gate):
    r = client.post(
        "/api/v1/inventory/sessions",
        headers=auth_headers("Librarian"),
        json={"shelf_code": "A-01", "device_code": device_gate.code},
    )
    assert r.status_code == 422 and r.json()["code"] == "DEVICE_NOT_HANDHELD"
