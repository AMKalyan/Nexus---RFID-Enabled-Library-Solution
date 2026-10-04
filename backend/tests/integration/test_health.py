import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.db


def test_nfr07_health_checks_database_and_reports_migration(migrated_db):
    client = TestClient(create_app(check_db=True))
    health = client.get("/api/v1/health").json()
    assert health["status"] == "ok" and health["checks"]["database"] is True
    assert client.get("/api/v1/version").json()["alembic_rev"] is not None
