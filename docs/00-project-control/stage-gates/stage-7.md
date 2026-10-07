# Stage Gate 7: Verification (D8)

| Field | Value |
|---|---|
| SOP reference | §9 Stage 7 |
| Branch | `stage/7-verification` |
| Gate date | 2026-10-08 |
| Outcome | Pending approval |

## Exit criteria (SOP §9 Stage 7 bullets)

| SOP requirement | Output | Evidence | Met |
|---|---|---|---|
| Functional tests | Unit tests for policy, validation, tokens, masking, errors, SIP2 framing, commands, configuration guard, licence | `backend/tests/unit/`; [test results](../../06-testing/test-results.md) | ☑ |
| Integration tests | API, services and PostgreSQL per module, including the SIP2 TCP listener (previously untested) | `backend/tests/integration/`; `test_sip2_listener.py` (3) | ☑ |
| Regression tests | The API published with the last release must still be served, and the published snapshot must be current | `backend/tests/regression/test_api_contract.py` (2); `docs/08-operations/openapi.json` refreshed | ☑ |
| Performance tests | 10 and 50 concurrent users with a mix of search, circulation and dashboard; bottleneck analysis | [`performance-results.md`](../../06-testing/performance-results.md): 0 errors; Q-08 met at 10 users, missed at 50 (DEF-008, known limitation) | ☑ |
| Security tests | Scanners, 18 live checks (authentication, RBAC, IDOR, error leakage, injection, device keys, headers, redirect, rate limit), repository secret checks, threat-table review | [`security-checks.md`](../../06-testing/security-checks.md); `ops/tests/security_smoke.py` | ☑ |
| Migration tests | AC 01 suite; 20k run reconciled exactly; batch rollback rehearsal | `test_ac01_migration.py` (11); [migration run report](../../05-data-migration/migration-run-report.md) | ☑ |
| Backup and restore tests | AC 10 suite; live restore after damaging 19,200 items; the development database was also backed up before and restored after the AC 09 rehearsal | `test_ac10_restore_integrity.py` (5); [restore report](../../05-data-migration/restore-and-integrity-report.md) | ☑ |
| Offline-update tests | 1.0.0 installed and updated to 1.0.1 with networking off, from bundles only | [`ops/tests/ac09_offline_lifecycle.md`](../../../ops/tests/ac09_offline_lifecycle.md); offline transcript; `test_bundle_scripts.sh` (a tampered bundle is refused) | ☑ |
| Rollback tests | 1.0.1 rolled back to 1.0.0 (schema 0004 → 0003); counts unchanged; legacy data IDENTICAL; migration 0004 reverses cleanly | Offline transcript step 3; `test_ac09_release_101_migration_upgrades_downgrades_and_reapplies` | ☑ |
| Map every test result to a requirement | Matrix generated from JUnit results by `ops/trace_tests.py`; RTM updated | [`test-to-requirement-matrix.md`](../../06-testing/test-to-requirement-matrix.md) | ☑ |
| Triage defects by severity and retest fixes | DEF-007 to DEF-014: both S2 defects fixed on `fix/` branches with failing-first tests; S3/S4 fixed or recorded | [defect log](../defect-log.md); [UAT checklist](../../06-testing/uat-checklist.md) | ☑ |

## Test totals at gate
Run of record (`bash ops/ci-local.sh`, exit 0):

| Suite | Result |
|---|---|
| Backend | 242 tests passed (92% line coverage) |
| Acceptance | 83 passed |
| Simulator | 6 passed |
| Migration tools | 5 passed |
| Frontend | 9 passed |

The traceability matrix covers 253 JUnit cases, all passing, with no requirement failing.

ruff, mypy, bandit, pip-audit and npm audit are clean. The live security smoke checks pass 18 of 18. The offline AC 09 rehearsal and the UAT walkthrough of AC 01–08 and AC 10 pass.

## Findings and decisions
- **Two S2 defects, both fixed and retested.**
  - DEF-011: the local pipeline reported success when tests failed. Totals in earlier gate records were re-confirmed by this stage's runs.
  - DEF-009: the API accepted built-in or placeholder secrets outside development, and could echo a secret fragment into the startup log.
- **The API image now runs in production mode by default.** Development uses `docker-compose.dev.yml`.
- **Performance: recorded as a known limitation, by decision.** One API process saturates at about 86 req/s (DEF-008). Running four workers proved the cause, but in-process state (command bus, live hub, card challenges, rate-limit counters) must move to shared storage first, so this is in the production backlog (NX-063).
- **One unexplained 15-minute stall** in a single test run (DEF-012). Not reproduced under lock monitoring; the test database now fails fast on lock waits (NX-064).
- **UAT found two UI defects, both fixed:**
  - DEF-013: stale loans after a repeat look-up
  - DEF-014: sideways scrolling at narrow widths
- **Release sequence.** Tags `v1.0.0` and `v1.0.1` mark the bundled releases. The offline bundle tooling was built on this branch because SOP Stage 7 requires the offline-update and rollback tests before this gate. Release documentation (D7–D9) follows on `release/1.0.0`.
- **The 1.0.1 migration adds a new setting rather than seeding an existing one,** so the update cannot collide with site data and the rollback removes only what 1.0.1 added.
- **Licence files are HMAC-signed** (the site holds the key). An asymmetric signature is in the production backlog.

## Decision
Pending approval. Release and handover (D7–D9) start from `main` once this branch is merged.
