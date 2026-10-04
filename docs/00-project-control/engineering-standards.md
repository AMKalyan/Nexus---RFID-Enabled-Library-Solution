# Engineering Standards

Applies to all code, configuration, data and documentation in this repository.

These standards implement SOP §10 (Engineering controls) and NFR 02 (Security and privacy). A change that violates a standard requires an Architecture Decision Record (ADR) in `docs/02-design/adr/`.

## 1. Technology baseline

| Area | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Frontend | React + Vite + TypeScript, Tailwind CSS, TanStack Query, Lucide icons |
| Database | PostgreSQL 16 — schemas `legacy_ilms` (read-only), `nexus`, `staging` |
| Search | PostgreSQL `tsvector` + GIN index maintained by triggers |
| Packaging | Docker Compose; offline distribution via `docker save` image archives |

## 2. Security directives

### 2.1 Input validation and client trust
- Every request body, path/query parameter and uploaded file is validated by a strict Pydantic schema before it reaches business logic.
- Uploaded spreadsheets are size-limited, type-checked by content, and parsed in a staging area only.
- React escapes all rendered strings; no `dangerouslySetInnerHTML`. Rich text, if any, is sanitised server-side.

### 2.2 Secrets and configuration
- JWT signing keys, database credentials and adapter keys live only in the backend `.env` file, which is never committed.
- `.env.example` contains synthetic placeholders only.
- The frontend reads only public `VITE_*` variables and holds no secrets.

### 2.3 Authentication, authorisation and RBAC
- Passwords are hashed with argon2id. Plaintext passwords are never stored or logged.
- Access tokens are short-lived signed JWTs; refresh tokens are rotated and revocable.
- Roles: `Admin`, `Librarian`, `CirculationClerk`, `Auditor`, `Patron`. Every protected endpoint declares its required permission and is enforced server-side.
- IDOR protection: parameterised routes verify ownership or staff permission (a patron can never read another patron's loans).
- Staff smart-card login goes through the `CredentialProvider` adapter and issues the same tokens as password login.

### 2.4 Error handling and information disclosure
- A global exception handler returns sanitised JSON: `{"error": "<message>", "code": "<ERR_CODE>"}`.
- Responses never contain SQL, tracebacks, file paths or internal identifiers beyond what the API contract defines.

### 2.5 Database security and data protection
- Application code uses the SQLAlchemy ORM / expression language with bound parameters. String-built SQL is prohibited.
- Exception (ADR-0003): DDL, grants, triggers and integrity checksums use `sqlalchemy.text()` with bound parameters, and only inside Alembic migrations and `ops/` tooling.
- The application database role has `SELECT` only on `legacy_ilms` and `INSERT/SELECT` only on `nexus.audit_log`.
- 100% synthetic data. Logs mask personal data (email, phone, smart-card UID, name).
- Every administrative change, circulation transaction, fine adjustment, tagging action and gate alert is written to `nexus.audit_log`.

### 2.6 API defence and transport
- Rate limiting (`slowapi`) on authentication, migration and device-ingest endpoints.
- All traffic is designed for TLS termination at the nginx reverse proxy; the demo uses a locally generated self-signed certificate that is never committed.

## 3. Code quality (SOP §10)
- Python: `ruff` (lint + format), `mypy`, `bandit`, `pip-audit`. TypeScript: `eslint`, `prettier`, `npm audit`.
- The build pipeline runs format check, lint, static analysis, dependency scan and tests; a failing check blocks the stage gate.
- Tests are named and tagged by requirement ID (e.g. `test_ac04_reference_item_blocked`).

## 4. Configuration
- All environment-specific values come from environment variables or files outside source code.
- Adapters are selected by configuration (`ADAPTER_EMAIL=mock|smtp`, etc.).

## 5. Dependencies
- Exact versions pinned (`requirements.txt` with hashes where practical, `package-lock.json`).
- A software bill of materials with licences and offline-installation notes is kept in `docs/04-repository/`.

## 6. Version control and change control
- Branch per SOP stage (`stage/N-<name>`); small topic branches allowed within a stage.
- Meaningful, conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- A stage is closed by a stage-gate record, a `--no-ff` merge into `main` and a `sop-stage-N` tag. The final evaluation release is tagged `v1.0.0-eval`.
- When behaviour changes, the requirement (RTM), design, code, tests and documentation are updated in the same change.

## 7. Defects
- Defects are logged in `docs/00-project-control/defect-log.md` with ID, severity, reproduction steps, owner, status, fix version and retest evidence.
