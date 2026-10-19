# Test Results: Stage 7 Run of Record

| Field | Value |
|---|---|
| Date | 2026-10-19 (release 1.0.3 run of record; the Stage 7 gate run was on 2026-10-08) |
| Branch | `feature/demo-accounts` at release 1.0.3 (release 1.0.2 fixes DEF-015 to DEF-024 included) |
| Command | `bash ops/ci-local.sh` (same steps as `.github/workflows/ci.yml`), then the simulator, migration-tool and acceptance suites with JUnit output |
| Environment | Windows 11 host (i5-1240P, 16 GB); Python 3.12.6; Node 22; PostgreSQL 16.4 container via `docker-compose.dev.yml` |

## Pipeline

| Check | Tool | Result |
|---|---|---|
| Format | `ruff format --check` | All files formatted |
| Lint, including security rules | `ruff check` | All checks passed |
| Types | `mypy app nexus_ops` | No issues |
| Static security analysis | `bandit -r app nexus_ops` | 0 issues ([security checks](security-checks.md)) |
| Python dependencies | `pip-audit` | No known vulnerabilities |
| Backend tests (unit, integration, acceptance, regression) | `pytest --cov=app` | **251 passed, 0 failed**; line coverage **93%** |
| Simulator, migration and ops tooling | `ruff format --check`, `ruff check` | Clean |
| Device simulator | `pytest` | 8 passed |
| Migration tools | `pytest` | 5 passed |
| Frontend types and tests | `tsc -b`, `vitest run` | Pass; 13 passed in 5 files |
| Frontend dependencies | `npm audit --audit-level=high` | 0 vulnerabilities |
| Frontend build | `vite build` | Pass |
| Pipeline exit status | `ops/ci-local.sh` | 0. A forced failure exits non-zero since DEF-011 |

## By test type

| Type | Suite | Result |
|---|---|---|
| Functional and integration | `backend/tests/unit`, `backend/tests/integration` | Pass (included in the 251) |
| Acceptance (AC 01–08, AC 10) | `pytest -m acceptance` → [`junit-acceptance.xml`](junit-acceptance.xml) | 85 passed, 0 failed |
| Regression | `backend/tests/regression/test_api_contract.py` | 2 passed; no endpoint removed, snapshot current (62 paths) |
| Performance | `backend/tests/perf/perf_async.py` | 0 errors. Q-08 met at 10 users, missed at 50 (DEF-008, known limitation) ([performance results](performance-results.md)) |
| Security | Scanners plus `ops/tests/security_smoke.py` | 19 of 19 live checks pass against a fresh 1.0.2 installation, including the DEF-015 spoofing checks ([security checks](security-checks.md)) |
| Migration | 20,000-row run, plus rollback rehearsal | Reconciled exactly; rollback left other data and legacy data unchanged ([run report](../05-data-migration/migration-run-report.md)) |
| Backup and restore | AC 10 tests, plus live rehearsal | Restore verified; legacy fingerprints identical ([restore report](../05-data-migration/restore-and-integrity-report.md)) |
| Offline update and rollback | AC 09 rehearsal with networking off, plus `test_bundle_scripts.sh` and `test_migrations.py` | Install 1.0.0, update to 1.0.1 and roll back all pass; legacy data IDENTICAL; release 1.0.2 update from 1.0.1 and rollback also pass (network on) ([rehearsal](../../ops/tests/ac09_offline_lifecycle.md)) |
| User acceptance | [UAT checklist](uat-checklist.md) | AC 01–08 and AC 10 pass in the browser; AC 09 passes in the offline rehearsal |

Traceability: [`test-to-requirement-matrix.md`](test-to-requirement-matrix.md). It covers 264 JUnit test cases (backend, simulator and migration tools), all passing; 252 are traced to a requirement by name.

## Coverage notes

The lowest-covered backend modules, and why:
- `db/seed.py` (54%): demo data paths used by the CLI only.
- `db/migrations/versions/0001_baseline.py` (49%): downgrade paths are exercised in the release rehearsal.
- `main.py` and `worker.py` (74–76%): process start-up and the background loop.

The SIP2 TCP listener went from 0% to 97% with `test_sip2_listener.py` in this stage.

## Defects raised in Stage 7

| ID | Severity | Status |
|---|---|---|
| DEF-007 OPAC search scanned every item | S3 | Closed |
| DEF-008 Q-08 latency missed at 50 users (single API process) | S3 | Known limitation |
| DEF-009 Built-in or placeholder secrets accepted outside development | S2 | Closed |
| DEF-010 HTTP redirect dropped the HTTPS port | S3 | Closed |
| DEF-011 Local pipeline hid failing tests | S2 | Closed |
| DEF-012 One intermittent 15-minute stall in a test run | S3 | Monitoring (fail-fast lock timeout added; no recurrence) |
| DEF-013 Desk look-up did not refresh loans | S3 | Closed |
| DEF-014 Pages scrolled sideways at narrow widths | S4 | Closed |
| DEF-015 to DEF-024 (release stage: spoofed client address, health status code, SIP2 allow-list and name, restart policy, restore restart, licence install, migration guard, simulator replay, health screen) | S2/S3 | Closed in 1.0.2, retested |

No S1 or S2 defect is open. Details, reproduction steps and retest evidence are in the [defect log](../00-project-control/defect-log.md).
