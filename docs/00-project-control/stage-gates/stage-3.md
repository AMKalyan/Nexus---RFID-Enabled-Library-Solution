# Stage Gate 3: Foundation Build (D3)

| Field | Value |
|---|---|
| SOP reference | §9 Stage 3 |
| Branch | `stage/3-foundation` |
| Gate date | 2026-10-05 |
| Outcome | Approved |

## Exit criteria (SOP §9 Stage 3 bullets)

| SOP requirement | Output | Evidence | Met |
|---|---|---|---|
| Implement project structure | Monorepo: `backend/` (layered packages), `frontend/`, `ops/`, `docs/` | README repository map; `docs/02-design/architecture.md` §3 | ☑ |
| Implement configuration | Settings from environment and `.env`; `.env.example` with placeholders only; adapters selected by configuration | `backend/app/core/config.py`, `.env.example`, `backend/app/integrations/registry.py` | ☑ |
| Implement authentication | argon2id passwords; short-lived JWT; rotating, hashed refresh tokens with reuse detection; rate-limited login | `backend/app/core/security.py`, `backend/app/api/v1/auth.py`; `test_nfr02_*` | ☑ |
| Implement role management | Five roles and 27 permissions seeded per the RBAC matrix; server-side `require()` and `ensure_self_or()`; permissions re-read per request | migration `0002_rbac_seed`, `backend/app/core/auth.py`; `test_nfr02_role_change_effective_immediately` | ☑ |
| Implement audit logging | Append-only `nexus.audit_log` (database grants); PII masked in details; login, logout and legacy mirror audited | `backend/app/core/audit.py`; `test_nfr02_audit_log_is_append_only`, `test_nfr02_audit_masks_pii_details`, `test_nfr02_login_attempts_are_audited_without_username` | ☑ |
| Implement health checks | `/api/v1/health` with database check; `/api/v1/version` with migration revision; container health checks | `backend/app/main.py`, `docker-compose.yml`; `test_nfr07_*` | ☑ |
| Implement database migrations | Alembic `0001_baseline` (schemas, read-only legacy role, grants, search trigger) and `0002_rbac_seed`; downgrade verified | `backend/app/db/migrations/versions/`; upgrade → downgrade → upgrade round trip; `alembic check` clean | ☑ |
| Implement test framework | pytest with PostgreSQL fixtures (fresh migrated database per session, transactional tests); vitest for the UI | `backend/tests/conftest.py`, `frontend/src/api/client.test.ts` | ☑ |
| Prepare synthetic seed data | Seed command: 2,000 legacy bibs, 2,377 accessions, 300 borrowers (fixed seed), mirrored into `nexus`; shelves, devices, staff, tags and activity; generated credentials kept out of git | `backend/app/db/seed.py`; `test_nfr01_mirror_copies_without_touching_legacy`, `test_fr10_seeded_isbns_have_valid_check_digits` | ☑ |
| Prepare a repeatable local build | Dockerfiles for API and web; nginx TLS proxy with security headers; `docker compose up -d --build` brings up a healthy stack | `backend/Dockerfile`, `frontend/Dockerfile`, `ops/nginx/`, README "Build and run" | ☑ |
| Run static checks | ruff (lint and format), mypy, bandit, pip-audit, tsc, npm audit in `ops/ci-local.sh` and `.github/workflows/ci.yml` | `docs/06-testing/baseline-test-report.md` | ☑ |
| Run baseline tests | 29 backend tests (83% line coverage) and 2 frontend tests passing | `docs/06-testing/baseline-test-report.md` | ☑ |

## Defects found and closed in this stage

| ID | Summary | Resolution |
|---|---|---|
| DEF-001 | Published vulnerabilities in pinned backend dependencies | Upgraded FastAPI/Starlette, Pillow, PyJWT, python-multipart and uvicorn; pip-audit clean |
| DEF-002 | `audit_log.details` lacked a database default | JSONB server defaults in the baseline migration |
| DEF-003 | Published vulnerabilities in frontend dependencies | Upgraded react-router-dom, Vite, Vitest, Tailwind and PostCSS; npm audit clean |

## Decisions recorded
- Frontend shell (Task 5) was built before the database tasks while the container runtime was being installed. The order of work changed; the scope did not.
- Raw SQL scope clarified in ADR-0003. Seeding the simulated legacy system is operations tooling, and the scope is enforced by a test.
- The frontend build image moved to Node 22 because the current Vite requires Node ≥ 20.19.

## Decision
Approved on 2026-10-05. Core library functions (Stage 4) can start from `main` once this branch is merged.
