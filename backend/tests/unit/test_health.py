from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_nfr07_version_endpoint():
    r = TestClient(create_app(check_db=False)).get("/api/v1/version")
    assert r.status_code == 200
    release = (Path(__file__).resolve().parents[3] / "VERSION").read_text().strip()
    assert r.json()["version"] == release


def test_nfr07_version_reports_build_notes():
    notes = TestClient(create_app(check_db=False)).get("/api/v1/version").json()["build_notes"]
    assert isinstance(notes, str) and notes


def test_nfr07_health_is_503_when_a_check_fails():
    """Docker health checks and the update roll-back decide on the status code, not the body (DEF-016)."""
    app = create_app(check_db=False)
    client = TestClient(app)
    app.state.health_checks.append(lambda: ("database", True))
    assert client.get("/api/v1/health").status_code == 200
    app.state.health_checks.append(lambda: ("outbox", False))
    r = client.get("/api/v1/health")
    assert r.status_code == 503 and r.json() == {
        "status": "degraded",
        "checks": {"database": True, "outbox": False},
    }
