"""Regression: the API published with the last release must still be served (NFR 05)."""

import json
import pathlib

from fastapi.testclient import TestClient

from app.main import create_app

SNAPSHOT = pathlib.Path(__file__).parents[3] / "docs" / "08-operations" / "openapi.json"


def operations(spec: dict) -> set[tuple[str, str]]:
    return {(path, method) for path, ops in spec["paths"].items() for method in ops}


def current_spec() -> dict:
    return TestClient(create_app(check_db=False)).get("/api/openapi.json").json()


def test_nfr05_no_endpoint_removed_since_last_release():
    published = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert operations(published) - operations(current_spec()) == set()


def test_nfr05_published_snapshot_is_current():
    """New endpoints must be exported to docs/08-operations/openapi.json so the API guide stays complete."""
    published = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert operations(current_spec()) - operations(published) == set()
