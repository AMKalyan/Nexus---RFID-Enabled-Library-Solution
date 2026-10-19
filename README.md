# Nexus — RFID-Enabled Library Solution

Nexus is a modular prototype that adds RFID workflows to an existing Integrated Library Management System (ILMS) **without modifying, deleting or corrupting existing library records**. The workflows are tagging, circulation, inventory, security gates and smart-card sign-in. It also adds reporting, data migration and offline lifecycle management.

All external devices and services are integrated through documented adapter interfaces with working mocks: RFID readers, handhelds, gates, smart cards, CCTV, email, SMS, printing, the legacy ILMS, and NCIP/SIP2 endpoints. All data and credentials in this repository are synthetic.

**Current release: 1.0.3** (schema revision `0004`). See [RELEASE-NOTES.md](RELEASE-NOTES.md).

## Acceptance scenarios

| AC | Scenario | Evidence |
|---|---|---|
| AC 01 | Spreadsheet migration: stage, validate, de-duplicate, commit, reconcile | [Migration run report](docs/05-data-migration/migration-run-report.md) (20,000 = 19,200 + 600 + 200) |
| AC 02 | Locate an item, validate it, associate an RFID tag | [UAT](docs/06-testing/uat-checklist.md) |
| AC 03 | Check out, renew and check in through the desk, NCIP and SIP2, with audit | [UAT](docs/06-testing/uat-checklist.md) |
| AC 04 | Refuse reference items, blocked members, fines over the limit | [UAT](docs/06-testing/uat-checklist.md) |
| AC 05 | Handheld inventory: missing and misplaced items, with beep and light cues | [UAT](docs/06-testing/uat-checklist.md) |
| AC 06 | Security gate alarm with mock CCTV snapshot and queued notification | [UAT](docs/06-testing/uat-checklist.md) |
| AC 07 | Staff smart-card sign-in with role-based permissions | [UAT](docs/06-testing/uat-checklist.md) |
| AC 08 | Dashboard and filterable reports with CSV/PDF export | [UAT](docs/06-testing/uat-checklist.md) |
| AC 09 | Offline install, update and rollback | [Offline rehearsal](ops/tests/ac09_offline_lifecycle.md) |
| AC 10 | Restore after a damaging change; legacy data proven identical | [Restore and integrity report](docs/05-data-migration/restore-and-integrity-report.md) |

Every test is traced to a requirement in the [test-to-requirement matrix](docs/06-testing/test-to-requirement-matrix.md). Results: [test results](docs/06-testing/test-results.md).

## Repository map

| Path | Purpose |
|---|---|
| `backend/` | FastAPI application, RFID middleware, interop (NCIP, SIP2) and integration adapters; tests in `backend/tests/` |
| `frontend/` | React staff UI, OPAC, dashboard and administration |
| `device-sim/` | RFID device simulator: staff reader, handheld, gate, smart card, camera |
| `migration/` | Spreadsheet migration utility and synthetic data generator |
| `ops/` | Offline bundle build, install, update, rollback, backup, restore, integrity and licence tooling |
| `docs/` | Deliverables D1–D9 (below) |

| Deliverable | Location |
|---|---|
| Project control: standards, plan, stage gates, defect log, issue tracker | [`docs/00-project-control/`](docs/00-project-control/) |
| D1 Requirements: RTM, use cases, data dictionary | [`docs/01-requirements/`](docs/01-requirements/) |
| D2 Architecture: design, security, interfaces, ADRs | [`docs/02-design/`](docs/02-design/) |
| D3 Working prototype | `backend/`, `frontend/`, `device-sim/` |
| D4 Source repository: branching, SBOM and licences | [`docs/04-repository/`](docs/04-repository/) |
| D5 Database and migration | [`docs/05-data-migration/`](docs/05-data-migration/) |
| D6 Test package | [`docs/06-testing/`](docs/06-testing/) |
| D7 Deployment package | [`docs/07-deployment/`](docs/07-deployment/) |
| D8 Operational documentation | [`docs/08-operations/`](docs/08-operations/) |
| D9 Demonstration: script, limitations, backlog | [`docs/09-demo/`](docs/09-demo/) |

## Delivery process

Development follows the AISYS Software Development SOP §9 stage by stage. Each stage was delivered on a `stage/N-*` branch, closed by a stage-gate record in [`docs/00-project-control/stage-gates/`](docs/00-project-control/stage-gates/), merged into `main` with `--no-ff` and tagged `sop-stage-N`. Defects were fixed on `fix/DEF-NNN-*` branches. The releases are tagged `v1.0.0`, `v1.0.1` and `v1.0.2`, and the evaluation release is `v1.0.0-eval`.

## Install from an offline bundle

```bash
sh ops/build_bundle.sh 1.0.2        # on a build machine: produces ops/bundles/nexus-1.0.2.zip
```

On the target host, unzip the bundle and follow the [installation guide](docs/07-deployment/installation-guide.md):

```powershell
powershell -ExecutionPolicy Bypass -File ops\install.ps1 -Demo
```

## Build and run (development)

Prerequisites: Docker Desktop (Linux containers), Python 3.12, Node 22, and Git Bash or another POSIX shell.

```bash
cp .env.example .env              # then replace every placeholder value
sh ops/nginx/gen-cert.sh          # self-signed certificate for local HTTPS
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose exec api python -m app.db.seed --legacy 2000 --demo
docker compose cp api:/app/ops/demo-credentials.txt ops/demo-credentials.txt
```

- Application: https://localhost:8443 (self-signed certificate)
- API documentation: https://localhost:8443/api/docs
- Generated demo credentials: `ops/demo-credentials.txt` (git-ignored)

To run the API and UI without containers:

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/alembic upgrade head && .venv/Scripts/uvicorn app.main:app --reload    # :8000
cd frontend && npm ci && npm run dev                                                  # :5173
```

The `docker-compose.dev.yml` override exposes PostgreSQL on `localhost:5433` for the test suite and runs the API with `ENVIRONMENT=dev`. Without it, the API image runs in production mode and refuses to start with development or placeholder secrets.

To use the operator scripts (`ops/backup.sh`, `ops/restore.sh`, …) against a development stack, include the override for those commands too:

```bash
COMPOSE_FILE="docker-compose.yml;docker-compose.dev.yml" sh ops/restore.sh <file>
```

On Linux and macOS, separate the two files with `:` instead of `;`.

## Quality checks

```bash
bash ops/ci-local.sh              # format, lint, types, bandit, dependency audits, all tests, build
```

The same steps run in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Hosting a public demonstration

Netlify or Vercel alone cannot run Nexus, which needs an always-on API with WebSockets and PostgreSQL. [Hosting options](docs/07-deployment/hosting-options.md) covers a single VM (recommended), a split UI/API set-up, and the publication checklist. On a demonstration instance, `DEMO_PUBLIC_ACCOUNTS=true` lists non-admin demo sign-in details on the login page.

## Known limitations

See [`docs/09-demo/known-limitations.md`](docs/09-demo/known-limitations.md) and the [production backlog](docs/09-demo/production-backlog.md).
