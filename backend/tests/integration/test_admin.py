import uuid

import pytest

pytestmark = pytest.mark.db

NEW_USER = {
    "username": "newclerk",
    "display_name": "New Clerk",
    "role": "CirculationClerk",
    "password": "Str0ng-Passw0rd",
}


def test_fr11_admin_creates_user_and_it_is_audited(client, auth_headers):
    h = auth_headers("Admin")
    r = client.post("/api/v1/admin/users", headers=h, json=NEW_USER)
    assert r.status_code == 201 and "password" not in r.text and r.json()["role"] == "CirculationClerk"
    audit = client.get("/api/v1/admin/audit", headers=h, params={"action": "user.create"}).json()
    assert audit["items"][0]["entity_id"] == r.json()["id"]


def test_fr11_new_user_can_sign_in(client, auth_headers):
    client.post("/api/v1/admin/users", headers=auth_headers("Admin"), json=NEW_USER)
    r = client.post("/api/v1/auth/login", json={"username": "newclerk", "password": "Str0ng-Passw0rd"})
    assert r.status_code == 200


@pytest.mark.parametrize("password", ["short1", "alllettersnodigits", "123456789012345"])
def test_fr11_weak_password_rejected(client, auth_headers, password):
    r = client.post(
        "/api/v1/admin/users", headers=auth_headers("Admin"), json={**NEW_USER, "password": password}
    )
    assert r.status_code == 422


def test_fr11_duplicate_username_rejected(client, auth_headers):
    h = auth_headers("Admin")
    client.post("/api/v1/admin/users", headers=h, json=NEW_USER)
    assert client.post("/api/v1/admin/users", headers=h, json=NEW_USER).json()["code"] == "USERNAME_EXISTS"


def test_fr11_deactivated_user_loses_access(client, auth_headers, db_session):
    from app.core.security import create_access_token

    h = auth_headers("Admin")
    user = client.post("/api/v1/admin/users", headers=h, json=NEW_USER).json()
    access = create_access_token(uuid.UUID(user["id"]), "staff", "CirculationClerk")
    token = {"Authorization": f"Bearer {access}"}
    assert client.get("/api/v1/auth/me", headers=token).status_code == 200
    client.patch(f"/api/v1/admin/users/{user['id']}", headers=h, json={"is_active": False})
    assert client.get("/api/v1/auth/me", headers=token).status_code == 401


def test_fr11_auditor_reads_audit_but_cannot_manage_users(client, auth_headers):
    h = auth_headers("Auditor")
    assert client.get("/api/v1/admin/audit", headers=h).status_code == 200
    assert client.post("/api/v1/admin/users", headers=h, json=NEW_USER).status_code == 403
    assert client.get("/api/v1/admin/users", headers=h).status_code == 403


def test_fr11_roles_list_permissions(client, auth_headers):
    roles = client.get("/api/v1/admin/roles", headers=auth_headers("Admin")).json()
    by_name = {r["name"]: r for r in roles}
    assert "migration.run" in by_name["Admin"]["permissions"]
    assert "migration.run" not in by_name["Librarian"]["permissions"]


def test_fr11_settings_round_trip_audited(client, auth_headers):
    h = auth_headers("Admin")
    r = client.put(
        "/api/v1/admin/settings/gate_alert_recipients", headers=h, json={"value": ["desk@example.org"]}
    )
    assert r.status_code == 200
    assert client.get("/api/v1/admin/settings", headers=h).json()["gate_alert_recipients"] == [
        "desk@example.org"
    ]
    audit = client.get("/api/v1/admin/audit", headers=h, params={"action": "setting.update"}).json()
    assert audit["total"] == 1


def test_fr11_unknown_setting_rejected(client, auth_headers):
    r = client.put("/api/v1/admin/settings/root_shell", headers=auth_headers("Admin"), json={"value": 1})
    assert r.status_code == 422 and r.json()["code"] == "SETTING_UNKNOWN"
