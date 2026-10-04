# Stage Gate 2: Requirements and Design (D1–D2)

| Field | Value |
|---|---|
| SOP reference | §9 Stage 2 |
| Branch | `stage/2-design` |
| Gate date | 2026-10-04 |
| Outcome | Approved |

## Exit criteria (SOP §9 Stage 2 bullets)

| # | SOP requirement | Output | Evidence | Met |
|---|---|---|---|---|
| 1 | Prepare use cases and acceptance criteria | 16 use cases; Given/When/Then criteria for AC 01–10 | `docs/01-requirements/use-cases.md` | ☑ |
| 2 | Define the domain model and database schema | ER model, data dictionary, schemas, roles and grants, indexing, backup design | `docs/01-requirements/data-dictionary.md`, `docs/02-design/database-design.md` | ☑ |
| 2 | Define the APIs and event model | REST endpoint catalogue with permissions, device event envelope and command set | `docs/02-design/interface-design.md` §1–2 | ☑ |
| 2 | Define integration contracts | NCIP 2.0 subset, SIP2 boundary, notification, camera, credential and legacy connector interfaces | `docs/02-design/interface-design.md` §3–4 | ☑ |
| 2 | Define security controls | Threat model, RBAC matrix, authentication, data protection, transport, supply chain | `docs/02-design/security-design.md` | ☑ |
| 2 | Define deployment topology | Container topology, ports, offline lifecycle | `docs/02-design/architecture.md` §5, ADR-0002 | ☑ |
| 3 | Create mock contracts for unavailable ILMS and RFID interfaces | Mock behaviour defined for every adapter and device; device/IP table | `docs/02-design/interface-design.md` §2–5 | ☑ |
| 4 | Hold a design review and record decisions | Review checklist, six findings with decisions, ADR-0001..0005 | `docs/02-design/design-review.md`, `docs/02-design/adr/` | ☑ |

## Additional outputs
- Implementation plan for Stages 3–7 and release: `docs/00-project-control/implementation-plan.md`
- RTM updated to v0.2 with module mapping

## Decision
Approved on 2026-10-04. The foundation build (Stage 3) can start from `main` once this branch is merged.
