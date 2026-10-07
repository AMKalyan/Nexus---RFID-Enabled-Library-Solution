# Stage Gate 4: Core Library Functions (D4–D5)

| Field | Value |
|---|---|
| SOP reference | §9 Stage 4 |
| Branch | `stage/4-core` |
| Gate date | 2026-10-07 |
| Outcome | Approved |

## Exit criteria (SOP §9 Stage 4 bullets)

| SOP requirement | Output | Evidence | Met |
|---|---|---|---|
| Implement cataloguing | Bibliographic records and items with ISBN-10/13 checksum validation, unique accession numbers and barcodes, lookup by accession, barcode or tag EPC; spine-label PDF | `backend/app/services/catalog.py`; `tests/integration/test_catalog.py` (11 tests) | ☑ |
| Implement members | Member records, search, block/unblock with reason, patron-card PDF, contact details masked without personal-data permission | `backend/app/services/members.py`, `api/v1/members.py`; `tests/integration/test_members.py` (8 tests) | ☑ |
| Implement circulation | Check-out, renewal, check-in and due-date enquiry through one service; item row lock prevents double issue; security bit follows loan state | `backend/app/services/circulation.py`; `tests/integration/test_circulation.py` (11 tests, incl. a real two-thread race) | ☑ |
| Implement fines | Overdue fines on return (calendar days × category rate); pay and waive with audit | `backend/app/services/fines.py`; `test_fr04_overdue_checkin_raises_fine`, `test_fr04_fines_pay_and_waive` | ☑ |
| Implement restrictions | Pure policy engine: blocked or expired member, reference-only, fine limit, loan and renewal limits, configurable per category | `backend/app/services/policy.py`; `tests/unit/test_policy.py` (10), `tests/acceptance/test_ac04_circulation_blocks.py` (5) | ☑ |
| Implement search | Ranked full-text OPAC search with author, year and availability filters; virtual bookshelf | `backend/app/services/search.py`; `tests/integration/test_opac.py` (9) | ☑ |
| Implement reporting and dashboards | Dashboard statistics; seven filterable reports with CSV and PDF export; PII masking; CSV formula neutralisation | `backend/app/services/reports.py`, `export.py`; `tests/acceptance/test_ac08_reports.py` (14) | ☑ |
| Demonstrate key user journeys | Sign-in by role, dashboard, reference-item refusal, issue and return, public OPAC, session reset | `docs/06-testing/user-journeys.md` (UJ-01..06) | ☑ |
| Record defects | DEF-004 (charting library deprecation warnings) found and closed | `docs/00-project-control/defect-log.md` | ☑ |
| Update the traceability matrix | RTM v0.4: FR 04, FR 08, AC 04, AC 08 Done; FR 01, FR 02 Partial with scope notes; FR 11 in progress | `docs/01-requirements/rtm.md` | ☑ |
| Update API documentation | OpenAPI exported (39 paths) | `docs/08-operations/openapi.json`; live at `/api/docs` | ☑ |

## Additional outputs
- Administration API and screens: staff users (password policy, deactivation), roles, circulation policies, settings allow-list, audit-log query (`tests/integration/test_admin.py`, 11 tests).
- UI screens: OPAC, virtual shelf, my loans, catalogue, item, circulation desk, members, dashboard, reports, administration, audit log, system health.
- Test totals at gate: 108 backend tests and 5 frontend tests passing; full local pipeline green.

## Decisions recorded
- Overdue days are counted as calendar days between the due and return dates.
- Refusals are committed to the audit log before the 409 response, on every channel.
- Acquisition is limited to price and acquisition date on items; serials go to the backlog (ADR-0004). Net cataloguing is provided by the Stage 6 migration importer.

## Decision
Approved on 2026-10-07. RFID middleware and integrations (Stage 5) can start from `main` once this branch is merged.
