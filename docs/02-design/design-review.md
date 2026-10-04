# Design Review: Stage 2

- Date: 2026-10-04
- Scope: requirements package (D1) and architecture package (D2) before the foundation build
- Inputs: SOP; RTM v0.1; assumptions A-01..A-14; all documents in `docs/02-design/`

## Checklist

| Check | Result |
|---|---|
| Every FR, NFR and AC in the RTM maps to at least one designed component | Pass. Module columns are filled; see the RTM |
| Every SOP §6 layer has named components and code locations | Pass. See architecture.md §3 |
| Every unavailable device or service has an interface and a mock | Pass. Staff reader, handheld, gate, smart card, camera, printer, email, SMS, ILMS, NCIP, SIP2 |
| Legacy-data immutability is enforced, not just intended | Pass. DB grants (database-design.md §2) plus checksum tool |
| Security controls cover every NFR 02 item | Pass. Least privilege, secrets, audit, validation, transport; see security-design.md |
| Each acceptance scenario has testable Given/When/Then criteria | Pass. See use-cases.md |
| Offline install, update and rollback path defined | Pass. See ADR-0002 |
| No certification claims | Pass. NCIP/SIP2 described as subsets/boundaries |

## Findings and decisions

| # | Finding | Decision |
|---|---|---|
| 1 | Smart-card login needs a way to bind a reader event to a browser session. | Challenge-response handshake (interface design §2.4); `/auth/smartcard/challenge` endpoint added. |
| 2 | Mirroring legacy records into `nexus` could be mistaken for changing legacy data. | ADR-0005: mirroring copies, never writes back; `legacy_ref` is a soft reference. |
| 3 | Raw SQL is needed for grants, triggers and checksums, which conflicts with the ORM-only rule. | ADR-0003: allowed only in Alembic and `ops/`, enforced by lint. |
| 4 | Linux containers on Windows Server are a compatibility risk (R-03). | ADR-0002 documents the host options; a native Windows packaging goes in the backlog. |
| 5 | Full scope exceeds the time box (R-01). | ADR-0004: acceptance-scenario-first scope; RTM statuses stay honest. |
| 6 | Gate behaviour when the API is down must not lose events or create duplicates. | The simulator queues events with stable `event_id`s; ingest is idempotent (interface design §2.2). |

## Outcome
The design is approved for the foundation build (Stage 3). Implementation follows `docs/00-project-control/implementation-plan.md`.
