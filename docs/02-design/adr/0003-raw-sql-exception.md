# ADR-0003: Limited raw SQL for DDL, grants and integrity checks

- Status: Accepted
- Date: 2026-10-04

## Context
The engineering standards require all queries to go through the ORM with bound parameters. Some necessary work can't be expressed through the ORM: role creation and grants, triggers for full-text indexing, and table-wide checksum queries over the legacy schema.

## Decision
`sqlalchemy.text()` is allowed only:
- inside Alembic migration scripts, and
- in `ops/` tooling (integrity, backup helpers).

Values are always bound parameters. Identifiers (schema and table names) come from a fixed allow-list in code, never from user input. Application code (`backend/app/api`, `services`, `middleware_rfid`, `interop`, `integrations`) must not use `text()`; a lint check enforces this.

## Consequences
- The security rule holds for everything that processes user input.
- DDL stays readable and reviewable in migrations.
