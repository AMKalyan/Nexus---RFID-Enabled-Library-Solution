# ADR-0005: Read-only legacy integration through references

- Status: Accepted
- Date: 2026-10-04

## Context
NFR 01 forbids modifying, deleting or corrupting existing library records. No real ILMS is available (A-01).

## Decision
- Existing records live in the `legacy_ilms` schema, owned by a role the application cannot use.
- The application role has `SELECT` only.
- Nexus mirrors legacy bibs, items and borrowers into its own tables on demand, through `LegacyIlmsConnector`, storing `legacy_ref`.
- All new state (tags, loans, fines, events) is written only to `nexus`.
- Write-back to a real ILMS is a future adapter concern, handled through NCIP/SIP2.

## Consequences
- Legacy immutability is guaranteed by the database. Tests and checksums prove it (AC 10).
- Mirrored records can drift from the source. A re-sync job is listed in the backlog.
