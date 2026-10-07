"""AC 01: import a supplied spreadsheet into staging, reject invalid rows, identify duplicates, migrate valid
records, and reconcile source and target counts."""

import pytest
from sqlalchemy import func, select

from app.db.models import AuditLog, Bib, ImportRow, Item

pytestmark = [pytest.mark.db, pytest.mark.acceptance]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload(client, h, path, name="export.xlsx"):
    with open(path, "rb") as f:
        return client.post("/api/v1/migration/batches", headers=h, files={"file": (name, f, XLSX)})


def test_ac01_stage_validate_commit_reconcile(
    client, db_session, auth_headers, sample_xlsx, integrity, ops_env
):
    h = auth_headers("Admin")
    legacy_before = integrity.snapshot()
    staged = upload(client, h, sample_xlsx.path)
    assert staged.status_code == 201 and staged.json()["rows_total"] == 2000
    batch = staged.json()["id"]
    assert (
        db_session.scalar(select(func.count()).select_from(ImportRow).where(ImportRow.batch_id == batch))
        == 2000
    )

    rep = client.post(f"/api/v1/migration/batches/{batch}/validate", headers=h).json()
    m = sample_xlsx.manifest
    assert rep["source"] == m.rows
    assert rep["rejected"] == len(m.invalid_rows)
    assert rep["duplicate"] == len(m.exact_duplicate_rows)
    assert rep["likely_duplicate"] >= len(m.likely_duplicate_rows)
    assert rep["source"] == rep["valid"] + rep["rejected"] + rep["duplicate"] and rep["balanced"]
    assert sum(rep["by_reason"].values()) >= rep["rejected"]
    in_catalogue = select(func.count()).select_from(Item).where(Item.migration_batch_id == batch)
    assert db_session.scalar(in_catalogue) == 0  # validation is a dry run

    done = client.post(f"/api/v1/migration/batches/{batch}/commit", headers=h).json()
    assert done["committed"] == rep["valid"] and done["balanced"] is True
    assert done["backup_file"].endswith(".dump") and (ops_env / done["backup_file"]).exists()
    assert db_session.scalar(in_catalogue) == rep["valid"]
    assert integrity.compare(legacy_before, integrity.snapshot()) == []
    assert (
        db_session.scalars(select(AuditLog).where(AuditLog.action == "migration.commit")).first() is not None
    )


def test_ac01_rejected_rows_listed_with_reasons(client, auth_headers, sample_xlsx, ops_env):
    h = auth_headers("Admin")
    batch = upload(client, h, sample_xlsx.path).json()["id"]
    client.post(f"/api/v1/migration/batches/{batch}/validate", headers=h)
    csv = client.get(f"/api/v1/migration/batches/{batch}/report", headers=h, params={"format": "csv"})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    first_invalid = sample_xlsx.manifest.invalid_rows[0]
    defect = sample_xlsx.manifest.defects[first_invalid]
    assert any(
        line.startswith(f"{first_invalid},rejected,") and defect in line for line in csv.text.splitlines()
    )


def test_ac01_batch_rollback_removes_only_that_batch(client, db_session, auth_headers, sample_xlsx, ops_env):
    h = auth_headers("Admin")
    batch = upload(client, h, sample_xlsx.path).json()["id"]
    client.post(f"/api/v1/migration/batches/{batch}/validate", headers=h)
    client.post(f"/api/v1/migration/batches/{batch}/commit", headers=h)
    other = db_session.scalar(select(func.count()).select_from(Item).where(Item.migration_batch_id.is_(None)))
    r = client.post(f"/api/v1/migration/batches/{batch}/rollback", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "rolled_back"
    assert (
        db_session.scalar(select(func.count()).select_from(Item).where(Item.migration_batch_id == batch)) == 0
    )
    assert (
        db_session.scalar(select(func.count()).select_from(Bib).where(Bib.migration_batch_id == batch)) == 0
    )
    assert (
        db_session.scalar(select(func.count()).select_from(Item).where(Item.migration_batch_id.is_(None)))
        == other
    )


def test_fr10_second_import_of_same_file_is_all_duplicates(client, auth_headers, sample_xlsx, ops_env):
    h = auth_headers("Admin")
    first = upload(client, h, sample_xlsx.path).json()["id"]
    valid = client.post(f"/api/v1/migration/batches/{first}/validate", headers=h).json()["valid"]
    client.post(f"/api/v1/migration/batches/{first}/commit", headers=h)
    second = upload(client, h, sample_xlsx.path).json()["id"]
    rep = client.post(f"/api/v1/migration/batches/{second}/validate", headers=h).json()
    assert rep["valid"] == 0 and rep["duplicate"] == valid + len(sample_xlsx.manifest.exact_duplicate_rows)


def test_fr10_commit_requires_validation(client, auth_headers, sample_xlsx, ops_env):
    h = auth_headers("Admin")
    batch = upload(client, h, sample_xlsx.path).json()["id"]
    r = client.post(f"/api/v1/migration/batches/{batch}/commit", headers=h)
    assert r.status_code == 409 and r.json()["code"] == "BATCH_NOT_VALIDATED"


def test_fr10_csv_upload_supported(client, auth_headers, tmp_path, ops_env):
    path = tmp_path / "small.csv"
    header = (
        "Accession No,Barcode,Title,Author,ISBN,Publisher,Year,Edition,Subjects,Call No,Shelf,Item Type,"
        "Price,Acquired On"
    )
    good = "ACC-700001,BC70000001,Csv Book,Rao,9780470695067,Pub,2001,,,000.1 RAO,A-01,lending,10,2020-01-02"
    bad = ",BC70000002,,Rao,,Pub,2001,,,,,lending,10,"
    path.write_text("\n".join([header, good, bad]) + "\n", encoding="utf-8")
    h = auth_headers("Admin")
    with open(path, "rb") as f:
        batch = client.post(
            "/api/v1/migration/batches", headers=h, files={"file": ("small.csv", f, "text/csv")}
        )
    rep = client.post(f"/api/v1/migration/batches/{batch.json()['id']}/validate", headers=h).json()
    assert (rep["source"], rep["valid"], rep["rejected"]) == (2, 1, 1)


def test_nfr02_upload_rejects_non_spreadsheet(client, auth_headers):
    r = client.post(
        "/api/v1/migration/batches",
        headers=auth_headers("Admin"),
        files={"file": ("x.xlsx", b"MZ\x90\x00not-a-zip", "application/octet-stream")},
    )
    assert r.status_code == 422 and r.json()["code"] == "UPLOAD_TYPE_INVALID"


def test_nfr02_upload_rejects_wrong_columns(client, auth_headers, tmp_path):
    path = tmp_path / "wrong.csv"
    path.write_text("Name,Price\nx,1\n", encoding="utf-8")
    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/migration/batches", headers=auth_headers("Admin"), files={"file": ("wrong.csv", f)}
        )
    assert r.status_code == 422 and r.json()["code"] == "UPLOAD_COLUMNS_MISSING"


def test_nfr02_librarian_cannot_migrate(client, auth_headers, sample_xlsx):
    assert upload(client, auth_headers("Librarian"), sample_xlsx.path).status_code == 403
