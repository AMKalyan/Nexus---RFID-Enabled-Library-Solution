"""FR 12: offline activation by a signed licence file; unlicensed sites are read-only for non-admins."""

import importlib.util
import json
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import licence
from app.core.config import get_settings

KEY = "k" * 40
OPS_LICENCE = Path(__file__).resolve().parents[3] / "ops" / "licence.py"


def issued(key: str = KEY, expires: date | None = None) -> dict:
    payload = {
        "site": "Test Library",
        "expires": (expires or date.today() + timedelta(days=30)).isoformat(),
        "features": ["circulation"],
    }
    return {**payload, "sig": licence.sign(payload, key)}


def test_fr12_valid_tampered_and_expired_licences():
    assert licence.check(issued(), KEY) == "valid"
    assert licence.check({**issued(), "site": "Other Library"}, KEY) == "invalid"
    assert licence.check(issued(), "x" * 40) == "invalid"
    assert licence.check(issued(expires=date.today() - timedelta(days=1)), KEY) == "expired"


def test_fr12_api_accepts_licences_issued_by_the_ops_tool():
    spec = importlib.util.spec_from_file_location("ops_licence", OPS_LICENCE)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    payload = {"site": "Central", "expires": "2030-01-01", "features": ["rfid"]}
    assert licence.check({**payload, "sig": tool.sign(payload, KEY)}, KEY) == "valid"


def test_fr12_status_from_file(tmp_path):
    path = tmp_path / "licence.json"
    assert licence.status_from_file(path, KEY) == "missing"
    path.write_text("not json", encoding="utf-8")
    assert licence.status_from_file(path, KEY) == "invalid"
    path.write_text(json.dumps(issued()), encoding="utf-8")
    assert licence.status_from_file(path, KEY) == "valid"


@pytest.fixture
def production(monkeypatch, tmp_path):
    """The app in production mode with strong secrets and a licence file path under tmp_path."""
    env = {
        "ENVIRONMENT": "production",
        "JWT_SECRET": "j" * 64,
        "LICENCE_KEY": KEY,
        "LICENCE_FILE": str(tmp_path / "licence.json"),
        "DATABASE_URL": "postgresql+psycopg://nexus_app:Strong-App-Pass-1@db:5432/nexus",
        "OWNER_DATABASE_URL": "postgresql+psycopg://nexus_owner:Strong-Owner-Pass-1@db:5432/nexus",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    yield tmp_path / "licence.json"
    get_settings.cache_clear()


def not_licence_refused(r) -> bool:
    return r.status_code != 403 or r.json().get("code") != "LICENCE_REQUIRED"


def client_and_headers():
    from app.core.security import create_access_token
    from app.main import create_app

    client = TestClient(create_app(check_db=False))

    def bearer(role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(uuid.uuid4(), 'staff', role)}"}

    return client, bearer


def test_fr12_unlicensed_installation_is_read_only_for_non_admins(production):
    client, bearer = client_and_headers()
    assert client.get("/api/v1/version").json()["licence"] == "missing"
    r = client.post("/api/v1/circulation/checkout", headers=bearer("CirculationClerk"), json={})
    assert r.status_code == 403 and r.json()["code"] == "LICENCE_REQUIRED"
    assert "licence" in r.json()["error"].lower()
    device = client.post("/api/v1/devices/GATE-01/events", json={})
    assert device.status_code == 403 and device.json()["code"] == "LICENCE_REQUIRED"
    # Sign-in and administration still work, so the site can be activated.
    assert not_licence_refused(client.post("/api/v1/auth/login", json={}))
    assert not_licence_refused(client.post("/api/v1/circulation/checkout", headers=bearer("Admin"), json={}))


def test_fr12_licensed_installation_is_not_restricted(production):
    production.write_text(json.dumps(issued()), encoding="utf-8")
    client, bearer = client_and_headers()
    assert client.get("/api/v1/version").json()["licence"] == "valid"
    r = client.post("/api/v1/circulation/checkout", headers=bearer("CirculationClerk"), json={})
    assert not_licence_refused(r)


def test_fr12_development_is_never_restricted():
    client, bearer = client_and_headers()
    r = client.post("/api/v1/circulation/checkout", headers=bearer("CirculationClerk"), json={})
    assert not_licence_refused(r)
