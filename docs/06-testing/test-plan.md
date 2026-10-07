# Test Plan (D6)

Covers SOP §9 Stage 7. All results are in [`test-results.md`](test-results.md). Every test is mapped to a requirement in [`test-to-requirement-matrix.md`](test-to-requirement-matrix.md).

## Scope and approach

| Test type (SOP Stage 7) | What is tested | Where | How it runs |
|---|---|---|---|
| Functional (unit) | Policy engine, validation rules, token and password handling, masking, error sanitising, SIP2 framing, command bus, configuration guard | `backend/tests/unit/` | `pytest`, no database |
| Integration | API + service + PostgreSQL per module: auth, catalogue, OPAC, members, circulation, fines, reports, admin, devices, live feed, outbox, seed | `backend/tests/integration/` | `pytest` against a disposable `nexus_test` database (Alembic-migrated per session, transaction rolled back per test) |
| Acceptance | One file per scenario, AC 01–AC 10 | `backend/tests/acceptance/` | `pytest -m acceptance` |
| Regression | The API published with the last release is still served; the published OpenAPI snapshot is current | `backend/tests/regression/` | `pytest` |
| Device simulator | Event generation, offline queue and replay order, outage marking | `device-sim/test_sim.py` | `pytest` |
| Migration tooling | Sample generator: defect rates, manifest, reproducibility | `migration/test_gen_sample.py` | `pytest` |
| Frontend | API client token handling, refusal banner, inventory audio cues | `frontend/src/**/*.test.ts(x)` | `vitest` |
| Performance | 50 concurrent users, mixed search, circulation and dashboard; 20k-row migration timing | `backend/tests/perf/perf_async.py` | Against the running stack ([`performance-results.md`](performance-results.md)) |
| Security | Scanners, live smoke checks, repository secret checks, review against the threat table | `ops/tests/security_smoke.py` | Against the running stack ([`security-checks.md`](security-checks.md)) |
| Migration | Stage, validate, reconcile, commit and roll back 20,000 rows | `migration/nexus_migrate.py` | Against the running stack ([migration run report](../05-data-migration/migration-run-report.md)) |
| Backup and restore | Verified backup, restore after a damaging change, legacy fingerprints identical | AC 10 tests, `ops/backup.*`, `ops/restore.*`, `ops/integrity.py` | Tests plus a live rehearsal ([restore report](../05-data-migration/restore-and-integrity-report.md)) |
| Offline update and rollback | Install 1.0.0 offline, update to 1.0.1, roll back to 1.0.0 | `ops/install.*`, `ops/update.*`, `ops/rollback.*` | Offline rehearsal (AC 09, `ops/tests/ac09_offline_lifecycle.md`) |
| User acceptance | Each AC walked through in the browser with screenshots | [`uat-checklist.md`](uat-checklist.md) | Manual, against the running stack |

## Naming and traceability

Test names carry the requirement they prove: `test_fr10_…`, `test_nfr02_…`, `test_ac06_…`. `ops/trace_tests.py` reads the JUnit results and builds the matrix from these names, so a renamed or failing test shows up there.

## Environments

| Environment | Used for |
|---|---|
| Development host: Windows 11, i5-1240P, 16 GB RAM; Python 3.12.6, Node 22 | Unit, integration, acceptance, regression and frontend tests (`bash ops/ci-local.sh`) |
| Docker Compose stack: PostgreSQL 16.4, API, nginx with TLS, using `docker-compose.dev.yml` | Performance, security smoke checks, migration, restore, UAT |
| GitHub Actions workflow (`.github/workflows/ci.yml`) | The same pipeline steps as `ops/ci-local.sh`. The repository is local-only, so the local script is the run of record |

All data is synthetic ([synthetic data declaration](../01-requirements/synthetic-data-declaration.md)).

## Entry and exit criteria

| | Criteria |
|---|---|
| Entry | Stage 6 merged; stack builds and starts healthy; seeded and migrated data present |
| Exit | All automated tests pass. Every FR, NFR and AC row has tests or a recorded reason why not. No open S1 or S2 defect. S3 and S4 defects are recorded as known limitations with workarounds. Performance, security and UAT results are recorded |

## Defect handling

Failures go into the [defect log](../00-project-control/defect-log.md) with a severity (S1–S4). S1 and S2 defects are fixed on `fix/<id>-*` branches merged into the stage branch, with retest evidence. S3 and S4 defects are fixed if cheap, or recorded as known limitations.
