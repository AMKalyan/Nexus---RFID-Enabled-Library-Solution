"""Operations tooling: backups, restores and legacy-data integrity checks (NFR 01, AC 10).

This package runs as the database owner and may use raw SQL with bound parameters and quoted identifiers
(ADR-0003). It is not imported by request-handling code except to take a backup before a migration.
"""
