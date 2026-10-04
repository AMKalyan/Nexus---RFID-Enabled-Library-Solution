import pytest
from fastapi.testclient import TestClient

from app.core.ratelimit import limiter
from app.db.base import get_session
from app.db.models import Role
from app.main import create_app
from tests.factories import make_member, make_staff

pytestmark = pytest.mark.db


@pytest.fixture
def client(db_session):
    app = create_app(check_db=False)
    app.dependency_overrides[get_session] = lambda: db_session
    limiter.reset()
    return TestClient(app)


def _login(client, username, password="Passw0rd!x"):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_nfr02_login_success_and_me(client, db_session):
    make_staff(db_session, "Librarian", username="lib1")
    r = _login(client, "lib1")
    assert r.status_code == 200
    me = client.get("/api/v1/auth/me", headers=_bearer(r.json()["access_token"]))
    assert me.json()["role"] == "Librarian" and "catalog.write" in me.json()["permissions"]


def test_nfr02_bad_password_generic_error(client, db_session):
    make_staff(db_session, "Librarian", username="lib2")
    for username in ("lib2", "nobody"):
        r = _login(client, username, "wrong")
        assert r.status_code == 401 and r.json()["code"] == "INVALID_CREDENTIALS"


def test_nfr02_login_rate_limited(client):
    codes = [_login(client, "x", "y").status_code for _ in range(11)]
    assert codes[-1] == 429


def test_nfr02_refresh_rotation_and_reuse_detection(client, db_session):
    make_staff(db_session, "CirculationClerk", username="clerk1")
    first = _login(client, "clerk1").json()["refresh_token"]
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert second.status_code == 200
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert reuse.status_code == 401 and reuse.json()["code"] == "ERR_TOKEN_REUSED"
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": second.json()["refresh_token"]})
    assert again.status_code == 401


def test_nfr02_role_change_effective_immediately(client, db_session):
    user = make_staff(db_session, "Admin", username="adm1")
    headers = _bearer(_login(client, "adm1").json()["access_token"])
    assert "admin.users.write" in client.get("/api/v1/auth/me", headers=headers).json()["permissions"]
    user.role_id = db_session.query(Role).filter_by(name="Auditor").one().id
    db_session.flush()
    assert "admin.users.write" not in client.get("/api/v1/auth/me", headers=headers).json()["permissions"]


def test_nfr02_patron_logs_in_with_card_number(client, db_session):
    member = make_member(db_session, password="Passw0rd!x")
    r = _login(client, member.card_no)
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=_bearer(r.json()["access_token"])).json()["role"] == "Patron"


def test_nfr02_missing_or_garbage_token_is_401(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=_bearer("not.a.jwt")).status_code == 401


def test_nfr02_logout_revokes_refresh_token(client, db_session):
    make_staff(db_session, "Librarian", username="lib3")
    tokens = _login(client, "lib3").json()
    client.post(
        "/api/v1/auth/logout",
        headers=_bearer(tokens["access_token"]),
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 401
    )


def test_nfr02_login_attempts_are_audited_without_username(client, db_session):
    from sqlalchemy import select

    from app.db.models import AuditLog

    make_staff(db_session, "Librarian", username="lib4")
    _login(client, "lib4")
    _login(client, "lib4", "wrong")
    rows = db_session.scalars(select(AuditLog).where(AuditLog.action.like("auth.login.%"))).all()
    assert {r.action for r in rows} == {"auth.login.success", "auth.login.failure"}
    assert all("lib4" not in str(r.details) for r in rows)
