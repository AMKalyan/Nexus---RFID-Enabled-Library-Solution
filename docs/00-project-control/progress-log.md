# Progress Log

A running record of delivery against the SOP §9 stages. It is updated at every working session and every stage gate.

## Schedule

| SOP stage | Planned | Actual | Gate tag |
|---|---|---|---|
| 1 Initiation & controls | Day 1 (2026-10-04) | 2026-10-04 | `sop-stage-1` |
| 2 Requirements & design | Day 1 (2026-10-04) | 2026-10-04 | `sop-stage-2` |
| 3 Foundation build | Day 1 (2026-10-04) | 2026-10-05 | `sop-stage-3` |
| 4 Core library functions | Day 2 (2026-10-05) AM | 2026-10-07 | `sop-stage-4` |
| 5 RFID middleware & integrations | Day 2 midday | 2026-10-07 | `sop-stage-5` |
| 6 Migration & resilience | Day 2 afternoon | 2026-10-07 | `sop-stage-6` |
| 7 Verification | Day 2 evening | 2026-10-08 | `sop-stage-7` |
| Release & handover (D9–D10) | Day 2 evening | 2026-10-19 | `v1.0.0-eval` |

## Session log

### 2026-10-04 — Session 1
- Stage 1 started on branch `stage/1-initiation`.
- Repository initialised; engineering standards, RTM v0.1, assumptions/clarifications, risks/dependencies/exclusions, synthetic-data declaration, issue tracker, branch strategy and defect log created.
- Environment: Docker Desktop + WSL2 being installed on the development host (DEP-01). Stages 1–2 are documentation only and are not blocked by it.

## Resume checklist (next session)
1. `git status` and `git log --oneline --decorate -10`: confirm you're on the expected branch and see the last tag.
2. Read the "Next task" line below and the matching task in `implementation-plan.md`.
3. From Stage 3 onwards: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d` (the dev override is required with the local dev passwords, DEF-009), then run the test suite to confirm a green baseline before continuing.

- Stage 1 merged and tagged `sop-stage-1`.
- Stage 2 on `stage/2-design`: use cases, data dictionary, architecture, database, interface and security designs, ADR-0001..0005, design review, implementation plan.

- Stage 2 merged and tagged `sop-stage-2`.
- Stage 3 started on `stage/3-foundation`: Task 1 (backend skeleton, config, logging, sanitised errors, version endpoint) done, 6 unit tests passing.
- Paused for the development host reboot that completes the Docker Desktop installation.

### 2026-10-05 — Session 2
- WSL2 and Docker Desktop completed on the development host; PostgreSQL 16.4 runs in Docker.
- Stage 3 Tasks 2–6: database schemas, roles and baseline migration; authentication, tokens and RBAC; audit, legacy connector and synthetic seed; containers, TLS proxy and local pipeline. Task 5 (frontend shell) was done earlier while waiting for Docker.
- Dependency scans found published vulnerabilities in both stacks (DEF-001, DEF-003); dependencies upgraded and retested.
- Stage 3 gate approved, merged and tagged `sop-stage-3`.

### 2026-10-07 — Session 3
- Stage 3 merged and tagged `sop-stage-3` and `day1-checkpoint`.
- Stage 4 Tasks 7–11: cataloguing and OPAC search; members, policy engine, circulation and fines; dashboard and reports; administration; UI screens. 108 backend and 5 frontend tests passing.
- Manual user journeys recorded in `docs/06-testing/user-journeys.md`; DEF-004 closed.
- Stage 4 gate approved, merged and tagged `sop-stage-4`.

- Stage 4 merged and tagged `sop-stage-4`.
- Stage 5 Tasks 12–20: RFID middleware (ingest, dispatcher, command bus, live hub); tagging; handheld inventory; gate, CCTV and notification outbox; smart-card login; NCIP 2.0 subset and SIP2 boundary; device simulator; RFID screens. 189 backend, 6 simulator and 8 frontend tests passing (90% backend coverage).
- Simulator rehearsal of AC 02, 05, 06 and 07 recorded in `docs/06-testing/user-journeys.md` (UJ-07..11).
- Stage 5 gate approved, merged and tagged `sop-stage-5`.

- Stage 6 Tasks 21–24: synthetic 20k export generator and profiler; staged spreadsheet migration with validation, duplicate detection, reconciliation and batch rollback; verified backup, restore and legacy integrity checksums; D5 package. 214 backend (91% coverage), 6 simulator, 5 migration-tool and 8 frontend tests passing.
- Live 20k run reconciled exactly against the generator manifest; batch rollback and restore rehearsed on the stack with legacy data IDENTICAL (`docs/05-data-migration/`). DEF-005 and DEF-006 closed.
- Stage 6 gate approved, merged and tagged `sop-stage-6`.

- Stage 7 Task 25 on `stage/7-verification`: API contract regression test; load test at 10 and 50 users; security scanners and live smoke checks; UAT of AC 01-08 and AC 10 with screenshots; generated test-to-requirement matrix; test plan and results. Run of record: 234 backend (92% coverage), 6 simulator, 5 migration-tool, 9 frontend tests passing; 83 acceptance tests passing.
- Defects DEF-007 to DEF-014 raised. S2 defects DEF-009 (insecure defaults accepted outside development) and DEF-011 (local pipeline hid failures) fixed on `fix/` branches; DEF-008 (50-user latency) recorded as a known limitation; DEF-012 (one unexplained stall) mitigated with a fail-fast lock timeout.
- The API image now defaults to production mode; local development uses `docker-compose.dev.yml`.

### 2026-10-08 — Session 4
- Task 26 on `stage/7-verification`: offline bundle build, verified install, update with automatic rollback, manual rollback, licence activation (read-only until licensed outside development). Releases tagged `v1.0.0` and `v1.0.1` (build notes, reversible migration 0004).
- AC 09 rehearsed with networking off: install 1.0.0, update to 1.0.1, roll back to 1.0.0, legacy data IDENTICAL (`ops/tests/ac09_offline_lifecycle.md`). The development database was backed up first and restored afterwards.
- Gate run: 242 backend (92% coverage), 83 acceptance, 6 simulator, 5 migration-tool, 9 frontend tests passing; traceability matrix 253 of 253 passing.
- Stage 7 gate approved, merged and tagged `sop-stage-7`.

### 2026-10-19 — Session 5
- Release work on `release/1.0.0`: SBOM from the shipped images; D7 deployment, D8 operations and D9 demonstration packages.
- Writing the release documentation against the code found DEF-015 to DEF-024 (three S2: spoofed client address, `/health` status code, SIP2 allow-list). All fixed test-first on `fix/` branches and released as 1.0.2 (`v1.0.2`).
- 1.0.2 rehearsed: update from 1.0.1 and rollback (legacy data IDENTICAL), fresh install with a pre-issued licence, 19/19 security smoke checks, `/health` 503 with the database stopped.
- Run of record: 247 backend (92% coverage), 85 acceptance, 8 simulator, 5 migration-tool, 11 frontend tests passing; traceability 260/260.
- Release record `stage-gates/release.md`; release merged into `main` and tagged `v1.0.0-eval`.

**Status:** complete.
