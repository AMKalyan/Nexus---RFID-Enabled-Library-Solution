"""AC 02: create or locate a bibliographic item, validate it, associate a mock RFID tag, and display the
tag-to-item relationship."""

import pytest
from sqlalchemy import select

from app.db.models import AuditLog
from app.middleware_rfid.live_hub import hub

pytestmark = [pytest.mark.db, pytest.mark.acceptance]
EPC1, EPC2, EPC3, EPC9 = (f"E28011606000020000000{n:03d}" for n in (1, 2, 3, 9))


def _tag(client, h, epc, **target):
    return client.post("/api/v1/tags", headers=h, json={"epc": epc, **target})


def test_ac02_associate_tag_and_show_relationship(client, auth_headers, sample_item, db_session):
    h = auth_headers("Librarian")
    assert client.post(f"/api/v1/items/{sample_item.id}/validate", headers=h).json()["problems"] == []
    r = _tag(client, h, EPC1, target_type="item", item_id=str(sample_item.id))
    assert r.status_code == 201 and r.json()["security_bit"] is True
    item = client.get(f"/api/v1/items/{sample_item.id}", headers=h).json()
    assert item["active_tag"]["epc"] == EPC1
    tag = client.get(f"/api/v1/tags/{EPC1}", headers=h).json()
    assert tag["item"]["accession_no"] == sample_item.accession_no and tag["item"]["title"] == "Sample Title"
    assert db_session.scalars(select(AuditLog).where(AuditLog.action == "tag.associate")).first() is not None


def test_ac02_create_bib_item_and_tag_end_to_end(client, auth_headers, db_session):
    from tests.factories import ensure_shelf

    ensure_shelf(db_session, "B-01")
    h = auth_headers("Librarian")
    bib = client.post(
        "/api/v1/bibs", headers=h, json={"title": "RFID Handbook", "isbn": "9780470695067"}
    ).json()
    body = {
        "accession_no": "ACC-555001",
        "barcode": "BC55500001",
        "call_no": "621.38 FIN",
        "shelf_code": "B-01",
        "item_type": "lending",
    }
    item = client.post(f"/api/v1/bibs/{bib['id']}/items", headers=h, json=body).json()
    assert _tag(client, h, EPC3, target_type="item", item_id=item["id"]).status_code == 201
    assert (
        client.get("/api/v1/items", headers=h, params={"epc": EPC3}).json()[0]["accession_no"] == "ACC-555001"
    )


def test_ac02_withdrawn_item_cannot_be_tagged(client, auth_headers, withdrawn_item):
    r = _tag(client, auth_headers("Librarian"), EPC2, target_type="item", item_id=str(withdrawn_item.id))
    assert (
        r.status_code == 422
        and r.json()["code"] == "TAG_TARGET_INVALID"
        and "ITEM_WITHDRAWN" in r.json()["error"]
    )


def test_ac02_retag_retires_previous(client, auth_headers, tagged_item):
    h = auth_headers("Librarian")
    old = tagged_item.active_epc
    assert _tag(client, h, EPC3, target_type="item", item_id=str(tagged_item.id)).status_code == 201
    history = client.get(f"/api/v1/items/{tagged_item.id}", headers=h).json()["tag_history"]
    assert {t["epc"]: t["status"] for t in history} == {old: "retired", EPC3: "active"}
    assert next(t for t in history if t["epc"] == old)["retire_reason"] == "retagged"


def test_fr05_epc_already_active_elsewhere(client, auth_headers, tagged_item, sample_item):
    r = _tag(
        client,
        auth_headers("Librarian"),
        tagged_item.active_epc,
        target_type="item",
        item_id=str(sample_item.id),
    )
    assert r.status_code == 409 and r.json()["code"] == "TAG_IN_USE"
    items = client.get(
        "/api/v1/items", headers=auth_headers("Librarian"), params={"epc": tagged_item.active_epc}
    ).json()
    assert items[0]["id"] == str(tagged_item.id)


def test_fr05_member_card_tag(client, auth_headers, sample_member):
    r = _tag(client, auth_headers("Librarian"), EPC9, target_type="member", member_id=str(sample_member.id))
    assert r.status_code == 201
    assert (
        client.get(f"/api/v1/tags/{EPC9}", headers=auth_headers("Librarian")).json()["member"]["card_no"]
        == sample_member.card_no
    )  # noqa: E501


def test_fr05_target_must_match_type(client, auth_headers, sample_item):
    r = _tag(client, auth_headers("Librarian"), EPC9, target_type="member", item_id=str(sample_item.id))
    assert r.status_code == 422


def test_fr05_tag_on_loan_item_has_security_bit_off(client, auth_headers, active_loan):
    h = auth_headers("Librarian")
    r = _tag(client, h, EPC2, target_type="item", item_id=str(active_loan.item_id))
    assert r.status_code == 201 and r.json()["security_bit"] is False


def test_fr05_retire_and_monitor_tags(client, auth_headers, tagged_item):
    h = auth_headers("Librarian")
    r = client.post(f"/api/v1/tags/{tagged_item.active_epc}/retire", headers=h, json={"reason": "damaged"})
    assert r.status_code == 200 and r.json()["status"] == "retired"
    retired = client.get("/api/v1/tags", headers=h, params={"status": "retired"}).json()
    assert tagged_item.active_epc in [t["epc"] for t in retired]


def test_fr05_staff_reader_publishes_resolved_reads(client, device_staff, tagged_item, device_event):
    body = device_event(
        "TagsRead",
        device_type="staff_station",
        epcs=[tagged_item.active_epc, "E2800000000000000000FFFF"],
        mode="single",
    )
    r = client.post(
        f"/api/v1/devices/{device_staff.code}/events",
        json=body,
        headers={"X-Device-Key": device_staff.raw_key},
    )
    assert r.status_code == 202
    reads = hub.recent("tag.read")[-1]["data"]["reads"]
    assert reads[0]["accession_no"] == tagged_item.accession_no and reads[1]["unknown"] is True


def test_nfr02_clerk_cannot_tag(client, auth_headers, sample_item):
    r = _tag(client, auth_headers("CirculationClerk"), EPC1, target_type="item", item_id=str(sample_item.id))
    assert r.status_code == 403
