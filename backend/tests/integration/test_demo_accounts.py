"""Public demo instances can show sign-in details for every role except Admin; real installations never do."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings

pytestmark = pytest.mark.db
PUBLIC_PASSWORD = "demo-visitor-2026"


def test_nfr02_demo_accounts_are_off_by_default(client):
    assert Settings(_env_file=None).demo_public_accounts is False
    assert client.get("/api/v1/auth/demo-accounts").json() == []


def test_nfr02_demo_accounts_need_a_password_of_at_least_twelve_characters():
    with pytest.raises(ValidationError, match="DEMO_PUBLIC_PASSWORD"):
        Settings(_env_file=None, demo_public_accounts=True, demo_public_password="short")


@pytest.fixture
def public_demo(monkeypatch):
    monkeypatch.setenv("DEMO_PUBLIC_ACCOUNTS", "true")
    monkeypatch.setenv("DEMO_PUBLIC_PASSWORD", PUBLIC_PASSWORD)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_nfr02_demo_accounts_list_every_role_except_admin(public_demo, client):
    accounts = client.get("/api/v1/auth/demo-accounts").json()
    assert {a["role"] for a in accounts} == {"Librarian", "CirculationClerk", "Auditor", "Patron"}
    assert all(a["password"] == PUBLIC_PASSWORD for a in accounts)
    assert "admin" not in {a["username"] for a in accounts}


def test_nfr02_seed_gives_public_accounts_the_demo_password_and_keeps_admin_secret(
    public_demo, client, db_session
):
    from app.db.seed import seed_demo
    from tests.factories import make_member

    make_member(db_session).card_no = "B00001"
    db_session.flush()
    creds = seed_demo(db_session)
    db_session.flush()

    for username in ("librarian", "clerk", "auditor", "B00001"):
        r = client.post("/api/v1/auth/login", json={"username": username, "password": PUBLIC_PASSWORD})
        assert r.status_code == 200, username
    assert (
        client.post("/api/v1/auth/login", json={"username": "admin", "password": PUBLIC_PASSWORD}).status_code
        == 401
    )
    assert creds["staff admin (Admin) password"] != PUBLIC_PASSWORD
