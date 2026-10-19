# Presentation Outline

Slide-by-slide outline for the D9 presentation. It frames the live demonstration ([demo script](demo-script.md)) and takes about 10 minutes before and after it. Every figure on the slides comes from the linked evidence.

| # | Slide | Minutes |
|---|---|---|
| 1 | Title | 0:15 |
| 2 | The problem | 1:00 |
| 3 | Scope and approach | 1:00 |
| 4 | Architecture | 1:30 |
| 5 | Data integrity by design | 0:45 |
| 6 | Security controls | 0:45 |
| 7 | Offline deployment and lifecycle | 0:45 |
| 8 | SOP stage evidence | 1:00 |
| 9 | Acceptance scenarios (leads into the live demo) | 0:30 |
| — | Live demonstration, §1–§10 | 15:00 |
| 10 | Test evidence | 1:00 |
| 11 | Defects | 0:30 |
| 12 | Known limitations | 0:45 |
| 13 | Production backlog | 0:45 |
| 14 | Repository map and questions | — |

## 1. Title

- Nexus: RFID-enabled library solution prototype, release 1.0.2.
- Built to the AISYS Candidate Software Development SOP, stages 1–7 plus release.

## 2. The problem

- A library runs an existing Integrated Library Management System and wants RFID workflows: tagging, circulation, shelf inventory, security gates and staff smart cards.
- Constraint from the SOP purpose and NFR 01: integrate without changing, deleting or corrupting existing records, and back up before any integration.
- About 20,000 records arrive as spreadsheets and must be migrated with validation, duplicate handling and reconciliation (FR 10).
- The site is isolated: install, update and roll back without internet access (FR 12, NFR 03).
- No vendor hardware or live ILMS is available, so every device and external service sits behind a documented adapter with a working mock (SOP §1).

## 3. Scope and approach

- Acceptance-first: the ten priority scenarios AC 01–AC 10 drive the build; the rest of the functional scope is Partial or Backlog with scope notes ([ADR-0004](../02-design/adr/0004-acceptance-first-scope.md)).
- 12 functional and 9 non-functional requirements traced in the [RTM](../01-requirements/rtm.md).
- All data and credentials are synthetic ([synthetic data declaration](../01-requirements/synthetic-data-declaration.md)).
- Excluded by the SOP: hardware, live institutional systems, and any NCIP, SIP2, ISO or performance certification claim.

## 4. Architecture

Source: [`docs/02-design/architecture.md`](../02-design/architecture.md).

- Modular monolith ([ADR-0001](../02-design/adr/0001-modular-monolith.md)): one FastAPI service with the seven SOP §6 layers as packages: user layer (React UI and OPAC), application services, RFID middleware, interoperability (NCIP 2.0 subset, SIP2 boundary), data layer, integration adapters, operations.
- One circulation service behind the desk, NCIP and SIP2, so the rules (AC 04) and the audit trail (AC 03) are identical on every channel.
- Device simulator as a separate process speaking the same HTTP event contract a vendor bridge would use.
- Diagram: the layered component view (architecture §3) and the deployment view (architecture §5): nginx (TLS) → API → PostgreSQL, devices and kiosks through nginx.
- Technology choices table (architecture §6).

## 5. Data integrity by design

Sources: [database design](../02-design/database-design.md), [restore and integrity report](../05-data-migration/restore-and-integrity-report.md).

- Three schemas: `legacy_ilms` (read-only to the application role), `nexus`, `staging`.
- Prevention: database grants; the application role cannot modify legacy data (`test_nfr01_app_role_cannot_modify_legacy`).
- Detection: SHA-256 fingerprints of every legacy table before and after each migration commit, update and restore (`ops/integrity.py`).
- Recovery: a verified backup before every migration commit and update; restore in one transaction.
- Append-only `audit_log` for every administrative, circulation, fine, tagging, migration and gate action.

## 6. Security controls

Sources: [security design](../02-design/security-design.md), [security checks](../06-testing/security-checks.md).

- argon2id passwords, 15-minute JWT with rotating refresh tokens, server-side RBAC for five roles, ownership checks against IDOR.
- Sanitised errors, PII masking in logs and audit, rate limits on sign-in, device ingest and migration. nginx overwrites `X-Forwarded-For`, so a client cannot dodge a rate limit or write a false address into the audit log (DEF-015).
- SIP2 listener off by default; when enabled, only listed kiosk addresses may connect (an empty list refuses all, DEF-017), and Patron Status returns initials only (DEF-023).
- Per-device and per-agency keys stored hashed; TLS at nginx with HSTS and CSP.
- The image refuses to start in production with development or placeholder secrets (DEF-009).

## 7. Offline deployment and lifecycle

Sources: [ADR-0002](../02-design/adr/0002-offline-packaging.md), [AC 09 rehearsal](../../ops/tests/ac09_offline_lifecycle.md), [environment checklist](../07-deployment/environment-checklist.md).

- Bundle per release: image archive, Compose file, scripts, SBOM and `SHA256SUMS`; a tampered bundle is refused before anything is installed.
- `install`, `update` (backup first, automatic rollback if unhealthy after 120 s) and `rollback` scripts in PowerShell and shell. Since 1.0.2 `/api/v1/health` answers 503 when the database check fails, so "unhealthy" includes a release that cannot use its database (DEF-016).
- Services restart after a host or Docker restart (`restart: unless-stopped`, DEF-018).
- Licence-file activation; unlicensed installations are read-only for non-administrators. A pre-issued licence is installed with its key and takes effect immediately (DEF-020).
- Rehearsed with networking off: 1.0.0 → 1.0.1 → 1.0.0 in about 1 minute 40 seconds, legacy data IDENTICAL. The live demonstration repeats the cycle one release later: 1.0.1 → 1.0.2 → 1.0.1.

## 8. SOP stage evidence

Each stage was delivered on a `stage/N-*` branch, closed by a gate record, merged with `--no-ff` into `main` and tagged.

| Stage | Gate record | Branch | Gate date | Tag | Backend tests at gate |
|---|---|---|---|---|---|
| 1 Initiation and controls (D0) | [stage-1.md](../00-project-control/stage-gates/stage-1.md) | `stage/1-initiation` | 2026-10-04 | `sop-stage-1` | — |
| 2 Requirements and design (D1–D2) | [stage-2.md](../00-project-control/stage-gates/stage-2.md) | `stage/2-design` | 2026-10-04 | `sop-stage-2` | — |
| 3 Foundation build (D3) | [stage-3.md](../00-project-control/stage-gates/stage-3.md) | `stage/3-foundation` | 2026-10-05 | `sop-stage-3` | 29 (83% coverage) |
| 4 Core library functions (D4–D5) | [stage-4.md](../00-project-control/stage-gates/stage-4.md) | `stage/4-core` | 2026-10-07 | `sop-stage-4` | 108 |
| 5 RFID middleware and integrations (D6) | [stage-5.md](../00-project-control/stage-gates/stage-5.md) | `stage/5-rfid` | 2026-10-07 | `sop-stage-5` | 189 (90%) |
| 6 Migration and resilience (D7) | [stage-6.md](../00-project-control/stage-gates/stage-6.md) | `stage/6-migration` | 2026-10-07 | `sop-stage-6` | 214 (91%) |
| 7 Verification (D8) | [stage-7.md](../00-project-control/stage-gates/stage-7.md) | `stage/7-verification` | 2026-10-08 | `sop-stage-7` | 242 (92%) |

- Release tags `v1.0.0` and `v1.0.1` mark the two bundled releases used for the AC 09 rehearsal. Release 1.0.2 adds the release-stage fixes (DEF-015 to DEF-023) on `fix/` branches merged into the release branch. Release documentation (D7–D9) is on `release/1.0.0`.
- Supporting controls: [engineering standards](../00-project-control/engineering-standards.md), [issue tracker](../00-project-control/issue-tracker.md), [defect log](../00-project-control/defect-log.md), [progress log](../00-project-control/progress-log.md), [branch strategy](../04-repository/branch-strategy.md).
- Show on screen: `git log --oneline --graph --decorate` around a stage merge, and `git tag`.

## 9. Acceptance scenarios

| AC | Scenario | Demo | Acceptance test |
|---|---|---|---|
| AC 01 | Spreadsheet migration with reconciliation | §1 | `test_ac01_migration.py` |
| AC 02 | Tag an item and show the relationship | §2 | `test_ac02_tagging.py` |
| AC 03 | Check-out, renew, check-in over desk, NCIP and SIP2 with audit trail | §3 | `test_ac03_circulation_interop.py` |
| AC 04 | Refuse reference item, blocked member, fine over limit | §4 | `test_ac04_circulation_blocks.py` |
| AC 05 | Handheld shelf inventory, missing and misplaced, light and tone | §5 | `test_ac05_inventory.py` |
| AC 06 | Gate alarm with accession, CCTV image and queued email | §6 | `test_ac06_gate_event.py` |
| AC 07 | Smart-card sign-in with RBAC | §7 | `test_ac07_smartcard_rbac.py` |
| AC 08 | Dashboard and filterable, exportable reports | §8 | `test_ac08_reports.py` |
| AC 09 | Offline install, update and rollback | §9 | Offline rehearsal, `test_ac09_release_101_migration_upgrades_downgrades_and_reapplies` |
| AC 10 | Restore after a failed change, legacy data intact | §10 | `test_ac10_restore_integrity.py` |

Then switch to the live demonstration.

## 10. Test evidence

Sources: [test results](../06-testing/test-results.md), [test-to-requirement matrix](../06-testing/test-to-requirement-matrix.md), [performance results](../06-testing/performance-results.md), [security checks](../06-testing/security-checks.md), [UAT checklist](../06-testing/uat-checklist.md).

| Measure | Result |
|---|---|
| Backend tests (unit, integration, acceptance, regression) | 242 passed, 0 failed; line coverage 92% |
| Acceptance tests (AC 01–08, AC 10) | 83 passed |
| Device simulator / migration tools / frontend | 6 / 5 / 9 passed |
| Traceability | 253 JUnit cases, all passing; 243 traced to a requirement by name |
| Static analysis and dependency audits | ruff, mypy, bandit (0 issues), pip-audit and npm audit (0 vulnerabilities) clean |
| Live security smoke checks | 18 of 18 pass |
| API contract regression | 2 passed; 62 paths, none removed |
| Migration | 20,000 = 19,200 valid + 600 rejected + 200 duplicates; 13.7 s end to end (target under 5 minutes) |
| Restore | 19,200 damaged items restored; legacy fingerprints IDENTICAL (3 tables, 4,677 rows) |
| Offline lifecycle | Install, update and rollback pass with networking off; legacy IDENTICAL |
| Performance | 0 errors in every run. Q-08 met at 10 users (search p95 82 ms, check-out p95 227 ms); missed at 50 users (search p95 842 ms, check-out p95 1,104 ms): DEF-008 |
| UAT | AC 01–08 and AC 10 pass in the browser; AC 09 passes in the offline rehearsal |

All figures are observations on the development host (Windows 11, i5-1240P, 16 GB), not certified results.

## 11. Defects

Source: [defect log](../00-project-control/defect-log.md).

- 23 defects raised: 14 across stages 3–7 and 9 at the release stage. 21 closed with retest evidence; open are DEF-008 (known limitation) and DEF-012 (under monitoring).
- Both S2 defects in Stage 7 fixed on `fix/` branches with failing-first tests: DEF-009 (insecure defaults accepted outside development) and DEF-011 (local pipeline hid failing tests).
- UAT found two UI defects, both fixed: DEF-013 (stale loan list) and DEF-014 (sideways scrolling).
- Release stage: writing the deployment and operations documentation against the code found DEF-015 to DEF-023, all fixed in 1.0.2, each with a test or check that failed before the change:
  - S2: client-supplied `X-Forwarded-For` bypassed the sign-in rate limit and set the audit address (DEF-015); `/health` answered 200 when degraded, hiding a database failure from Docker and the update rollback (DEF-016); an empty SIP2 allow-list accepted every host (DEF-017).
  - S3: no restart policy (DEF-018); a failed shell restore left the services stopped (DEF-019); a pre-issued licence could not be installed (DEF-020); migration commit did not reconcile before inserting (DEF-021); the simulator dropped replayed events refused with 401, 403 or 429 (DEF-022); SIP2 Patron Status disclosed the full name (DEF-023).
- No S1 or S2 defect is open.

## 12. Known limitations

Source: [known-limitations.md](known-limitations.md).

- Mocks for RFID hardware, CCTV, SMS, email, print, the smart-card credential provider and the legacy ILMS; no conformance claims for NCIP, SIP2 or ISO 28560.
- Single API process: Q-08 latency missed at 50 users (DEF-008).
- HMAC licences (the site holds the key); self-signed certificate; SIP2 has no transport security, so its listener is off by default.
- Acquisition and serials minimal or absent (FR 01 Partial); Windows Server 2022 not yet verified (NFR 03 Partial).
- No supported way to register an NCIP agency yet.
- The maintenance notice is stored but not displayed; the System health screen does not show a failing check (both found while preparing 1.0.2).

## 13. Production backlog

Source: [production-backlog.md](production-backlog.md).

- 31 items with priority and rough size; 12 are P1 (needed before go-live).
- Phase 1, site readiness: Windows Server verification, site certificate, NCIP agency administration, the site's ILMS connector and re-sync.
- Phase 2, hardware and messaging: vendor RFID adapters, ISO 28560 encoding, real card authentication, SMTP.
- Phase 3, capacity and assurance: scale beyond one process (NX-063), data retention, penetration test.

## 14. Repository map and questions

- [README](../../README.md) repository map; documentation packages D1, D2 and D4–D9 under [`docs/`](../).
- Demonstration recording: see [README](README.md#recording).
