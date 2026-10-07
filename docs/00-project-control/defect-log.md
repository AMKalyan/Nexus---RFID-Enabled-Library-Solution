# Defect Log

SOP reference: §10 Defects; deliverable D6.

Severity scale:
- **S1 Critical**: data loss or corruption, security breach, demo-blocking
- **S2 Major**: an acceptance scenario fails, with no workaround
- **S3 Minor**: functional issue with a workaround
- **S4 Cosmetic**

| ID | Found in stage | Severity | Summary | Reproduction steps | Requirement | Owner | Status | Fix version / commit | Retest evidence |
|---|---|---|---|---|---|---|---|---|---|
| DEF-001 | 3 | S2 Major | Pinned dependencies had published vulnerabilities (Pillow 10.4.0, PyJWT 2.9.0, python-multipart 0.0.12, Starlette 0.38.6 via FastAPI 0.115.0) | Run `pip-audit -r backend/requirements.txt` | NFR 02, NFR 04 | Backend | Closed | Stage 3: FastAPI 0.142.2, Pillow 12.3.0, PyJWT 2.15.1, python-multipart 0.0.32, uvicorn 0.54.0 | pip-audit: no known vulnerabilities; full test suite green |
| DEF-002 | 3 | S3 Minor | `audit_log.details` had no database default, so inserts that omit it failed | Insert an audit row without `details` | NFR 02 | Backend | Closed | Stage 3 baseline migration (JSONB server defaults) | `test_nfr02_audit_log_is_append_only` passes |
| DEF-003 | 3 | S2 Major | Frontend dependencies had published vulnerabilities (react-router-dom 6.26.2 shipped in the bundle; Vite 5, Vitest 2, Tailwind 3 tool chain) | Run `npm audit` in `frontend/` | NFR 02, NFR 04 | Frontend | Closed | Stage 3: react-router-dom 7.18.4, Vite 8.3.2, Vitest 5.0.3, Tailwind 4.3.3 (Vite plugin), PostCSS 8.5.28 | `npm audit`: 0 vulnerabilities; unit tests, build and login screen re-checked |
| DEF-004 | 4 | S4 Cosmetic | Dashboard charts logged React `defaultProps` deprecation warnings | Open the dashboard with the browser console open | FR 08 | Frontend | Closed | Stage 4: Recharts 3.10.1 | Console shows no warnings from the new bundle (`docs/06-testing/user-journeys.md`) |
| DEF-005 | 6 | S2 Major | The API image would install pg_dump 15, which cannot back up the PostgreSQL 16 server, so pre-migration backups would fail in production | `docker run python:3.12.7-slim apt-cache policy postgresql-client` shows 15 | NFR 01, FR 10 | Ops | Closed | Stage 6: `postgresql-client-16` from the PostgreSQL apt repository in `backend/Dockerfile` | `docker compose exec api pg_dump --version` → 16.15; 20k migration backup created in the container |
| DEF-006 | 6 | S3 Minor | Staging used per-row ORM statements: 2,000 rows took 21 s on the development host | Profile `MigrationService.stage` | FR 10 | Backend | Closed | Stage 6: core multi-row INSERTs and pipelined UPDATEs | Staging 2,000 rows 2.8 s; full 20,000-row run 13.7 s (`docs/05-data-migration/migration-run-report.md`) |
