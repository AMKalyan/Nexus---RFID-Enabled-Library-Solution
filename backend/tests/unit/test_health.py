from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_nfr07_version_endpoint():
    r = TestClient(create_app(check_db=False)).get("/api/v1/version")
    assert r.status_code == 200
    release = (Path(__file__).resolve().parents[3] / "VERSION").read_text().strip()
    assert r.json()["version"] == release
