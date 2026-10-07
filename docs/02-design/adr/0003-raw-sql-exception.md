# ADR-0003: Limited raw SQL for DDL, grants and integrity checks

- Status: Accepted
- Date: 2026-10-04

## Context
The engineering standards require all queries to go through the ORM with bound parameters. Some necessary work can't be expressed through the ORM: role creation and grants, triggers for full-text indexing, and table-wide checksum queries over the legacy schema.

## Decision
`sqlalchemy.text()` is allowed only:
- inside Alembic migration scripts,
- in model DDL helpers (`sqlalchemy.text` used as a partial-index predicate or column server default), and
- in operations tooling: `ops/` (integrity, backup helpers) and the seed command `app/db/seed.py`, which runs `SET ROLE legacy_owner` to load the simulated existing ILMS.

Values are always bound parameters. Identifiers (schema and table names) come from a fixed allow-list in code, never from user input. Application code (`backend/app/api`, `services`, `middleware_rfid`, `interop`, `integrations`) must not use `text()`; the test `test_adr0003_no_raw_sql_in_application_code` enforces this.

## Consequences
- The security rule holds for everything that processes user input.
- DDL stays readable and reviewable in migrations.
