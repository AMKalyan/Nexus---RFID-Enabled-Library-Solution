import pytest
from sqlalchemy import select

from app.db.models import AuditLog

pytestmark = pytest.mark.db


def test_fr01_create_bib_and_item_then_find_by_accession(client, auth_headers):
    h = auth_headers("Librarian")
    bib = client.post(
        "/api/v1/bibs",
        headers=h,
        json={
            "title": "Practical RFID",
            "author": "K. Finkenzeller",
            "isbn": "9780470695067",
            "pub_year": 2010,
        },
    ).json()
    item = client.post(
        f"/api/v1/bibs/{bib['id']}/items",
        headers=h,
        json={
            "accession_no": "ACC-900001",
            "barcode": "BC90000001",
            "call_no": "621.38 FIN",
            "shelf_code": None,
            "item_type": "lending",
        },
    )
    assert item.status_code == 201
    found = client.get("/api/v1/items", headers=h, params={"accession_no": "ACC-900001"}).json()
    assert found[0]["bib"]["title"] == "Practical RFID"
    by_barcode = client.get("/api/v1/items", headers=h, params={"barcode": "BC90000001"}).json()
    assert by_barcode[0]["accession_no"] == "ACC-900001"


def test_fr01_duplicate_accession_rejected(client, auth_headers, sample_item):
    r = client.post(
        f"/api/v1/bibs/{sample_item.bib_id}/items",
        headers=auth_headers("Librarian"),
        json={"accession_no": sample_item.accession_no, "barcode": "BC-NEW-1", "item_type": "lending"},
    )
    assert r.status_code == 409 and r.json()["code"] == "ACCESSION_EXISTS"


def test_fr01_duplicate_barcode_rejected(client, auth_headers, sample_item):
    r = client.post(
        f"/api/v1/bibs/{sample_item.bib_id}/items",
        headers=auth_headers("Librarian"),
        json={"accession_no": "ACC-777777", "barcode": sample_item.barcode, "item_type": "lending"},
    )
    assert r.status_code == 409 and r.json()["code"] == "BARCODE_EXISTS"


def test_fr01_invalid_isbn_rejected(client, auth_headers):
    r = client.post(
        "/api/v1/bibs", headers=auth_headers("Librarian"), json={"title": "X", "isbn": "9780470695060"}
    )
    assert r.status_code == 422 and r.json()["code"] == "ISBN_INVALID"


def test_fr01_isbn10_with_check_x_accepted(client, auth_headers):
    r = client.post(
        "/api/v1/bibs", headers=auth_headers("Librarian"), json={"title": "X", "isbn": "0-8044-2957-X"}
    )
    assert r.status_code == 201 and r.json()["isbn"] == "080442957X"


def test_fr01_unknown_bib_is_404(client, auth_headers):
    r = client.post(
        "/api/v1/bibs/00000000-0000-0000-0000-000000000000/items",
        headers=auth_headers("Librarian"),
        json={"accession_no": "ACC-123456", "barcode": "BC1", "item_type": "lending"},
    )
    assert r.status_code == 404 and r.json()["code"] == "BIB_NOT_FOUND"


def test_nfr02_clerk_cannot_catalogue(client, auth_headers):
    r = client.post("/api/v1/bibs", headers=auth_headers("CirculationClerk"), json={"title": "X"})
    assert r.status_code == 403


def test_fr01_catalogue_write_is_audited(client, db_session, auth_headers):
    client.post("/api/v1/bibs", headers=auth_headers("Librarian"), json={"title": "Audited"})
    assert db_session.scalars(select(AuditLog).where(AuditLog.action == "bib.create")).first() is not None


def test_fr01_update_bib(client, auth_headers, sample_item):
    h = auth_headers("Librarian")
    r = client.patch(f"/api/v1/bibs/{sample_item.bib_id}", headers=h, json={"edition": "2nd"})
    assert r.status_code == 200 and r.json()["edition"] == "2nd"


def test_fr05_validate_item_reports_problems(client, auth_headers, withdrawn_item, sample_item):
    h = auth_headers("Librarian")
    assert client.post(f"/api/v1/items/{sample_item.id}/validate", headers=h).json()["problems"] == []
    problems = client.post(f"/api/v1/items/{withdrawn_item.id}/validate", headers=h).json()["problems"]
    assert "ITEM_WITHDRAWN" in problems


def test_fr01_spine_label_pdf(client, auth_headers, sample_item):
    r = client.get(f"/api/v1/items/{sample_item.id}/spine-label.pdf", headers=auth_headers("Librarian"))
    assert (
        r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
    )
