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
