"""Fingerprint the simulated existing ILMS so any change to it can be proven (AC 10).

For every table in the legacy schema: the row count and a SHA-256 over all rows serialised as JSON, in
primary-key order. Two snapshots are equal only if no row was added, removed or changed.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Connection, create_engine, text

from app.core.config import get_settings

SCHEMA = "legacy_ilms"

_TABLES = text(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = :schema AND table_type = 'BASE TABLE' ORDER BY table_name"
)
_PK = text(
    "SELECT a.attname FROM pg_index i "
    "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
    "WHERE i.indrelid = CAST(:qualified AS regclass) AND i.indisprimary ORDER BY a.attnum"
)


def _quote(identifier: str) -> str:
    """Quote an identifier read from the catalogue (never from user input)."""
    return '"' + identifier.replace('"', '""') + '"'


def snapshot_connection(conn: Connection) -> dict[str, dict[str, int | str]]:
    result: dict[str, dict[str, int | str]] = {}
    for (table,) in conn.execute(_TABLES, {"schema": SCHEMA}):
        qualified = f"{_quote(SCHEMA)}.{_quote(table)}"
        pk = [r[0] for r in conn.execute(_PK, {"qualified": qualified})]
        order = ", ".join(_quote(c) for c in pk) or "1"
        digest, rows = hashlib.sha256(), 0
        # Identifiers come from the system catalogue and are quoted (ADR-0003); no user input here.
        query = text(f"SELECT row_to_json(t)::text FROM {qualified} AS t ORDER BY {order}")  # noqa: S608  # nosec B608
        for (row,) in conn.execution_options(stream_results=True).execute(query):
            digest.update(row.encode())
            digest.update(b"\n")
            rows += 1
        result[table] = {"rows": rows, "sha256": digest.hexdigest()}
    return result


def snapshot(owner_url: str | None = None) -> dict[str, dict[str, int | str]]:
    engine = create_engine(
        owner_url or os.environ.get("OPS_DATABASE_URL") or get_settings().owner_database_url
    )
    try:
        with engine.connect() as conn:
            return snapshot_connection(conn)
    finally:
        engine.dispose()


def compare(before: dict, after: dict) -> list[str]:
    """Tables whose rows differ between two snapshots (including added or dropped tables)."""
    return sorted(t for t in set(before) | set(after) if before.get(t) != after.get(t))


def write_report(snap: dict, directory: Path | str, label: str) -> Path:
    path = Path(directory) / f"integrity-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{label}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema": SCHEMA, "taken_at": datetime.now(UTC).isoformat(), "tables": snap}, indent=2),
        encoding="utf-8",
    )
    return path
