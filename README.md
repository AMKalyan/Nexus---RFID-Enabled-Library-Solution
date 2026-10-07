# Nexus — RFID-Enabled Library Solution

Nexus is a modular prototype that adds RFID workflows (tagging, circulation, inventory, security gates, smart-card login), reporting, data migration and offline lifecycle management to an existing Integrated Library Management System (ILMS) **without modifying, deleting or corrupting existing library records**.

All external devices and services (RFID readers, handhelds, gates, smart cards, CCTV, email, SMS, print, the legacy ILMS, NCIP/SIP2 endpoints) are integrated through documented adapter interfaces with working mocks. All data and credentials in this repository are synthetic.

## Repository map

| Path | Purpose |
|---|---|
| `docs/00-project-control/` | Engineering standards, SOP stage-gate records, issue tracker, progress log, defect log |
| `docs/01-requirements/` | D1 — Requirements package (RTM, assumptions, use cases, data dictionary) |
| `docs/02-design/` | D2 — Architecture package |
| `backend/` | FastAPI application, RFID middleware, interop and integration adapters |
| `frontend/` | React staff UI, OPAC, dashboard and administration |
| `device-sim/` | RFID device simulator (staff reader, handheld, gate, smart card, camera) |
| `migration/` | Spreadsheet migration utility and synthetic data generator |
| `ops/` | Offline install, update, rollback, backup, restore and integrity tooling |

## Delivery process

Development follows the AISYS Software Development SOP §9 stage by stage. Each stage is delivered on a `stage/N-*` branch, closed by a stage-gate review record in `docs/00-project-control/stage-gates/`, merged into `main` and tagged `sop-stage-N`.

## Build and run (development)

Prerequisites: Docker Desktop (Linux containers), Python 3.12, Node 22, Git Bash or a POSIX shell.

```bash
cp .env.example .env              # then replace every placeholder value
sh ops/nginx/gen-cert.sh          # self-signed certificate for local HTTPS
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose exec api python -m app.db.seed --legacy 2000 --demo
```

- Application: https://localhost:8443. The certificate is self-signed.
- API documentation: https://localhost:8443/api/docs
- Generated demo credentials: `ops/demo-credentials.txt` (git-ignored).

Local development without containers for the API and UI:

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/alembic upgrade head && .venv/Scripts/uvicorn app.main:app --reload    # :8000
cd frontend && npm ci && npm run dev                                                  # :5173
```

## Quality checks

```bash
bash ops/ci-local.sh              # format, lint, types, bandit, dependency audits, tests, build
```

The `docker-compose.dev.yml` override exposes PostgreSQL on `localhost:5433` for the test suite and runs the API with `ENVIRONMENT=dev`. Without it the API image runs in production mode and refuses to start with development or placeholder secrets.

To use the operator scripts (`ops/backup.sh`, `ops/restore.sh`, …) against a development stack, include the override for those commands too, for example `COMPOSE_FILE="docker-compose.yml;docker-compose.dev.yml" sh ops/restore.sh <file>`. On Linux and macOS, separate the two files with `:` instead of `;`.
