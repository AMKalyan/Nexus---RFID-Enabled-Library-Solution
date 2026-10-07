# Progress Log

A running record of delivery against the SOP §9 stages. It is updated at every working session and every stage gate.

## Schedule

| SOP stage | Planned | Actual | Gate tag |
|---|---|---|---|
| 1 Initiation & controls | Day 1 (2026-10-04) | 2026-10-04 | `sop-stage-1` |
| 2 Requirements & design | Day 1 (2026-10-04) | 2026-10-04 | `sop-stage-2` |
| 3 Foundation build | Day 1 (2026-10-04) | 2026-10-05 | `sop-stage-3` |
| 4 Core library functions | Day 2 (2026-10-05) AM | 2026-10-07 | `sop-stage-4` |
| 5 RFID middleware & integrations | Day 2 midday | — | `sop-stage-5` |
| 6 Migration & resilience | Day 2 afternoon | — | `sop-stage-6` |
| 7 Verification | Day 2 evening | — | `sop-stage-7` |
| Release & handover (D9–D10) | Day 2 evening | — | `v1.0.0-eval` |

## Session log

### 2026-10-04 — Session 1
- Stage 1 started on branch `stage/1-initiation`.
- Repository initialised; engineering standards, RTM v0.1, assumptions/clarifications, risks/dependencies/exclusions, synthetic-data declaration, issue tracker, branch strategy and defect log created.
- Environment: Docker Desktop + WSL2 being installed on the development host (DEP-01). Stages 1–2 are documentation only and are not blocked by it.

## Resume checklist (next session)
1. `git status` and `git log --oneline --decorate -10`: confirm you're on the expected branch and see the last tag.
2. Read the "Next task" line below and the matching task in `implementation-plan.md`.
3. From Stage 3 onwards: `docker compose up -d`, then run the test suite to confirm a green baseline before continuing.

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

**Next task:** Task 12 of `implementation-plan.md` (device registry, event ingest, dispatcher, command bus, live hub) on `stage/5-rfid`.
