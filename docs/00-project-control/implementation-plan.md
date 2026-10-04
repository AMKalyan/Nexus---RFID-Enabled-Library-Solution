# Nexus Implementation Plan (SOP Stages 3–7 and Release)

**Goal:** Build the Nexus prototype so that all ten priority acceptance scenarios (AC 01–10) run end-to-end, with the evidence each SOP §9 stage requires.

**Architecture:** A modular FastAPI backend (`backend/app`) with one package per SOP §6 layer, PostgreSQL with the schemas `legacy_ilms` (read-only), `nexus` and `staging`, a React/Vite frontend served by nginx, and a separate `device-sim` process that speaks the RFID event contract. Every external device or service sits behind an adapter interface with a mock. See `docs/02-design/README.md`.

**Tech stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, psycopg 3, argon2-cffi, PyJWT, slowapi, openpyxl, reportlab, Pillow, defusedxml; React 18 + TypeScript + Vite + Tailwind + TanStack Query + Lucide + Recharts; PostgreSQL 16; Docker Compose.

**Spec:** `docs/02-design/*` and `docs/01-requirements/*` (use cases, data dictionary, RTM). Read the relevant spec section before starting each task.

## Global constraints

- Python ≥ 3.11 (images use 3.12). Node ≥ 20 for builds only.
- All dependency versions pinned exactly (`requirements*.txt`, `package-lock.json`).
- Application code never uses `sqlalchemy.text()` (ADR-0003). Raw SQL is allowed only in `backend/app/db/migrations/` and `ops/`.
- The app connects as `nexus_app`. Alembic and `ops/` connect as `nexus_owner`.
- Every error response is `{"error": str, "code": str}` (validation errors may add `fields`).
- Every admin, circulation, fine, tagging, migration and gate action writes one `nexus.audit_log` row inside the same transaction.
- PII (email, phone, names, card UIDs) is masked in logs.
- All data is synthetic. Faker uses seed 42.
- Tests are named after the requirement they prove (`test_ac04_*`, `test_fr05_*`, `test_nfr01_*`).
- Commits use conventional prefixes. Each stage closes with a gate record, a `--no-ff` merge and a `sop-stage-N` tag (see `docs/04-repository/branch-strategy.md`).

## Review focus

These are the inputs most likely to break the system that no acceptance scenario exercises directly. Each one has a test in the task that owns the code.

1. **Same item checked out twice at once** (two clerks, or UI + NCIP). Expect exactly one loan; the second request gets `ITEM_NOT_AVAILABLE`. Test in Task 8 (`test_fr04_concurrent_checkout_single_loan`).
2. **Spreadsheet with odd cells:** empty rows, merged header, ISBN stored as a number, Excel date serials, trailing spaces, non-UTF-8 CSV. Expect normalisation or a precise reason code, never a crash. Test in Task 22 (`test_fr10_messy_cells_normalised`).
3. **Device event replayed after an offline period, with an `occurred_at` older than later events.** Expect it to be processed once, reports ordered by `occurred_at` (not receipt time), and no duplicate alarm notification. Test in Task 15 (`test_fr07_offline_replay_out_of_order`).
4. **Re-tagging an EPC already active on another item.** Expect `TAG_IN_USE` with no change to either item. Test in Task 13 (`test_fr05_epc_already_active_elsewhere`).
5. **Expired or forged tokens and role changes mid-session.** Expect 401 for bad tokens, and a demoted user to lose the permission on the very next request. Test in Task 3 (`test_nfr02_role_change_effective_immediately`).

---

## File structure

```
backend/
  pyproject.toml            ruff, mypy, pytest, bandit config
  requirements.txt          pinned runtime deps
  requirements-dev.txt      pinned dev/test deps
  Dockerfile
  alembic.ini
  app/
    main.py                 create_app(): routers, middleware, error handlers
    core/
      config.py             Settings (pydantic-settings), get_settings()
      logging.py            JSON formatter, PII masking
      errors.py             AppError, install_error_handlers()
      security.py           argon2 hashing, JWT, refresh tokens
      auth.py               Principal, get_principal(), require(), ensure_self_or()
      audit.py              audit()
      ratelimit.py          limiter
    db/
      base.py               Base, engine, SessionLocal, get_session()
      models/               one module per aggregate: identity, catalog, members, circulation,
                            devices, notify, ops, staging, legacy
      migrations/           Alembic env + versions
      seed.py               synthetic legacy + demo data
    api/v1/                 thin routers: auth, health, catalog, opac, members, circulation, fines,
                            tags, inventory, gate, devices, notifications, reports, admin, migration, ws
    services/               catalog, members, policy, circulation, fines, tagging, inventory, gate,
                            reports, notifications, users
    middleware_rfid/        ingest, dispatcher, commands, live_hub, handlers/
    interop/                ncip.py, sip2.py, sip2_server.py
    integrations/           base.py (Protocols), registry.py, notify_mock.py, camera_mock.py,
                            credentials_mock.py, legacy_db.py
  tests/
    conftest.py
    unit/  integration/  acceptance/  perf/
frontend/                   Vite React app (src/pages/*, src/api/*, src/components/*)
device-sim/                 sim.py (CLI + small FastAPI panel), offline queue
migration/                  gen_sample.py, rules.yaml, mapping.yaml, nexus_migrate.py (CLI)
ops/
  db/init/01-roles.sh       creates nexus_app, nexus_readonly, legacy_owner
  integrity.py  backup.(sh|ps1)  restore.(sh|ps1)  build_bundle.(sh|ps1)
  install.(sh|ps1)  update.(sh|ps1)  rollback.(sh|ps1)  nginx/  tests/
docker-compose.yml          db, api, web (+ devsim under profile "demo")
docker-compose.dev.yml      exposes db on 5433 for local test runs
.env.example
.github/workflows/ci.yml
```

## Schedule

| Day | Tasks | Stage gate |
|---|---|---|
| Day 1 (2026-10-04) | Tasks 1–6 | `sop-stage-3` |
| Day 2 (2026-10-05) morning | Tasks 7–11 | `sop-stage-4` |
| Day 2 midday | Tasks 12–20 | `sop-stage-5` |
| Day 2 afternoon | Tasks 21–24 | `sop-stage-6` |
| Day 2 evening | Tasks 25–27 | `sop-stage-7`, `v1.0.0-eval` |

Cut-line if behind schedule:
- Keep every AC slice and every gate.
- Drop these to Backlog in the RTM: SIP2 TCP listener, spine-label PDF, patron-card PDF, footfall chart, PDF report export (CSV stays).

---

# SOP Stage 3: Foundation build (branch `stage/3-foundation`)

### Task 1: Backend skeleton, configuration, logging, errors, health/version

**Files:**
- Create: `backend/pyproject.toml`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/core/{__init__,config,logging,errors,ratelimit}.py`, `backend/app/api/__init__.py`, `backend/app/api/v1/{__init__,health}.py`, `.env.example`, `VERSION`
- Test: `backend/tests/unit/test_logging_mask.py`, `backend/tests/unit/test_errors.py`, `backend/tests/unit/test_health.py`

**Interfaces:**
- Produces:
  - `get_settings() -> Settings`
  - `AppError(code: str, message: str, status_code: int = 400)`
  - `install_error_handlers(app: FastAPI) -> None`
  - `mask_pii(text: str) -> str`
  - `configure_logging(level: str) -> None`
  - `limiter: slowapi.Limiter`
  - `create_app() -> FastAPI`
  - `GET /api/v1/health` → `{"status": "ok", ...}`
  - `GET /api/v1/version` → `{"version": str, "alembic_rev": str | None, "licence": str}`

- [ ] **Step 1: Pin dependencies**

`backend/requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
alembic==1.13.3
psycopg[binary]==3.2.3
pydantic==2.9.2
pydantic-settings==2.5.2
argon2-cffi==23.1.0
PyJWT==2.9.0
slowapi==0.1.9
python-multipart==0.0.12
openpyxl==3.1.5
reportlab==4.2.2
Pillow==10.4.0
PyYAML==6.0.2
defusedxml==0.7.1
Faker==30.1.0
httpx==0.27.2
```
`backend/requirements-dev.txt`:
```
-r requirements.txt
pytest==8.3.3
pytest-cov==5.0.0
ruff==0.6.9
mypy==1.11.2
bandit==1.7.10
pip-audit==2.7.3
types-PyYAML==6.0.12.20240917
```
Run: `cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt`
Expected: installs without resolver errors.

- [ ] **Step 2: Tool configuration**

`backend/pyproject.toml`:
```toml
[project]
name = "nexus-backend"
version = "1.0.0"
requires-python = ">=3.11"

[tool.ruff]
line-length = 110
target-version = "py311"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "S", "SIM"]
ignore = ["S101"]          # assert allowed in tests
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S105", "S106"]

[tool.mypy]
python_version = "3.12"
strict_optional = true
ignore_missing_imports = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["db: needs PostgreSQL", "acceptance: AC scenario"]
```

- [ ] **Step 3: Write the failing tests**

`backend/tests/unit/test_logging_mask.py`:
```python
from app.core.logging import mask_pii

def test_nfr02_masks_email_and_phone():
    out = mask_pii("notify asha.rao@example.org at +91-98450-12345")
    assert "asha.rao@example.org" not in out
    assert "a***@example.org" in out
    assert "12345" not in out and out.endswith("45")

def test_nfr02_mask_leaves_plain_text():
    assert mask_pii("checkout ACC-000123 ok") == "checkout ACC-000123 ok"
```
`backend/tests/unit/test_errors.py`:
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.errors import AppError, install_error_handlers

def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    @app.get("/boom")
    def boom():
        raise RuntimeError("SELECT * FROM secret_table at /srv/app.py")
    @app.get("/apperr")
    def apperr():
        raise AppError("MEMBER_BLOCKED", "Member is blocked", 409)
    return app

def test_nfr02_unhandled_error_is_sanitised():
    r = TestClient(_app(), raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert r.json() == {"error": "Internal Server Error", "code": "ERR_INTERNAL"}
    assert "secret_table" not in r.text

def test_app_error_shape():
    r = TestClient(_app()).get("/apperr")
    assert r.status_code == 409
    assert r.json() == {"error": "Member is blocked", "code": "MEMBER_BLOCKED"}

def test_validation_error_does_not_echo_input():
    app = _app()
    @app.get("/n")
    def n(x: int):
        return x
    r = TestClient(app).get("/n", params={"x": "<script>"})
    assert r.status_code == 422
    assert r.json()["code"] == "ERR_VALIDATION"
    assert "<script>" not in r.text
```
`backend/tests/unit/test_health.py`:
```python
from fastapi.testclient import TestClient
from app.main import create_app

def test_nfr07_version_endpoint():
    r = TestClient(create_app(check_db=False)).get("/api/v1/version")
    assert r.status_code == 200
    assert r.json()["version"] == "1.0.0"
```

- [ ] **Step 4: Run the tests and confirm they fail**

Run: `cd backend && .venv/Scripts/pytest tests/unit -q`
Expected: FAIL with `ModuleNotFoundError: app.core.logging`.

- [ ] **Step 5: Implement**

`backend/app/core/config.py`:
```python
from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

def _read_version() -> str:
    for p in (Path(__file__).resolve().parents[3] / "VERSION", Path("/app/VERSION")):
        if p.exists():
            return p.read_text().strip()
    return "0.0.0"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore")
    environment: str = "dev"
    app_version: str = _read_version()
    database_url: str = "postgresql+psycopg://nexus_app:change-me@localhost:5433/nexus"
    owner_database_url: str = "postgresql+psycopg://nexus_owner:change-me@localhost:5433/nexus"
    jwt_secret: SecretStr = SecretStr("dev-only-change-me")
    access_token_minutes: int = 15
    refresh_token_hours: int = 8
    log_level: str = "INFO"
    adapter_email: str = "mock"
    adapter_sms: str = "mock"
    adapter_print: str = "mock"
    adapter_camera: str = "mock"
    adapter_credentials: str = "mock"
    adapter_legacy: str = "db"
    outbox_dir: str = "outbox"
    backup_dir: str = "../ops/backups"
    rate_limit_auth: str = "10/minute"
    rate_limit_devices: str = "600/minute"
    rate_limit_migration: str = "10/minute"
    upload_max_mb: int = 25
    sip2_listener_enabled: bool = False
    licence_file: str = "licence.json"
    licence_key: SecretStr = SecretStr("dev-licence-key")

@lru_cache
def get_settings() -> Settings:
    return Settings()
```
`backend/app/core/logging.py`:
```python
import json
import logging
import re
import sys
from datetime import UTC, datetime

_EMAIL = re.compile(r"\b([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE = re.compile(r"\+?\d[\d\- ]{7,}(\d{2})\b")
PII_KEYS = {"email", "phone", "full_name", "name", "card_uid", "smartcard_uid", "recipient", "password"}

def mask_pii(text: str) -> str:
    text = _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)
    return _PHONE.sub(lambda m: "***" + m.group(1), text)

def mask_mapping(data: dict) -> dict:
    return {k: ("***" if k in PII_KEYS and v else v) for k, v in data.items()}

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": mask_pii(record.getMessage()),
        }
        extra = getattr(record, "ctx", None)
        if isinstance(extra, dict):
            payload["ctx"] = mask_mapping(extra)
        if record.exc_info:
            payload["exc"] = mask_pii(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)

def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
```
`backend/app/core/errors.py`:
```python
import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("nexus.errors")

class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code

def _body(message: str, code: str, **extra: object) -> dict:
    return {"error": message, "code": code, **extra}

def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_body(exc.message, exc.code), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body("Invalid request", "ERR_VALIDATION", fields=fields), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        msg = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(_body(msg, f"ERR_HTTP_{exc.status_code}"), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return JSONResponse(_body("Internal Server Error", "ERR_INTERNAL"), status_code=500)
```
`backend/app/core/ratelimit.py`:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```
`backend/app/api/v1/health.py`:
```python
from fastapi import APIRouter, Request
from app.core.config import get_settings

router = APIRouter(tags=["operations"])

@router.get("/version")
def version(request: Request) -> dict:
    return {
        "version": get_settings().app_version,
        "alembic_rev": getattr(request.app.state, "alembic_rev", None),
        "licence": getattr(request.app.state, "licence_status", "unchecked"),
    }

@router.get("/health")
def health(request: Request) -> dict:
    checks = request.app.state.health_checks  # list[Callable[[], tuple[str, bool]]]
    results = {name: ok for name, ok in (c() for c in checks)}
    return {"status": "ok" if all(results.values()) else "degraded", "checks": results}
```
`backend/app/main.py`:
```python
from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.ratelimit import limiter
from app.api.v1 import health

def create_app(check_db: bool = True) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Nexus API", version=settings.app_version,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.limiter = limiter
    app.state.health_checks = []
    install_error_handlers(app)

    @app.exception_handler(RateLimitExceeded)
    async def _rl(_, __):  # noqa: ANN001
        return JSONResponse({"error": "Too many requests", "code": "ERR_RATE_LIMIT"}, status_code=429)

    app.include_router(health.router, prefix="/api/v1")
    return app

app = create_app()
```
`VERSION`: `1.0.0`

`.env.example`:
```
# Copy to .env and replace every value. Never commit .env.
NEXUS_VERSION=1.0.0
POSTGRES_USER=nexus_owner
POSTGRES_PASSWORD=replace-owner-password
POSTGRES_DB=nexus
NEXUS_APP_PASSWORD=replace-app-password
NEXUS_READONLY_PASSWORD=replace-readonly-password
DATABASE_URL=postgresql+psycopg://nexus_app:replace-app-password@db:5432/nexus
OWNER_DATABASE_URL=postgresql+psycopg://nexus_owner:replace-owner-password@db:5432/nexus
JWT_SECRET=replace-with-64-random-hex-chars
LICENCE_KEY=replace-with-licence-hmac-key
ADAPTER_EMAIL=mock
ADAPTER_SMS=mock
ADAPTER_PRINT=mock
ADAPTER_CAMERA=mock
ADAPTER_CREDENTIALS=mock
SIP2_LISTENER_ENABLED=false
```

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `cd backend && .venv/Scripts/pytest tests/unit -q`
Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add backend VERSION .env.example
git commit -m "feat: backend skeleton with config, JSON logging, sanitised errors and version endpoint"
```

---

### Task 2: Database, roles, models and baseline migration

**Files:**
- Create: `docker-compose.yml`, `docker-compose.dev.yml`, `ops/db/init/01-roles.sh`, `backend/app/db/{__init__,base}.py`, `backend/app/db/models/{__init__,legacy,identity,catalog,members,circulation,devices,notify,ops,staging}.py`, `backend/alembic.ini`, `backend/app/db/migrations/{env.py,script.py.mako}`, `backend/app/db/migrations/versions/0001_baseline.py`, `backend/tests/conftest.py`
- Test: `backend/tests/integration/test_db_integrity.py`

**Interfaces:**
- Produces:
  - `Base` (DeclarativeBase)
  - `engine`
  - `SessionLocal`
  - `get_session() -> Iterator[Session]`
  - ORM classes named after the tables in `docs/01-requirements/data-dictionary.md`, in PascalCase: `Bib`, `Item`, `Shelf`, `RfidTag`, `Member`, `CircPolicy`, `Loan`, `Fine`, `StaffUser`, `Role`, `Permission`, `RolePermission`, `RefreshToken`, `Device`, `DeviceEvent`, `GateEvent`, `Footfall`, `InventorySession`, `InventoryRead`, `NotificationOutbox`, `AuditLog`, `AppSetting`, `AppVersion`, `MigrationBatch`, `ImportRow`, `LegacyCatalogue`, `LegacyAccession`, `LegacyBorrower`.
  - Enums are Python `StrEnum`s in the same modules, e.g. `ItemStatus`, `ItemType`, `MemberStatus`, `TagStatus`, `LoanChannel`, `FineStatus`, `DeviceType`.
  - Test fixtures: `db_session`, `owner_conn`, `app_conn`.

- [ ] **Step 1: Compose files and role bootstrap**

`docker-compose.yml`:
```yaml
name: nexus
services:
  db:
    image: postgres:16.4-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      NEXUS_APP_PASSWORD: ${NEXUS_APP_PASSWORD}
      NEXUS_READONLY_PASSWORD: ${NEXUS_READONLY_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./ops/db/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      retries: 20
volumes:
  pgdata:
```
`docker-compose.dev.yml`:
```yaml
services:
  db:
    ports: ["5433:5432"]
```
`ops/db/init/01-roles.sh`:
```sh
#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_pw="$NEXUS_APP_PASSWORD" -v ro_pw="$NEXUS_READONLY_PASSWORD" <<'SQL'
CREATE ROLE nexus_app LOGIN PASSWORD :'app_pw';
CREATE ROLE nexus_readonly LOGIN PASSWORD :'ro_pw';
CREATE ROLE legacy_owner NOLOGIN;
SQL
```
Run: `cp .env.example .env` (fill in dev values; local test fixtures default to owner password `devowner` and app password `devapp`, so use those in the dev `.env`, or set `TEST_*DATABASE_URL`), then `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db`
Expected: `docker compose ps` shows db `healthy`.

- [ ] **Step 2: Base and session**

`backend/app/db/base.py`:
```python
from collections.abc import Iterator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.core.config import get_settings

class Base(DeclarativeBase):
    pass

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

- [ ] **Step 3: Models**

Write one module per aggregate. Each column follows the data dictionary exactly. The following example shows the conventions to use everywhere: UUID primary keys, `StrEnum` stored as native PG enums, schema-qualified tables, and partial unique indexes:

`backend/app/db/models/catalog.py`:
```python
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from sqlalchemy import Enum, ForeignKey, Index, Numeric, String, Text, func, text as sa_text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

S = {"schema": "nexus"}

class RecordSource(StrEnum):
    legacy = "legacy"; nexus = "nexus"; migration = "migration"

class ItemType(StrEnum):
    lending = "lending"; reference = "reference"

class ItemStatus(StrEnum):
    available = "available"; on_loan = "on_loan"; missing = "missing"
    in_repair = "in_repair"; withdrawn = "withdrawn"

class TagTarget(StrEnum):
    item = "item"; member = "member"

class TagStatus(StrEnum):
    active = "active"; retired = "retired"

class Bib(Base):
    __tablename__ = "bib"; __table_args__ = (Index("ix_bib_search", "search_tsv", postgresql_using="gin"), S)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    isbn: Mapped[str | None] = mapped_column(String(17))
    publisher: Mapped[str | None] = mapped_column(Text)
    pub_year: Mapped[int | None]
    edition: Mapped[str | None] = mapped_column(Text)
    subjects: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[RecordSource] = mapped_column(Enum(RecordSource, name="record_source", schema="nexus"))
    legacy_ref: Mapped[str | None] = mapped_column(String(40))
    migration_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    search_tsv: Mapped[str | None] = mapped_column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    items: Mapped[list["Item"]] = relationship(back_populates="bib")

class Shelf(Base):
    __tablename__ = "shelf"; __table_args__ = S
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    call_no_from: Mapped[str | None] = mapped_column(String(40))
    call_no_to: Mapped[str | None] = mapped_column(String(40))

class Item(Base):
    __tablename__ = "item"; __table_args__ = S
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bib_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nexus.bib.id"))
    accession_no: Mapped[str] = mapped_column(String(20), unique=True)
    barcode: Mapped[str] = mapped_column(String(32), unique=True)
    call_no: Mapped[str | None] = mapped_column(String(40))
    shelf_code: Mapped[str | None] = mapped_column(ForeignKey("nexus.shelf.code"))
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType, name="item_type", schema="nexus"))
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus, name="item_status", schema="nexus"),
                                               default=ItemStatus.available)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    acquired_on: Mapped[date | None]
    legacy_ref: Mapped[str | None] = mapped_column(String(40))
    migration_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    bib: Mapped[Bib] = relationship(back_populates="items")

class RfidTag(Base):
    __tablename__ = "rfid_tag"
    __table_args__ = (
        Index("uq_tag_active_item", "item_id", unique=True, postgresql_where=sa_text("status = 'active'")),
        Index("uq_tag_active_member", "member_id", unique=True, postgresql_where=sa_text("status = 'active'")),
        S,
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    epc: Mapped[str] = mapped_column(String(32), unique=True)
    target_type: Mapped[TagTarget] = mapped_column(Enum(TagTarget, name="tag_target", schema="nexus"))
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nexus.item.id"))
    member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("nexus.member.id"))
    security_bit: Mapped[bool] = mapped_column(default=True)
    status: Mapped[TagStatus] = mapped_column(Enum(TagStatus, name="tag_status", schema="nexus"),
                                              default=TagStatus.active)
    encoded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    encoded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    retired_at: Mapped[datetime | None]
    retire_reason: Mapped[str | None] = mapped_column(Text)
```
> `sa_text` here is SQLAlchemy's DDL helper for an index predicate in model metadata. It is not a query, so it doesn't count against ADR-0003. The lint rule in Task 6 allows it only under `app/db/models/`.

Write the remaining modules (`legacy`, `identity`, `members`, `circulation`, `devices`, `notify`, `ops`, `staging`) using the same pattern and the exact columns in the data dictionary. Points that need care:
- `Loan`: partial unique index `uq_loan_open_item` on `item_id` WHERE `returned_at IS NULL`.
- `DeviceEvent.event_id`: unique.
- `AuditLog.id`: `BigInteger` identity; `details` as JSONB.
- `ImportRow`: lives in schema `staging`, composite primary key `(batch_id, row_no)`, `reasons` as `ARRAY(Text)`.
- Legacy models (`LegacyCatalogue` → `legacy_ilms.catalogue`, `LegacyAccession` → `legacy_ilms.accession`, `LegacyBorrower` → `legacy_ilms.borrower`): schema `legacy_ilms`, no relationships to `nexus`.
- `app/db/models/__init__.py` imports every module, so `Base.metadata` is complete for Alembic.

- [ ] **Step 4: Alembic environment and baseline revision**

`backend/alembic.ini` sets `script_location = app/db/migrations`. In `env.py`, read `get_settings().owner_database_url`, set `target_metadata = Base.metadata`, `include_schemas=True`, and `version_table_schema="nexus"`. Run `CREATE SCHEMA IF NOT EXISTS nexus` before configuring, because the version table lives there.

Generate the table DDL:
Run: `cd backend && .venv/Scripts/alembic revision --autogenerate -m "baseline" --rev-id 0001`
Then rename the file to `0001_baseline.py` and add the hand-written parts below.

At the **top** of `upgrade()`:
```python
op.execute("CREATE SCHEMA IF NOT EXISTS staging")
op.execute("CREATE SCHEMA IF NOT EXISTS legacy_ilms AUTHORIZATION legacy_owner")
```
Wrap the three `legacy_ilms` `create_table` calls between `op.execute("SET ROLE legacy_owner")` and `op.execute("RESET ROLE")`, so the legacy tables are owned by `legacy_owner`.

At the **end** of `upgrade()`:
```python
op.execute("""
CREATE FUNCTION nexus.bib_tsv_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_tsv :=
    setweight(to_tsvector('simple', coalesce(NEW.title,'')), 'A') ||
    setweight(to_tsvector('simple', coalesce(NEW.author,'')), 'B') ||
    setweight(to_tsvector('simple', coalesce(NEW.subjects,'')), 'C') ||
    setweight(to_tsvector('simple', coalesce(NEW.publisher,'') || ' ' || coalesce(NEW.isbn,'')), 'D');
  RETURN NEW;
END $$;
CREATE TRIGGER bib_tsv BEFORE INSERT OR UPDATE ON nexus.bib
  FOR EACH ROW EXECUTE FUNCTION nexus.bib_tsv_update();
""")
op.execute("""
GRANT USAGE ON SCHEMA legacy_ilms TO nexus_app, nexus_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA legacy_ilms TO nexus_app, nexus_readonly;
GRANT USAGE ON SCHEMA nexus, staging TO nexus_app;
GRANT USAGE ON SCHEMA nexus TO nexus_readonly;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA nexus TO nexus_app;
REVOKE UPDATE, DELETE, TRUNCATE ON nexus.audit_log FROM nexus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA staging TO nexus_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA nexus, staging TO nexus_app;
GRANT SELECT ON ALL TABLES IN SCHEMA nexus TO nexus_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA nexus GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nexus_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA nexus GRANT SELECT ON TABLES TO nexus_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA nexus GRANT USAGE, SELECT ON SEQUENCES TO nexus_app;
""")
```
`downgrade()` drops the trigger and function, then the autogenerated tables in reverse order, then `DROP SCHEMA staging CASCADE` and `DROP SCHEMA legacy_ilms CASCADE`.

- [ ] **Step 5: Test fixtures**

`backend/tests/conftest.py`:
```python
import os
import subprocess
import sys
from collections.abc import Iterator
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

BASE_APP = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://nexus_app:devapp@localhost:5433/nexus_test")
BASE_OWNER = os.environ.get("TEST_OWNER_DATABASE_URL",
                            "postgresql+psycopg://nexus_owner:devowner@localhost:5433/nexus_test")

@pytest.fixture(scope="session")
def migrated_db() -> Iterator[None]:
    owner = make_url(BASE_OWNER)
    admin = create_engine(owner.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{owner.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{owner.database}"'))
    env = {**os.environ, "OWNER_DATABASE_URL": BASE_OWNER, "DATABASE_URL": BASE_APP}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env,
                   cwd=os.path.dirname(__file__) + "/..")
    os.environ["DATABASE_URL"] = BASE_APP
    yield

@pytest.fixture
def owner_conn(migrated_db):
    eng = create_engine(BASE_OWNER)
    with eng.connect() as c:
        tx = c.begin()
        yield c
        tx.rollback()

@pytest.fixture
def app_conn(migrated_db):
    eng = create_engine(BASE_APP)
    with eng.connect() as c:
        tx = c.begin()
        yield c
        tx.rollback()

@pytest.fixture
def db_session(app_conn) -> Iterator[Session]:
    s = Session(bind=app_conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()
```
Mark every DB test module with `pytestmark = pytest.mark.db`.

- [ ] **Step 6: Write the failing integrity tests**

`backend/tests/integration/test_db_integrity.py`:
```python
import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

pytestmark = pytest.mark.db

def _seed_legacy(owner_conn):
    owner_conn.execute(text("SET ROLE legacy_owner"))
    owner_conn.execute(text("INSERT INTO legacy_ilms.catalogue (bib_no, title) VALUES (1, 'Legacy Title')"))
    owner_conn.execute(text("RESET ROLE"))

def test_nfr01_app_role_can_read_legacy(app_conn):
    assert app_conn.execute(text("SELECT count(*) FROM legacy_ilms.catalogue")).scalar() >= 0

@pytest.mark.parametrize("stmt", [
    "UPDATE legacy_ilms.catalogue SET title = 'x'",
    "DELETE FROM legacy_ilms.catalogue",
    "INSERT INTO legacy_ilms.catalogue (bib_no, title) VALUES (99, 'x')",
    "TRUNCATE legacy_ilms.catalogue",
])
def test_nfr01_app_role_cannot_modify_legacy(app_conn, stmt):
    with pytest.raises(ProgrammingError, match="permission denied"):
        app_conn.execute(text(stmt))

def test_nfr02_audit_log_is_append_only(app_conn):
    app_conn.execute(text("INSERT INTO nexus.audit_log (actor_type, action, entity_type) "
                          "VALUES ('system','test','none')"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        app_conn.execute(text("UPDATE nexus.audit_log SET action = 'tampered'"))

def test_fr02_search_vector_maintained_by_trigger(app_conn):
    app_conn.execute(text("INSERT INTO nexus.bib (id, title, author, source) "
                          "VALUES (gen_random_uuid(), 'Wireless Sensor Networks', 'Rao', 'nexus')"))
    hits = app_conn.execute(text("SELECT count(*) FROM nexus.bib "
                                 "WHERE search_tsv @@ plainto_tsquery('simple', 'sensor rao')")).scalar()
    assert hits == 1
```

- [ ] **Step 7: Run and iterate until green**

Run: `cd backend && .venv/Scripts/pytest tests/integration/test_db_integrity.py -v`
Expected first: FAIL (no migration/schema). After Steps 3–4 are complete: 7 passed.
Then check that rollback works: `alembic downgrade base && alembic upgrade head` against the dev database completes without errors.

- [ ] **Step 8: Commit**

```bash
git add docker-compose*.yml ops/db backend
git commit -m "feat: database schemas, read-only legacy role, models and baseline migration (NFR 01)"
```

---

### Task 3: Authentication, tokens and RBAC

**Files:**
- Create: `backend/app/core/security.py`, `backend/app/core/auth.py`, `backend/app/services/users.py`, `backend/app/api/v1/auth.py`, `backend/app/db/migrations/versions/0002_rbac_seed.py`
- Modify: `backend/app/main.py` (include auth router)
- Test: `backend/tests/unit/test_security.py`, `backend/tests/integration/test_auth.py`, `backend/tests/factories.py`

**Interfaces:**
- Consumes: `get_session`, `StaffUser`, `Member`, `Role`, `RolePermission`, `RefreshToken`, `AppError`, `limiter`.
- Produces:
  - `hash_password(pw: str) -> str`
  - `verify_password(hash_: str, pw: str) -> bool`
  - `create_access_token(sub: uuid.UUID, typ: Literal["staff","patron"], role: str) -> str`
  - `decode_access_token(token: str) -> dict` (raises `AppError("ERR_TOKEN_INVALID", ..., 401)`)
  - `issue_refresh_token(session, typ, sub, family_id: uuid.UUID | None = None) -> str`
  - `rotate_refresh_token(session, raw: str) -> tuple[str, str, str]` (`typ, sub, new_raw`)
  - `@dataclass(frozen=True) Principal(typ: str, id: uuid.UUID, role: str, permissions: frozenset[str])`
  - `get_principal(request, session) -> Principal`
  - `require(perm: str) -> Depends[Principal]`
  - `ensure_self_or(principal: Principal, member_id: uuid.UUID, perm: str) -> None`
  - `issue_tokens(session, typ, sub, role) -> dict` (`{access_token, refresh_token, token_type, expires_in}`)
  - `authenticate_password(session, username, password) -> tuple[typ, id, role]`
  - Endpoints from interface design §1 "Authentication", except smart card (Task 16).
  - Test factories: `make_staff(session, role: str, username=None, password="Passw0rd!x", smartcard_uid=None) -> StaffUser` and `make_member(session, category="UG", status="active", password=None) -> Member`.

- [ ] **Step 1: RBAC seed migration**

`0002_rbac_seed.py` inserts the five roles, every permission code from security-design §3, and the role→permission rows exactly as the RBAC matrix shows. Permissions marked "self" are not granted to Patron; route-level `ensure_self_or` handles them. Patron gets `catalog.read`. Also seed `circ_policy` rows:

| category | loan_days | max_items | max_renewals | fine_per_day | fine_limit | can_borrow_reference |
|---|---|---|---|---|---|---|
| UG | 14 | 4 | 2 | 2.00 | 100.00 | false |
| PG | 21 | 6 | 3 | 2.00 | 150.00 | false |
| FAC | 60 | 15 | 5 | 0.00 | 500.00 | true |
| STAFF | 30 | 8 | 3 | 1.00 | 200.00 | false |

The `downgrade()` deletes those rows.

- [ ] **Step 2: Write the failing tests**

`backend/tests/unit/test_security.py`:
```python
import uuid
import pytest
from app.core.errors import AppError
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password

def test_nfr02_password_hash_is_argon2_and_verifies():
    h = hash_password("Correct-Horse-1")
    assert h.startswith("$argon2id$") and "Correct-Horse-1" not in h
    assert verify_password(h, "Correct-Horse-1")
    assert not verify_password(h, "wrong")

def test_nfr02_tampered_token_rejected():
    tok = create_access_token(uuid.uuid4(), "staff", "Admin")
    bad = tok[:-2] + ("AA" if tok[-2:] != "AA" else "BB")
    with pytest.raises(AppError) as e:
        decode_access_token(bad)
    assert e.value.code == "ERR_TOKEN_INVALID"
```
`backend/tests/integration/test_auth.py`:
```python
import pytest
from fastapi.testclient import TestClient
from app.core.ratelimit import limiter
from app.db.base import get_session
from app.main import create_app
from tests.factories import make_member, make_staff

pytestmark = pytest.mark.db

@pytest.fixture
def client(db_session):
    app = create_app(check_db=False)
    app.dependency_overrides[get_session] = lambda: db_session
    limiter.reset()
    return TestClient(app)

def _login(client, u, p="Passw0rd!x"):
    return client.post("/api/v1/auth/login", json={"username": u, "password": p})

def test_nfr02_login_success_and_me(client, db_session):
    make_staff(db_session, "Librarian", username="lib1")
    r = _login(client, "lib1")
    assert r.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["role"] == "Librarian" and "catalog.write" in me.json()["permissions"]

def test_nfr02_bad_password_generic_error(client, db_session):
    make_staff(db_session, "Librarian", username="lib2")
    for u in ("lib2", "nobody"):
        r = _login(client, u, "wrong")
        assert r.status_code == 401 and r.json()["code"] == "INVALID_CREDENTIALS"

def test_nfr02_login_rate_limited(client, db_session):
    codes = [_login(client, "x", "y").status_code for _ in range(11)]
    assert codes[-1] == 429

def test_nfr02_refresh_rotation_and_reuse_detection(client, db_session):
    make_staff(db_session, "CirculationClerk", username="clerk1")
    first = _login(client, "clerk1").json()["refresh_token"]
    second = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert second.status_code == 200
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert reuse.status_code == 401 and reuse.json()["code"] == "ERR_TOKEN_REUSED"
    # whole family revoked
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": second.json()["refresh_token"]})
    assert again.status_code == 401

def test_nfr02_role_change_effective_immediately(client, db_session):
    from app.db.models import Role
    u = make_staff(db_session, "Admin", username="adm1")
    tok = _login(client, "adm1").json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert "admin.users.write" in client.get("/api/v1/auth/me", headers=h).json()["permissions"]
    u.role_id = db_session.query(Role).filter_by(name="Auditor").one().id
    db_session.flush()
    assert "admin.users.write" not in client.get("/api/v1/auth/me", headers=h).json()["permissions"]

def test_nfr02_patron_logs_in_with_card_number(client, db_session):
    m = make_member(db_session, password="Passw0rd!x")
    r = _login(client, m.card_no)
    assert r.status_code == 200
```

- [ ] **Step 3: Run and confirm failure**

Run: `.venv/Scripts/pytest tests/unit/test_security.py tests/integration/test_auth.py -q`
Expected: FAIL (`ModuleNotFoundError: app.core.security`).

- [ ] **Step 4: Implement**

`backend/app/core/security.py`:
```python
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import RefreshToken

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
Typ = Literal["staff", "patron"]

def hash_password(pw: str) -> str:
    return _ph.hash(pw)

def verify_password(hash_: str, pw: str) -> bool:
    try:
        return _ph.verify(hash_, pw)
    except (VerificationError, InvalidHashError):
        return False

def create_access_token(sub: uuid.UUID, typ: Typ, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    claims = {"sub": str(sub), "typ": typ, "role": role, "jti": uuid.uuid4().hex,
              "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(claims, s.jwt_secret.get_secret_value(), algorithm="HS256")

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().jwt_secret.get_secret_value(), algorithms=["HS256"],
                          options={"require": ["exp", "sub", "typ"]})
    except jwt.PyJWTError as exc:
        raise AppError("ERR_TOKEN_INVALID", "Invalid or expired token", 401) from exc

def _h(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def issue_refresh_token(session: Session, typ: Typ, sub: uuid.UUID, family_id: uuid.UUID | None = None) -> str:
    raw = secrets.token_urlsafe(32)
    session.add(RefreshToken(family_id=family_id or uuid.uuid4(), subject_type=typ, subject_id=sub,
                             token_hash=_h(raw),
                             expires_at=datetime.now(UTC) + timedelta(hours=get_settings().refresh_token_hours)))
    return raw

def rotate_refresh_token(session: Session, raw: str) -> tuple[str, uuid.UUID, str]:
    row = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _h(raw)))
    now = datetime.now(UTC)
    if row is None or row.expires_at < now:
        raise AppError("ERR_TOKEN_INVALID", "Invalid or expired token", 401)
    if row.revoked_at is not None:
        session.execute(update(RefreshToken).where(RefreshToken.family_id == row.family_id)
                        .values(revoked_at=now))
        session.commit()
        raise AppError("ERR_TOKEN_REUSED", "Token reuse detected", 401)
    row.revoked_at = now
    new_raw = issue_refresh_token(session, row.subject_type, row.subject_id, row.family_id)
    return row.subject_type, row.subject_id, new_raw
```
`backend/app/core/auth.py`:
```python
import uuid
from dataclasses import dataclass
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.base import get_session
from app.db.models import Member, MemberStatus, Role, RolePermission, StaffUser

@dataclass(frozen=True)
class Principal:
    typ: str
    id: uuid.UUID
    role: str
    permissions: frozenset[str]

def _perms_for_role(session: Session, role_name: str) -> frozenset[str]:
    q = select(RolePermission.permission_code).join(Role, Role.id == RolePermission.role_id) \
        .where(Role.name == role_name)
    return frozenset(session.scalars(q))

def get_principal(request: Request, session: Session = Depends(get_session)) -> Principal:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise AppError("ERR_UNAUTHENTICATED", "Authentication required", 401)
    claims = decode_access_token(header[7:])
    sub = uuid.UUID(claims["sub"])
    if claims["typ"] == "staff":
        user = session.get(StaffUser, sub)
        if user is None or not user.is_active:
            raise AppError("ERR_UNAUTHENTICATED", "Authentication required", 401)
        role = session.get(Role, user.role_id).name
    else:
        member = session.get(Member, sub)
        if member is None or member.status == MemberStatus.expired:
            raise AppError("ERR_UNAUTHENTICATED", "Authentication required", 401)
        role = "Patron"
    return Principal(claims["typ"], sub, role, _perms_for_role(session, role))

def require(perm: str):
    def dep(principal: Principal = Depends(get_principal)) -> Principal:
        if perm not in principal.permissions:
            raise AppError("ERR_FORBIDDEN", "Not permitted", 403)
        return principal
    return dep

def ensure_self_or(principal: Principal, member_id: uuid.UUID, perm: str) -> None:
    if principal.typ == "patron" and principal.id == member_id:
        return
    if perm in principal.permissions:
        return
    raise AppError("ERR_FORBIDDEN", "Not permitted", 403)
```
`backend/app/services/users.py`:
- `authenticate_password(session, username, password)` looks up `StaffUser.username == username`, falling back to `Member.card_no == username`.
- Use `verify_password`, and run a dummy verify when the user isn't found, so timing is equal.
- On failure: `AppError("INVALID_CREDENTIALS", "Invalid username or password", 401)`.
- On success: set `last_login_at` and return `(typ, id, role_name)`.
- `issue_tokens(...)` builds the token response dict.

`backend/app/api/v1/auth.py` wires these up:
- `@limiter.limit(get_settings().rate_limit_auth)` on login and refresh. The handler signature needs `request: Request`.
- Pydantic models `LoginIn(username: constr(min_length=1, max_length=64), password: constr(min_length=1, max_length=128))` and `RefreshIn(refresh_token: constr(min_length=20, max_length=128))`. Use `model_config = ConfigDict(extra="forbid")`.
- `logout` revokes the presented refresh token.
- `/me` returns `{id, typ, role, permissions: sorted(list)}`.
- Every successful and failed login writes an audit row. `audit()` arrives in Task 4: implement this task first, then add the audit calls in Task 4 Step 3.

`backend/tests/factories.py`:
- `make_staff` creates a `StaffUser` with `hash_password(password)` and the named role.
- `make_member` creates a `Member` with a unique `card_no` (`"M" + 6 random digits`), `full_name="Test Member"`, `email="member@example.org"` and the given category/status. It hashes the password if one is given.
- Both call `session.flush()` and return the object.

- [ ] **Step 5: Run and confirm green**

Run: `.venv/Scripts/pytest tests -q -m "not acceptance"`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: argon2 password auth, rotating refresh tokens, RBAC permissions and policies seed (NFR 02)"
```

---

### Task 4: Audit service, legacy connector and synthetic seed data

**Files:**
- Create: `backend/app/core/audit.py`, `backend/app/integrations/{__init__,base,registry,legacy_db}.py`, `backend/app/db/seed.py`
- Modify: `backend/app/api/v1/auth.py` (audit login events)
- Test: `backend/tests/integration/test_audit.py`, `backend/tests/integration/test_seed.py`

**Interfaces:**
- Produces:
  - `audit(session, *, actor_type: str, actor_id: uuid.UUID | None, action: str, entity_type: str, entity_id: str | None = None, details: dict | None = None, ip: str | None = None) -> None`. It adds the row without committing; the caller's transaction owns it. `details` pass through `mask_mapping`.
  - `class LegacyIlmsConnector(Protocol)` with `iter_catalogue()`, `iter_accessions()`, `iter_borrowers()`, `get_accession(acc_no) -> LegacyAccession | None`. Implementation `DbLegacyConnector(session)`.
  - `get_adapter(kind: Literal["email","sms","print","camera","credentials","legacy"], session=None)` in `registry.py`.
  - `python -m app.db.seed [--legacy N] [--demo] [--reset-demo]`:
    - `--legacy N` (owner connection, `SET ROLE legacy_owner`) inserts N bibs, ~1.2·N accessions and 300 borrowers with Faker seed 42, but only if the tables are empty.
    - `--demo` mirrors legacy rows into `nexus` through `DbLegacyConnector` (`source=legacy`, `legacy_ref` set), creates 8 shelves `A-01`…`D-02` with call-number ranges, 6 devices (interface design §5) with generated API keys, one staff user per role with a random password and a random 8-hex smart-card UID, plus some loans, fines and gate events for the dashboard.
    - Credentials and device keys are printed once and written to `ops/demo-credentials.txt` (gitignored).
  - Task 5 adds `mirror_legacy(session) -> dict[str, int]` (counts); the seed calls it.

- [ ] **Step 1: Write the failing tests**

`backend/tests/integration/test_audit.py`:
```python
import pytest
from sqlalchemy import select
from app.core.audit import audit
from app.db.models import AuditLog

pytestmark = pytest.mark.db

def test_nfr02_audit_masks_pii_details(db_session):
    audit(db_session, actor_type="system", actor_id=None, action="member.update", entity_type="member",
          entity_id="m1", details={"email": "x@example.org", "status": "blocked"})
    db_session.flush()
    row = db_session.scalars(select(AuditLog).where(AuditLog.entity_id == "m1")).one()
    assert row.details == {"email": "***", "status": "blocked"}
```
`backend/tests/integration/test_seed.py`:
```python
import pytest
from sqlalchemy import func, select
from app.db.models import Bib, Item, LegacyCatalogue
from app.db.seed import mirror_legacy, seed_legacy

pytestmark = pytest.mark.db

def test_nfr01_mirror_copies_without_touching_legacy(owner_conn, db_session):
    seed_legacy(owner_conn, n_bibs=50)
    before = owner_conn.execute(select(func.count()).select_from(LegacyCatalogue)).scalar()
    counts = mirror_legacy(db_session)
    assert counts["bibs"] == 50
    assert db_session.scalar(select(func.count()).select_from(Bib).where(Bib.source == "legacy")) == 50
    assert db_session.scalar(select(func.count()).select_from(Item)) >= 50
    # second mirror is idempotent
    assert mirror_legacy(db_session)["bibs"] == 0
    assert owner_conn.execute(select(func.count()).select_from(LegacyCatalogue)).scalar() == before
```
> `owner_conn` and `db_session` are separate connections. For this test, `seed_legacy` commits on its own owner connection (`owner_conn.commit()`), and the test starts with a `TRUNCATE` of legacy tables via `owner_conn`. Document this in the test docstring.

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/Scripts/pytest tests/integration/test_audit.py tests/integration/test_seed.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

`backend/app/core/audit.py`:
```python
import uuid
from sqlalchemy.orm import Session
from app.core.logging import mask_mapping
from app.db.models import AuditLog

def audit(session: Session, *, actor_type: str, actor_id: uuid.UUID | None, action: str, entity_type: str,
          entity_id: str | None = None, details: dict | None = None, ip: str | None = None) -> None:
    session.add(AuditLog(actor_type=actor_type, actor_id=actor_id, action=action, entity_type=entity_type,
                         entity_id=entity_id, details=mask_mapping(details or {}), ip=ip))
```
For `integrations/base.py`, define a `typing.Protocol` for every adapter in interface design §4 (`NotificationChannel.send(msg: OutboundMessage) -> DeliveryResult`, `CameraProvider.snapshot(camera_code: str, context: dict) -> bytes`, `CredentialProvider.resolve(card_uid: str) -> StaffIdentity | None`, `LegacyIlmsConnector`), plus the dataclasses `OutboundMessage(channel, recipient, subject, body)`, `DeliveryResult(ok: bool, error: str | None)` and `StaffIdentity(user_id, role)`.

`registry.get_adapter` maps `(kind, settings value)` to classes. An unknown value raises `AppError("ERR_CONFIG", ...)` at startup.

`seed.py` uses `Faker("en_IN")` with `Faker.seed(42)` and `random.Random(42)`:
- **Accession numbers:** `ACC-{n:06d}`
- **Barcodes:** `BC{n:08d}`
- **ISBN-13** with a valid check digit:
  ```python
  def isbn13(r):
      d = [9, 7, 8] + [r.randint(0, 9) for _ in range(9)]
      c = (10 - sum(x * (3 if i % 2 else 1) for i, x in enumerate(d)) % 10) % 10
      return "".join(map(str, d + [c]))
  ```
- **Call numbers:** DDC-like `"{ddc:03d}.{r.randint(0, 99):02d} {author[:3].upper()}"`; the shelf is chosen by DDC range.
- **Reference items:** about 10% are `reference`.

`mirror_legacy(session)`:
- Insert `Bib` for each `LegacyCatalogue` whose `str(bib_no)` is not yet a `legacy_ref`.
- Insert `Item` for each `LegacyAccession`, mapping status `AV→available`, `IS→on_loan`, `LS→missing`, `WD→withdrawn`.
- Insert `Member` for each `LegacyBorrower`.
- Write one `audit(action="legacy.mirror")` row with the counts, and return the counts.

Add the audit calls to `auth.py`: `auth.login.success`, `auth.login.failure` (details contain the username length only, never the username itself), `auth.logout`.

- [ ] **Step 4: Run and confirm green**

Run: `.venv/Scripts/pytest tests -q -m "not acceptance"`
Expected: all pass.

- [ ] **Step 5: Seed the dev database by hand**

Run:
```bash
cd backend
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.db.seed --legacy 2000 --demo
```
Expected: prints counts (≈2000 bibs, ≈2400 items, 300 members, 5 staff, 6 devices) and the credentials file path.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: audit trail, adapter registry, read-only legacy connector and synthetic seed data"
```

---

### Task 5: Frontend skeleton with login and permission-aware layout

**Files:**
- Create: `frontend/` (Vite React TS), `frontend/src/api/client.ts`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/components/Layout.tsx`, `frontend/src/App.tsx`, `frontend/src/api/client.test.ts`
- Modify: `backend/app/main.py` (CORS for `http://localhost:5173` in dev only)

**Interfaces:**
- Produces:
  - `api<T>(path: string, init?: RequestInit): Promise<T>`. It attaches the bearer token, refreshes once on 401, then retries, and throws `ApiError{code, message, status}`.
  - `useAuth(): {user, permissions: Set<string>, login(u,p), loginWithTokens(t), logout()}`.
  - `<RequirePermission perm="...">` hides UI the user can't use. The server still enforces every check.
  - Nav items are declared as `{path, label, icon, perm}`.

- [ ] **Step 1: Scaffold and pin**

Run:
```bash
npm create vite@5.5.2 frontend -- --template react-ts
cd frontend
npm i react-router-dom@6.26.2 @tanstack/react-query@5.59.0 lucide-react@0.447.0 recharts@2.12.7
npm i -D tailwindcss@3.4.13 postcss@8.4.47 autoprefixer@10.4.20 vitest@2.1.2 jsdom@25.0.1
npx tailwindcss init -p
```
Then set `"save-exact": true` in `frontend/.npmrc`, and check that `package-lock.json` exists.

- [ ] **Step 2: Write the failing test**

`frontend/src/api/client.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, setTokens, ApiError } from "./client";

describe("api client", () => {
  beforeEach(() => setTokens({ access_token: "old", refresh_token: "r1" }));

  it("refreshes once on 401 and retries", async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: "x", code: "ERR_TOKEN_INVALID" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "new", refresh_token: "r2" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", f);
    expect(await api<{ ok: boolean }>("/x")).toEqual({ ok: true });
    expect(f.mock.calls[2][1].headers.Authorization).toBe("Bearer new");
  });

  it("throws ApiError with server code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: "Member is blocked", code: "MEMBER_BLOCKED" }), { status: 409 })));
    await expect(api("/y")).rejects.toMatchObject({ code: "MEMBER_BLOCKED", status: 409 } as Partial<ApiError>);
  });
});
```
Run: `npx vitest run`
Expected: FAIL (`./client` not found).

- [ ] **Step 3: Implement `client.ts`**

```ts
export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); }
}
type Tokens = { access_token: string; refresh_token: string };
let tokens: Tokens | null = null;
export const setTokens = (t: Tokens | null) => { tokens = t; };
export const getTokens = () => tokens;
const BASE = "/api/v1";

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers as any) };
  if (tokens) headers.Authorization = `Bearer ${tokens.access_token}`;
  return fetch(BASE + path, { ...init, headers });
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await raw(path, init);
  if (res.status === 401 && tokens) {
    const r = await fetch(BASE + "/auth/refresh", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refresh_token }) });
    if (r.ok) { setTokens(await r.json()); res = await raw(path, init); } else { setTokens(null); }
  }
  const body = res.headers.get("content-type")?.includes("json") || res.status >= 400
    ? await res.json().catch(() => ({})) : await res.blob();
  if (!res.ok) throw new ApiError(body.code ?? "ERR_UNKNOWN", body.error ?? "Request failed", res.status);
  return body as T;
}
```
Tokens are kept in memory only, never in `localStorage`, so XSS can't read persisted tokens. A page reload asks the user to log in again, which is acceptable for staff terminals.

- [ ] **Step 4: Login page, auth context, layout**

- `LoginPage` has a username/password form and a "Tap staff card" button. The button is disabled until Task 16 ships the smart-card flow.
- `Layout` shows a left nav filtered by `permissions`, with the app version in the footer from `/api/v1/version`.
- Routes: `/login`, `/` (dashboard placeholder), `/opac` (public).
- Configure the Vite dev proxy: `/api` → `http://localhost:8000`.
- Tailwind palette: slate plus one accent (indigo).

- [ ] **Step 5: Verify**

Run: `npx vitest run && npm run build`
Expected: 2 tests passed; build succeeds.

Manual check:
1. Run `uvicorn app.main:app --reload` in `backend` and `npm run dev` in `frontend`.
2. Log in as the seeded librarian.
3. The nav shows Librarian items; the version footer shows `1.0.0`.

- [ ] **Step 6: Commit**

```bash
git add frontend backend/app/main.py
git commit -m "feat: React shell with in-memory token auth, refresh handling and permission-aware navigation"
```

---

### Task 6: Containers, build pipeline, static checks and Stage 3 gate

**Files:**
- Create: `backend/Dockerfile`, `frontend/Dockerfile`, `ops/nginx/nginx.conf`, `ops/nginx/gen-cert.sh`, `.github/workflows/ci.yml`, `backend/tests/unit/test_no_raw_sql.py`, `docs/06-testing/baseline-test-report.md`, `docs/00-project-control/stage-gates/stage-3.md`
- Modify: `docker-compose.yml` (add `api`, `web`), `README.md` (build/run section), `docs/01-requirements/rtm.md`, `docs/00-project-control/progress-log.md`, `docs/00-project-control/issue-tracker.md`

**Interfaces:**
- Produces: `docker compose up -d` brings up `db`, `api` (runs `alembic upgrade head` then uvicorn) and `web` (nginx: HTTPS on 8443 for dev, the built UI, and `/api` proxied to `api:8000`).

- [ ] **Step 1: Write the failing lint-rule test (ADR-0003)**

`backend/tests/unit/test_no_raw_sql.py`:
```python
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2] / "app"
ALLOWED = {"db/migrations", "db/models", "db/seed.py"}
PATTERN = re.compile(r"\b(text\(|sa_text\(|exec_driver_sql\()")

def test_adr0003_no_raw_sql_in_application_code():
    offenders = []
    for f in ROOT.rglob("*.py"):
        rel = f.relative_to(ROOT).as_posix()
        if any(rel.startswith(a) for a in ALLOWED):
            continue
        if PATTERN.search(f.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert offenders == []
```
> `seed.py` is allowed because it runs `SET ROLE legacy_owner` as the owner (operations tooling). Add that to the ADR-0003 allowed list in the same commit.

Run: `.venv/Scripts/pytest tests/unit/test_no_raw_sql.py -q`
Expected: PASS. If it fails, move the offending code before continuing.

- [ ] **Step 2: Dockerfiles**

`backend/Dockerfile`:
```dockerfile
FROM python:3.12.7-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY VERSION /app/VERSION
COPY backend/ .
RUN useradd -r -u 10001 nexus && mkdir -p /app/outbox /backups && chown -R nexus /app /backups
USER nexus
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
```
`frontend/Dockerfile`:
```dockerfile
FROM node:20.17-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:1.27.2-alpine
COPY ops/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
```
`ops/nginx/nginx.conf`:
- server 443 ssl using `/etc/nginx/certs/nexus.crt|key` (volume mounted)
- `ssl_protocols TLSv1.2 TLSv1.3`
- headers: `Strict-Transport-Security`, `Content-Security-Policy "default-src 'self'; img-src 'self' data:; connect-src 'self' wss:"`, `X-Content-Type-Options nosniff`, `X-Frame-Options DENY`
- `location /api/` → `proxy_pass http://api:8000`, with the WebSocket upgrade headers for `/api/v1/ws` and `/api/v1/devices/`
- `location /ncip` → api
- `location /` → `try_files $uri /index.html`
- `client_max_body_size 25m`
- port 80 → 301 to https

`ops/nginx/gen-cert.sh` generates a self-signed certificate into `ops/nginx/certs/`. That folder is gitignored; add `ops/nginx/certs/` to `.gitignore`.

Add to `docker-compose.yml`:
```yaml
  api:
    image: nexus-api:${NEXUS_VERSION}
    build: { context: ., dockerfile: backend/Dockerfile }
    env_file: .env
    environment:
      BACKUP_DIR: /backups
      OUTBOX_DIR: /app/outbox
    depends_on: { db: { condition: service_healthy } }
    volumes: [backups:/backups, outbox:/app/outbox]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
      interval: 10s
      retries: 12
  web:
    image: nexus-web:${NEXUS_VERSION}
    build: { context: ., dockerfile: frontend/Dockerfile }
    ports: ["8443:443", "8080:80"]
    volumes: ["./ops/nginx/certs:/etc/nginx/certs:ro"]
    depends_on: { api: { condition: service_healthy } }
```
Also add `backups:` and `outbox:` under top-level `volumes`.

Register the DB health check in `create_app` when `check_db=True`: run `SELECT 1` through the ORM with `session.execute(select(1))`, and read the current Alembic revision with `MigrationContext.configure(conn).get_current_revision()` into `app.state.alembic_rev`.

- [ ] **Step 3: Build pipeline**

`.github/workflows/ci.yml`. Jobs:
- **backend:** service `postgres:16.4-alpine` with the init script; then `pip install -r requirements-dev.txt`, `ruff check .`, `ruff format --check .`, `mypy app`, `bandit -q -r app -x app/db/migrations`, `pip-audit -r requirements.txt`, `pytest -q --cov=app --junitxml=reports/junit.xml`.
- **frontend:** `npm ci`, `npx tsc --noEmit`, `npx vitest run`, `npm audit --audit-level=high`, `npm run build`.

The repository is local, so add `ops/ci-local.sh` and `ops/ci-local.ps1`, which run the same commands in order. Those scripts are what produce the Stage 3 evidence.

- [ ] **Step 4: Run the full local pipeline**

Run:
```bash
docker compose build
docker compose up -d
bash ops/ci-local.sh
```
Expected:
- containers `healthy`
- `https://localhost:8443` serves the login page
- every pipeline step exits 0

Fix any ruff/mypy/bandit findings before continuing.

- [ ] **Step 5: Evidence and gate**

- Write `docs/06-testing/baseline-test-report.md`: date, commit hash, the command list, pass counts, coverage %, and bandit/pip-audit/npm-audit summaries (paste the tool summaries).
- Update the RTM: NFR 01 (grants + test IDs), NFR 02 (auth tests) and NFR 06 → **In progress**, with test IDs filled.
- Add a "Build and run" section to `README.md` covering `.env` setup, `docker compose up -d`, the seed command and the URL.
- Write `stage-gates/stage-3.md`. Map each SOP Stage 3 bullet to its evidence:
  - project structure
  - configuration
  - authentication
  - role management
  - audit logging
  - health checks
  - database migrations
  - test framework
  - synthetic seed data
  - repeatable local build
  - static checks
  - baseline tests
- Update the progress log and issue tracker (NX-020 Done).

- [ ] **Step 6: Commit, merge, tag, and checkpoint for Day 1**

```bash
git add -A
git commit -m "build: containers, TLS proxy, local CI pipeline and stage 3 evidence"
git checkout main
git merge --no-ff stage/3-foundation -m "Merge stage/3-foundation: SOP stage 3 foundation build"
git tag -a sop-stage-3 -m "SOP stage 3 (foundation build) approved"
git tag -a day1-checkpoint -m "End of day 1"
git checkout -b stage/4-core
```
Update the progress log "Next task" line to **Task 7**.

---

# SOP Stage 4: Core library functions (branch `stage/4-core`)

Router pattern for every task in Stages 4–5. Show it once here and apply it everywhere:
```python
router = APIRouter(prefix="/circulation", tags=["circulation"])

@router.post("/checkout", response_model=LoanOut, status_code=201)
def checkout(body: CheckoutIn, request: Request, session: Session = Depends(get_session),
             p: Principal = Depends(require("circulation.checkout"))) -> LoanOut:
    loan = CirculationService(session).checkout(
        member_card_no=body.member_card_no, item_ref=body.item, channel=LoanChannel.ui,
        actor=Actor.from_principal(p, request))
    session.commit()
    return LoanOut.model_validate(loan, from_attributes=True)
```
`Actor` lives in `app/services/common.py`:
```python
@dataclass(frozen=True)
class Actor:
    type: str                 # staff | member | device | external | system
    id: uuid.UUID | None
    ip: str | None = None
    channel: str = "ui"
    @staticmethod
    def from_principal(p: Principal, request: Request) -> "Actor":
        return Actor("staff" if p.typ == "staff" else "member", p.id,
                     request.client.host if request.client else None)
```
Services take `Actor`, write audit rows, and never commit; routers commit. Every test module for Stages 4–5 uses the `client` fixture from `test_auth.py`, moved into `conftest.py` in Task 7 Step 1. The `auth_headers(client, session, role) -> dict` helper creates a user of that role, logs in, and returns the header.

### Task 7: Catalogue, items, OPAC search, virtual bookshelf and spine labels

**Files:**
- Create: `backend/app/services/catalog.py`, `backend/app/services/search.py`, `backend/app/api/v1/{catalog,opac}.py`, `backend/app/services/labels.py`
- Modify: `backend/tests/conftest.py` (move `client`, add `auth_headers`)
- Test: `backend/tests/integration/test_catalog.py`, `backend/tests/integration/test_opac.py`

**Interfaces:**
- Produces:
  - `CatalogService(session)`:
    - `.create_bib(data: BibIn, actor) -> Bib`
    - `.add_item(bib_id, data: ItemIn, actor) -> Item`
    - `.get_item_by_ref(ref: str) -> Item` (ref = accession_no, barcode or active EPC; raises `ITEM_NOT_FOUND`)
    - `.validate_item(item_id) -> list[str]` (problems: `ITEM_WITHDRAWN`, `TITLE_MISSING`, `ACCESSION_FORMAT`, `NO_SHELF`)
    - `.update_bib(...)`
  - `SearchService(session).search(q: str, filters: OpacFilters, page: int, size: int) -> Page[BibHit]`, using `websearch_to_tsquery('simple', q)` through `func.websearch_to_tsquery` and ranking by `func.ts_rank`.
  - `virtual_shelf(shelf_code) -> list[ShelfSpine]`: items ordered by call number with title/author/status.
  - `spine_label_pdf(item) -> bytes`: reportlab, 1.5×1 inch label with call number and accession number.
  - Shared helper `isbn_is_valid(s: str) -> bool` in `app/services/validation.py`. It handles ISBN-10 (with X) and ISBN-13; the migration reuses it.

- [ ] **Step 1: Failing tests**

`backend/tests/integration/test_catalog.py`:
```python
import pytest

pytestmark = pytest.mark.db

def test_fr01_create_bib_and_item_then_find_by_accession(client, db_session, auth_headers):
    h = auth_headers("Librarian")
    bib = client.post("/api/v1/bibs", headers=h, json={"title": "Practical RFID", "author": "K. Finkenzeller",
                                                      "isbn": "9780470695067", "pub_year": 2010}).json()
    item = client.post(f"/api/v1/bibs/{bib['id']}/items", headers=h, json={
        "accession_no": "ACC-900001", "barcode": "BC90000001", "call_no": "621.38 FIN",
        "shelf_code": "A-01", "item_type": "lending"})
    assert item.status_code == 201
    found = client.get("/api/v1/items", headers=h, params={"accession_no": "ACC-900001"}).json()
    assert found[0]["bib"]["title"] == "Practical RFID"

def test_fr01_duplicate_accession_rejected(client, auth_headers, sample_item):
    h = auth_headers("Librarian")
    r = client.post(f"/api/v1/bibs/{sample_item.bib_id}/items", headers=h, json={
        "accession_no": sample_item.accession_no, "barcode": "BC-NEW", "item_type": "lending"})
    assert r.status_code == 409 and r.json()["code"] == "ACCESSION_EXISTS"

def test_fr01_invalid_isbn_rejected(client, auth_headers):
    r = client.post("/api/v1/bibs", headers=auth_headers("Librarian"), json={"title": "X", "isbn": "9780470695060"})
    assert r.status_code == 422 and r.json()["code"] == "ISBN_INVALID"

def test_nfr02_clerk_cannot_catalogue(client, auth_headers):
    r = client.post("/api/v1/bibs", headers=auth_headers("CirculationClerk"), json={"title": "X"})
    assert r.status_code == 403

def test_fr01_catalogue_write_is_audited(client, db_session, auth_headers):
    from sqlalchemy import select
    from app.db.models import AuditLog
    client.post("/api/v1/bibs", headers=auth_headers("Librarian"), json={"title": "Audited"})
    assert db_session.scalars(select(AuditLog).where(AuditLog.action == "bib.create")).first() is not None
```
`backend/tests/integration/test_opac.py`:
```python
import pytest

pytestmark = pytest.mark.db

def test_fr02_full_text_search_ranks_title_over_subject(client, make_bib):
    make_bib(title="Library Automation", subjects="cataloguing")
    make_bib(title="Cataloguing Rules", subjects="library automation")
    hits = client.get("/api/v1/opac/search", params={"q": "library automation"}).json()["items"]
    assert hits[0]["title"] == "Library Automation"

def test_fr02_new_record_searchable_immediately(client, auth_headers):
    client.post("/api/v1/bibs", headers=auth_headers("Librarian"), json={"title": "Quantum Shelving"})
    assert client.get("/api/v1/opac/search", params={"q": "quantum"}).json()["total"] == 1

def test_fr02_opac_hides_pii_and_is_public(client, make_bib):
    make_bib(title="Open Data")
    r = client.get("/api/v1/opac/search", params={"q": "open"})
    assert r.status_code == 200 and "email" not in r.text

def test_fr02_virtual_shelf_ordered_by_call_number(client, sample_shelf_items):
    spines = client.get("/api/v1/opac/shelves/A-01").json()
    assert [s["call_no"] for s in spines] == sorted(s["call_no"] for s in spines)

def test_fr02_malicious_query_is_safe(client):
    r = client.get("/api/v1/opac/search", params={"q": "'); DROP TABLE nexus.bib; --"})
    assert r.status_code == 200
```
New fixtures in `conftest.py`:
- `make_bib(**kw) -> Bib` (`source="nexus"`)
- `sample_item -> Item` (lending, available, shelf `A-01`, a shelf row created if missing)
- `sample_shelf_items` (5 items on `A-01` with shuffled call numbers)

- [ ] **Step 2: Run and confirm failure.** Run: `.venv/Scripts/pytest tests/integration/test_catalog.py tests/integration/test_opac.py -q`. Expected: 404/ImportError failures.

- [ ] **Step 3: Implement**

Implement the services and routers as specified above:
- `BibIn` validator raises `AppError("ISBN_INVALID", "ISBN checksum invalid", 422)`.
- Catch `IntegrityError` on `uq item.accession_no` and raise `AppError("ACCESSION_EXISTS", ..., 409)`, and similarly `BARCODE_EXISTS`.
- Audit actions: `bib.create`, `bib.update`, `item.create`.
- `GET /items/{id}/spine-label.pdf` returns `application/pdf`.

- [ ] **Step 4: Run and confirm green.** Run: `.venv/Scripts/pytest tests -q -m "not acceptance"`. Expected: all pass.

- [ ] **Step 4b: Scope notes recorded in the RTM.** FR 01 acquisition is captured as `price` and `acquired_on` on items, through the cataloguing form and the migration; acquisition workflow (orders, vendors, budgets) → Partial/Backlog. Serials → Backlog. FR 02 net cataloguing is provided by the migration importer (Task 22) accepting bibliographic spreadsheets from other libraries → Partial.

- [ ] **Step 5: Commit.** `git commit -am "feat: cataloguing, full-text OPAC search, virtual bookshelf and spine labels (FR 01, FR 02)"`

---

### Task 8: Members, circulation policy engine, circulation and fines

**Files:**
- Create: `backend/app/services/{common,members,policy,circulation,fines}.py`, `backend/app/api/v1/{members,circulation,fines}.py`, `backend/app/services/cards.py`
- Test: `backend/tests/unit/test_policy.py`, `backend/tests/integration/test_circulation.py`, `backend/tests/acceptance/test_ac04_circulation_blocks.py`

**Interfaces:**
- Produces:
  - `PolicyEngine.evaluate_checkout(member: Member, item: Item, policy: CircPolicy, open_fines: Decimal, open_loans: int) -> str | None`. Returns a refusal code or `None`. This is a pure function, so it can be unit tested.
  - `CirculationService(session)`:
    - `.checkout(*, member_card_no: str, item_ref: str, channel: LoanChannel, actor: Actor) -> Loan`
    - `.renew(*, item_ref: str | None = None, loan_id: uuid.UUID | None = None, actor: Actor, channel) -> Loan`
    - `.checkin(*, item_ref: str, actor: Actor, channel) -> CheckinResult(loan, fine: Fine | None)`
    - `.due(item_ref) -> DueInfo`
  - Refusal raises `CirculationRefused(code)`, a subclass of `AppError` with status 409.
  - `MembersService(session)`: `.create`, `.update`, `.block(member_id, reason, actor)`, `.unblock`, `.get_by_card(card_no)`, `.loans(member_id)`, `.fines(member_id)`.
  - `FinesService(session)`: `.raise_overdue(loan, now)`, `.pay(fine_id, actor)`, `.waive(fine_id, reason, actor)`, `.open_total(member_id) -> Decimal`.
  - `patron_card_pdf(member) -> bytes` (name, card number, Code128 barcode via reportlab).
  - Circulation side effects:
    - Check-out sets item `on_loan` and the active tag's `security_bit=False`.
    - Check-in sets item `available` and `security_bit=True`.
    - Audit actions: `circulation.checkout|renew|checkin|refused`, with `{channel, item, member, code}`.

Rule order in `evaluate_checkout` (first match wins). This ordering is part of the contract and is tested.

| # | Condition | Refusal code |
|---|---|---|
| 1 | `member.status == blocked` | `MEMBER_BLOCKED` |
| 2 | `member.status == expired` | `MEMBER_EXPIRED` |
| 3 | `item.status != available` | `ITEM_NOT_AVAILABLE` |
| 4 | `item.item_type == reference and not policy.can_borrow_reference` | `ITEM_REFERENCE_ONLY` |
| 5 | `open_fines > policy.fine_limit` | `FINE_LIMIT_EXCEEDED` |
| 6 | `open_loans >= policy.max_items` | `MAX_ITEMS_REACHED` |

Concurrency: `checkout` loads the item with `select(...).with_for_update()`. The partial unique index `uq_loan_open_item` is the final guard; an `IntegrityError` maps to `ITEM_NOT_AVAILABLE`.

- [ ] **Step 1: Failing tests**

`backend/tests/unit/test_policy.py`:
```python
from decimal import Decimal
from types import SimpleNamespace as NS
import pytest
from app.services.policy import PolicyEngine

POL = NS(can_borrow_reference=False, fine_limit=Decimal("100"), max_items=4)

def m(status="active"): return NS(status=status)
def i(status="available", t="lending"): return NS(status=status, item_type=t)

@pytest.mark.parametrize("member,item,fines,loans,expected", [
    (m(), i(), Decimal(0), 0, None),
    (m("blocked"), i(t="reference"), Decimal(500), 9, "MEMBER_BLOCKED"),
    (m(), i(t="reference"), Decimal(0), 0, "ITEM_REFERENCE_ONLY"),
    (m(), i(), Decimal("100.01"), 0, "FINE_LIMIT_EXCEEDED"),
    (m(), i(), Decimal("100.00"), 0, None),
    (m(), i(), Decimal(0), 4, "MAX_ITEMS_REACHED"),
    (m(), i("on_loan"), Decimal(0), 0, "ITEM_NOT_AVAILABLE"),
])
def test_ac04_policy_rules(member, item, fines, loans, expected):
    assert PolicyEngine.evaluate_checkout(member, item, POL, fines, loans) == expected
```
`backend/tests/integration/test_circulation.py`:
```python
import threading
import pytest
from sqlalchemy import func, select
from app.db.models import AuditLog, Loan, RfidTag

pytestmark = pytest.mark.db

def test_fr04_checkout_renew_checkin_cycle(client, auth_headers, sample_member, tagged_item):
    h = auth_headers("CirculationClerk")
    out = client.post("/api/v1/circulation/checkout", headers=h,
                      json={"member_card_no": sample_member.card_no, "item": tagged_item.accession_no})
    assert out.status_code == 201
    due1 = out.json()["due_at"]
    ren = client.post("/api/v1/circulation/renew", headers=h, json={"item": tagged_item.accession_no})
    assert ren.json()["due_at"] > due1 and ren.json()["renew_count"] == 1
    back = client.post("/api/v1/circulation/checkin", headers=h, json={"item": tagged_item.accession_no})
    assert back.status_code == 200 and back.json()["loan"]["returned_at"] is not None

def test_fr04_security_bit_follows_loan_state(client, db_session, auth_headers, sample_member, tagged_item):
    h = auth_headers("CirculationClerk")
    client.post("/api/v1/circulation/checkout", headers=h,
                json={"member_card_no": sample_member.card_no, "item": tagged_item.accession_no})
    tag = db_session.scalars(select(RfidTag).where(RfidTag.item_id == tagged_item.id)).one()
    db_session.refresh(tag); assert tag.security_bit is False
    client.post("/api/v1/circulation/checkin", headers=h, json={"item": tagged_item.accession_no})
    db_session.refresh(tag); assert tag.security_bit is True

def test_fr04_max_renewals(client, auth_headers, sample_member, tagged_item):
    h = auth_headers("CirculationClerk")
    client.post("/api/v1/circulation/checkout", headers=h,
                json={"member_card_no": sample_member.card_no, "item": tagged_item.accession_no})
    codes = [client.post("/api/v1/circulation/renew", headers=h, json={"item": tagged_item.accession_no})
             .status_code for _ in range(3)]
    assert codes == [200, 200, 409]

def test_fr04_overdue_checkin_raises_fine(client, db_session, auth_headers, overdue_loan):
    r = client.post("/api/v1/circulation/checkin", headers=auth_headers("CirculationClerk"),
                    json={"item": overdue_loan.item.accession_no})
    assert r.json()["fine"]["amount"] == "10.00"   # 5 days x 2.00 (UG)

def test_fr04_due_date_enquiry(client, auth_headers, active_loan):
    r = client.get("/api/v1/circulation/due", headers=auth_headers("CirculationClerk"),
                   params={"item": active_loan.item.accession_no})
    assert r.json()["due_at"] == active_loan.due_at.isoformat()

def test_nfr02_patron_cannot_read_other_patron_loans(client, patron_headers, other_member):
    r = client.get(f"/api/v1/members/{other_member.id}/loans", headers=patron_headers)
    assert r.status_code == 403

def test_fr04_concurrent_checkout_single_loan(committed_world):
    """Two real connections race to issue the same item; exactly one loan results."""
    results = committed_world.race_checkout(threads=2)
    assert sorted(results) == [201, 409]
    assert committed_world.count_open_loans() == 1
```
> `committed_world` is a fixture in `conftest.py` that commits a member pair and a tagged item through a separate owner-free app session, runs two `TestClient` requests in threads with real sessions (no override), and cleans up afterwards by deleting what it created. Implement it in this task.

`backend/tests/acceptance/test_ac04_circulation_blocks.py`:
```python
import pytest
from decimal import Decimal

pytestmark = [pytest.mark.db, pytest.mark.acceptance]

def _checkout(client, h, member, item):
    return client.post("/api/v1/circulation/checkout", headers=h,
                       json={"member_card_no": member.card_no, "item": item.accession_no})

def test_ac04_reference_item_blocked(client, auth_headers, sample_member, reference_item):
    r = _checkout(client, auth_headers("CirculationClerk"), sample_member, reference_item)
    assert r.status_code == 409 and r.json()["code"] == "ITEM_REFERENCE_ONLY"

def test_ac04_blocked_member_refused(client, auth_headers, blocked_member, tagged_item):
    r = _checkout(client, auth_headers("CirculationClerk"), blocked_member, tagged_item)
    assert r.json()["code"] == "MEMBER_BLOCKED"

def test_ac04_fine_limit_configurable(client, auth_headers, member_with_fines, tagged_item):
    member_with_fines.set_open_fines(Decimal("120.00"))      # UG limit 100
    clerk, admin = auth_headers("CirculationClerk"), auth_headers("Admin")
    assert _checkout(client, clerk, member_with_fines.member, tagged_item).json()["code"] == "FINE_LIMIT_EXCEEDED"
    client.patch("/api/v1/admin/policies/UG", headers=admin, json={"fine_limit": "150.00"})
    assert _checkout(client, clerk, member_with_fines.member, tagged_item).status_code == 201

def test_ac04_refusals_are_audited(client, db_session, auth_headers, blocked_member, tagged_item):
    from sqlalchemy import select
    from app.db.models import AuditLog
    _checkout(client, auth_headers("CirculationClerk"), blocked_member, tagged_item)
    row = db_session.scalars(select(AuditLog).where(AuditLog.action == "circulation.refused")).one()
    assert row.details["code"] == "MEMBER_BLOCKED"
```
Add fixtures:
- `sample_member` (UG, active)
- `blocked_member`
- `other_member`
- `patron_headers` (logged-in patron = `sample_member`)
- `tagged_item` (lending, active tag with `security_bit=True`)
- `reference_item`
- `active_loan`
- `overdue_loan` (due 5 days ago)
- `member_with_fines` (helper object with `.member` and `.set_open_fines(amount)`)

Add the `PATCH /admin/policies/{category}` endpoint here (permission `admin.policies.write`, audited `policy.update`). It is needed by AC 04.

- [ ] **Step 2: Run and confirm failure.** Run: `.venv/Scripts/pytest tests/unit/test_policy.py tests/integration/test_circulation.py tests/acceptance/test_ac04_circulation_blocks.py -q`. Expected: ImportError/404.

- [ ] **Step 3: Implement** the services, routers and admin policy endpoint per the interfaces above.
  - Fine on check-in = `max(0, days_late) * policy.fine_per_day`, where days are whole days late using `ceil((returned_at - due_at) / 1 day)`.
  - Renew: refused with `MAX_RENEWALS_REACHED` at `renew_count >= max_renewals`, and with `MEMBER_BLOCKED`/`FINE_LIMIT_EXCEEDED` per the same engine. New `due_at = max(now, due_at) + loan_days`.
  - Member block/unblock audited as `member.block` and `member.unblock`.

- [ ] **Step 4: Run and confirm green.** Run: `.venv/Scripts/pytest tests -q`. Expected: all pass.

- [ ] **Step 5: Commit.** `git commit -am "feat: members, policy engine, circulation with security-bit handling and fines (FR 04, AC 04)"`

---

### Task 9: Dashboard and reports

**Files:**
- Create: `backend/app/services/reports.py`, `backend/app/services/export.py`, `backend/app/api/v1/reports.py`
- Test: `backend/tests/acceptance/test_ac08_reports.py`

**Interfaces:**
- Produces:
  - `ReportsService(session).dashboard() -> Dashboard` with fields: `tagged_items`, `untagged_items`, `members_active`, `members_blocked`, `loans_active`, `loans_overdue`, `fines_open_total`, `gate_alarms_today`, `footfall_today`, `loans_by_day: list[{date, count}]` (30 days), and `top_titles: list[{title, loans}]`.
  - `ReportsService.run(report: ReportName, filters: ReportFilters) -> ReportTable(columns: list[str], rows: list[list])`. `ReportName` is a `StrEnum` covering the seven report names in interface design §1.
  - `to_csv(table) -> bytes` and `to_pdf(table, title) -> bytes` (reportlab `SimpleDocTemplate` + `Table`, landscape A4).
  - PII columns are masked when the principal lacks `member.pii.read`.

Filters per report (in addition to `from`/`to`):

| Report | Extra filters |
|---|---|
| tagged-items | `shelf_code`, `tag_status` |
| members | `category`, `status` |
| circulation | `channel`, `operator_id`, `member_category` |
| operators | `operator_id` |
| rfid-clients | `device_code`, `device_type` |
| fines | `status` |
| gate-events | `alarm`, `device_code` |

- [ ] **Step 1: Failing test**

`backend/tests/acceptance/test_ac08_reports.py`:
```python
import pytest

pytestmark = [pytest.mark.db, pytest.mark.acceptance]
REPORTS = ["tagged-items", "members", "circulation", "operators", "rfid-clients", "fines", "gate-events"]

def test_ac08_dashboard_tiles(client, auth_headers, activity_world):
    d = client.get("/api/v1/reports/dashboard", headers=auth_headers("Librarian")).json()
    assert d["tagged_items"] == activity_world.tagged
    assert d["loans_active"] == activity_world.active_loans
    assert d["gate_alarms_today"] == activity_world.alarms_today
    assert len(d["loans_by_day"]) == 30

@pytest.mark.parametrize("name", REPORTS)
def test_ac08_each_report_json_csv_pdf(client, auth_headers, activity_world, name):
    h = auth_headers("Auditor")
    j = client.get(f"/api/v1/reports/{name}", headers=h, params={"format": "json"})
    assert j.status_code == 200 and j.json()["columns"]
    c = client.get(f"/api/v1/reports/{name}", headers=h, params={"format": "csv"})
    assert c.headers["content-type"].startswith("text/csv") and c.text.count("\n") >= 1
    p = client.get(f"/api/v1/reports/{name}", headers=h, params={"format": "pdf"})
    assert p.content[:4] == b"%PDF"

def test_ac08_filters_apply(client, auth_headers, activity_world):
    h = auth_headers("Librarian")
    all_rows = client.get("/api/v1/reports/circulation", headers=h).json()["rows"]
    ncip_rows = client.get("/api/v1/reports/circulation", headers=h, params={"channel": "ncip"}).json()["rows"]
    assert 0 < len(ncip_rows) < len(all_rows)

def test_ac08_auditor_sees_masked_member_pii(client, auth_headers, activity_world):
    t = client.get("/api/v1/reports/members", headers=auth_headers("Auditor")).json()
    email_col = t["columns"].index("email")
    assert all(r[email_col] in ("***", None) for r in t["rows"])

def test_nfr02_clerk_cannot_read_reports(client, auth_headers):
    assert client.get("/api/v1/reports/dashboard", headers=auth_headers("CirculationClerk")).status_code == 403
```
`activity_world` fixture: 10 tagged and 5 untagged items, 6 loans (2 overdue, 2 via `ncip`), 3 fines, 4 gate events (2 alarms today), and 2 devices. It exposes the expected counts as attributes.

- [ ] **Step 2: Run, confirm failure → Step 3: Implement → Step 4: Run, confirm green.** (Same commands as Task 8.)

- [ ] **Step 5: Commit.** `git commit -am "feat: dashboard statistics and filterable reports with CSV/PDF export (FR 08, AC 08)"`

---

### Task 10: Core UI screens

**Files:**
- Create in `frontend/src/pages/`: `OpacPage.tsx`, `ShelfPage.tsx`, `MyLoansPage.tsx`, `CataloguePage.tsx`, `ItemPage.tsx`, `CirculationDeskPage.tsx`, `MembersPage.tsx`, `DashboardPage.tsx`, `ReportsPage.tsx`, `AdminUsersPage.tsx`, `AdminPoliciesPage.tsx`, `AuditPage.tsx`, `HealthPage.tsx`
- Create: `frontend/src/components/{RefusalBanner,DataTable,StatTile,ExportButtons}.tsx`, `frontend/src/api/endpoints.ts`
- Create: `backend/app/api/v1/admin.py` (users list/create/update/deactivate, roles list, settings get/patch, audit query, devices list), plus `backend/tests/integration/test_admin.py`
- Test: `frontend/src/components/RefusalBanner.test.tsx`

**Interfaces:**
- Consumes: the API endpoints from Tasks 3, 7, 8 and 9.
- Produces:
  - `RefusalBanner({code})` maps every refusal code to a human message. Example: `FINE_LIMIT_EXCEEDED` → "Outstanding fines exceed this member's limit".
  - The admin API endpoints in interface design §1.

- [ ] **Step 1: Failing tests**

`frontend/src/components/RefusalBanner.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { RefusalBanner, REFUSAL_TEXT } from "./RefusalBanner";
import { it, expect } from "vitest";

it("has text for every circulation refusal code", () => {
  for (const code of ["ITEM_REFERENCE_ONLY","MEMBER_BLOCKED","MEMBER_EXPIRED","FINE_LIMIT_EXCEEDED",
    "MAX_ITEMS_REACHED","MAX_RENEWALS_REACHED","ITEM_NOT_AVAILABLE","ITEM_NOT_ON_LOAN","ROLE_NOT_PERMITTED"])
    expect(REFUSAL_TEXT[code]).toBeTruthy();
});
it("renders message", () => {
  render(<RefusalBanner code="MEMBER_BLOCKED" />);
  expect(screen.getByRole("alert").textContent).toContain("blocked");
});
```
(Install `@testing-library/react@16.0.1` as a pinned dev dependency.)

`backend/tests/integration/test_admin.py`:
```python
import pytest

pytestmark = pytest.mark.db

def test_fr11_admin_creates_user_and_it_is_audited(client, db_session, auth_headers):
    h = auth_headers("Admin")
    r = client.post("/api/v1/admin/users", headers=h, json={"username": "newclerk", "display_name": "New Clerk",
                    "role": "CirculationClerk", "password": "Str0ng-Passw0rd"})
    assert r.status_code == 201 and "password" not in r.text
    audit = client.get("/api/v1/admin/audit", headers=h, params={"action": "user.create"}).json()
    assert audit["items"][0]["entity_id"] == r.json()["id"]

def test_fr11_weak_password_rejected(client, auth_headers):
    r = client.post("/api/v1/admin/users", headers=auth_headers("Admin"), json={
        "username": "weak", "display_name": "W", "role": "Auditor", "password": "short"})
    assert r.status_code == 422

def test_fr11_auditor_reads_audit_but_cannot_create_users(client, auth_headers):
    h = auth_headers("Auditor")
    assert client.get("/api/v1/admin/audit", headers=h).status_code == 200
    assert client.post("/api/v1/admin/users", headers=h, json={}).status_code == 403
```
Password policy: at least 12 characters, with at least one letter and one digit.

- [ ] **Step 2: Run, confirm failure → Step 3: Implement.**
  - Each page uses TanStack Query with the `api()` client.
  - The circulation desk has member card and item inputs (barcode, accession or EPC). It shows the member summary (status, open fines vs limit, current loans), check-out / renew / check-in buttons, and a `RefusalBanner` on 409.
  - The dashboard uses `StatTile`s plus a Recharts line chart (`loans_by_day`) and a bar chart (`top_titles`).
  - Reports has a report picker, a filter form generated from the filter table in Task 9, a `DataTable`, and `ExportButtons` that download CSV/PDF through `fetch` with the auth header, then a blob URL.

- [ ] **Step 4: Verify.**
  Run: `npx vitest run && npm run build && .venv/Scripts/pytest tests -q`
  Expected: all green.
  Manual journey, noted in `docs/06-testing/user-journeys.md`:
  1. Librarian catalogues a book.
  2. The book is searchable in the OPAC.
  3. A clerk issues and returns it.
  4. A blocked member is refused.
  5. The dashboard updates.
  Take screenshots into `docs/06-testing/evidence/stage4/`.

- [ ] **Step 5: Commit.** `git commit -am "feat: OPAC, catalogue, circulation desk, members, dashboard, reports and admin screens"`

### Task 11: Stage 4 gate

- [ ] Update the RTM (FR 01, 02, 04, 08, 11 → Done/Partial, with test IDs).
- [ ] Export the API docs: `curl -k https://localhost:8443/api/openapi.json > docs/08-operations/openapi.json`.
- [ ] Log any defects found in the manual journey in `defect-log.md` and fix the S1/S2 ones.
- [ ] Write `stage-gates/stage-4.md`, mapping each SOP Stage 4 bullet to its evidence.
- [ ] Update the progress log.
- [ ] Merge `--no-ff`, tag `sop-stage-4`, and branch `stage/5-rfid`.

---

# SOP Stage 5: RFID middleware and integrations (branch `stage/5-rfid`)

### Task 12: Device registry, event ingest, dispatcher, command bus and live hub

**Files:**
- Create: `backend/app/middleware_rfid/{__init__,schemas,ingest,dispatcher,commands,live_hub,device_auth}.py`, `backend/app/api/v1/{devices,ws}.py`
- Test: `backend/tests/integration/test_device_ingest.py`, `backend/tests/unit/test_commands.py`

**Interfaces:**
- Produces:
  - `DeviceEventIn` (Pydantic, `extra="forbid"`): `event_id: UUID`, `device_type: DeviceType`, `type: Literal["Heartbeat","TagsRead","GatePassage","CardTapped","Footfall"]`, `occurred_at: datetime`, `epcs: list[constr(pattern=r"^[0-9A-F]{8,32}$")] = []` (max 500), `payload: dict = {}`.
  - `authenticate_device(code, key, session) -> Device`. Uses `hmac.compare_digest` on the SHA-256 of the key; raises `ERR_DEVICE_AUTH` 401.
  - `ingest(session, device, event) -> Literal["accepted","duplicate"]`:
    1. Insert `DeviceEvent`.
    2. On a unique violation of `event_id`, return `"duplicate"` (nested SAVEPOINT).
    3. Otherwise call `dispatcher.dispatch(session, device, event)`.
    4. Set `processed_at` and `result`.
    5. Update `device.last_heartbeat_at` on every event.
  - `Dispatcher.register(event_type, handler: Callable[[Session, Device, DeviceEventIn], dict])`. Handlers are registered in Tasks 13–16.
  - `CommandBus`:
    - `send(device_code, command: str, params: dict, timeout_s=3.0, attempts=3) -> CommandResult(ok, response, attempts)`. Delivers through an in-process `asyncio.Queue` per device that the device WebSocket drains. Waits for an ack keyed by `command_id`. Retries with backoff 0.2 s · 2^n.
    - `poll(device_code) -> list[Command]` for devices without a socket.
  - `LiveHub.publish(topic: str, data: dict)`, and `/ws/live?token=` for authenticated UI clients (the token is validated with `decode_access_token`). Topics: `gate.alert`, `inventory.read`, `device.status`, `auth.card`.
  - Endpoint `POST /devices/{code}/events` (rate-limited `rate_limit_devices`; returns 202 or 200 duplicate).
  - Endpoint `WS /devices/{code}/ws` (header `X-Device-Key`).

- [ ] **Step 1: Failing tests**

`backend/tests/integration/test_device_ingest.py`:
```python
import uuid
from datetime import UTC, datetime
import pytest
from sqlalchemy import func, select
from app.db.models import DeviceEvent

pytestmark = pytest.mark.db

def ev(t="Heartbeat", **kw):
    return {"event_id": str(uuid.uuid4()), "device_type": kw.pop("device_type", "handheld"), "type": t,
            "occurred_at": datetime.now(UTC).isoformat(), "epcs": kw.pop("epcs", []), "payload": kw}

def test_fr03_event_requires_device_key(client, device_hh):
    r = client.post(f"/api/v1/devices/{device_hh.code}/events", json=ev(), headers={"X-Device-Key": "wrong"})
    assert r.status_code == 401 and r.json()["code"] == "ERR_DEVICE_AUTH"

def test_fr03_duplicate_event_ignored(client, db_session, device_hh):
    e = ev()
    h = {"X-Device-Key": device_hh.raw_key}
    assert client.post(f"/api/v1/devices/{device_hh.code}/events", json=e, headers=h).status_code == 202
    second = client.post(f"/api/v1/devices/{device_hh.code}/events", json=e, headers=h)
    assert second.status_code == 200 and second.json()["status"] == "duplicate"
    assert db_session.scalar(select(func.count()).select_from(DeviceEvent)
                             .where(DeviceEvent.event_id == uuid.UUID(e["event_id"]))) == 1

def test_fr03_heartbeat_marks_device_online(client, auth_headers, device_hh):
    client.post(f"/api/v1/devices/{device_hh.code}/events", json=ev(), headers={"X-Device-Key": device_hh.raw_key})
    devs = client.get("/api/v1/devices", headers=auth_headers("Librarian")).json()
    assert next(d for d in devs if d["code"] == device_hh.code)["status"] == "online"

def test_fr03_malformed_epc_rejected(client, device_hh):
    r = client.post(f"/api/v1/devices/{device_hh.code}/events", json=ev("TagsRead", epcs=["<bad>"]),
                    headers={"X-Device-Key": device_hh.raw_key})
    assert r.status_code == 422
```
`backend/tests/unit/test_commands.py`:
```python
import asyncio
import pytest
from app.middleware_rfid.commands import CommandBus

@pytest.mark.asyncio
async def test_fr03_command_times_out_and_retries():
    bus = CommandBus()
    res = await bus.send("HH-01", "Beep", {"pattern": "ok"}, timeout_s=0.05, attempts=3)
    assert res.ok is False and res.attempts == 3

@pytest.mark.asyncio
async def test_fr03_command_acknowledged():
    bus = CommandBus()
    async def device():
        cmd = await bus.next_for("HH-01")
        bus.ack(cmd.command_id, {"ok": True})
    asyncio.create_task(device())
    res = await bus.send("HH-01", "Beep", {"pattern": "ok"}, timeout_s=1, attempts=1)
    assert res.ok and res.response == {"ok": True}
```
(Add `pytest-asyncio==0.24.0` to `requirements-dev.txt`.)

Fixtures:
- `device_hh`, `device_gate`, `device_staff`, `device_card`: `Device` rows with generated keys, exposing `.raw_key`
- `camera` (`CAM-01`, linked from `GATE-01` config `{"camera": "CAM-01"}`)

- [ ] **Step 2: Run, confirm failure → Step 3: Implement → Step 4: Run, confirm green.**
- [ ] **Step 5: Commit.** `git commit -am "feat: RFID middleware with authenticated idempotent event ingest, command bus and live hub (FR 03)"`

---

### Task 13: Tagging workflow

**Files:**
- Create: `backend/app/services/tagging.py`, `backend/app/middleware_rfid/handlers/tags_read.py`, `backend/app/api/v1/tags.py`
- Test: `backend/tests/acceptance/test_ac02_tagging.py`

**Interfaces:**
- Produces:
  - `TaggingService(session)`:
    - `.associate(epc, target_type, target_id, actor) -> RfidTag`. Validates first: the item exists, is not withdrawn, and has a title; the member exists and is not expired. Errors: `TAG_TARGET_INVALID` (422, with problems), `TAG_IN_USE` (409, EPC active elsewhere). If the target already has an active tag, that tag is retired with `retire_reason="retagged"`. The security bit is set to `item.status != on_loan`. Audit `tag.associate`, and `tag.retire` when one is retired.
    - `.retire(epc, reason, actor)`
    - `.history(item_id) -> list[RfidTag]`
  - The `TagsRead` handler runs when there is no `session_id` in the payload (staff station mode). It publishes `tag.read {device, epcs, resolved: [{epc, item_id, title, status} | {epc, unknown: true}]}` to the live hub, so the tagging screen can pick up the blank tag the reader saw.
  - Tag monitoring: `GET /tags?status=&from=&to=` and the `tagged-items` report (Task 9).

- [ ] **Step 1: Failing test**

`backend/tests/acceptance/test_ac02_tagging.py`:
```python
import pytest

pytestmark = [pytest.mark.db, pytest.mark.acceptance]

def test_ac02_associate_tag_and_show_relationship(client, auth_headers, sample_item):
    h = auth_headers("Librarian")
    v = client.post(f"/api/v1/items/{sample_item.id}/validate", headers=h).json()
    assert v["problems"] == []
    r = client.post("/api/v1/tags", headers=h, json={"epc": "E28011606000020000000001",
                                                     "target_type": "item", "item_id": str(sample_item.id)})
    assert r.status_code == 201 and r.json()["security_bit"] is True
    item = client.get(f"/api/v1/items/{sample_item.id}", headers=h).json()
    assert item["active_tag"]["epc"] == "E28011606000020000000001"
    assert client.get("/api/v1/tags/E28011606000020000000001", headers=h).json()["item"]["accession_no"] \
        == sample_item.accession_no

def test_ac02_withdrawn_item_cannot_be_tagged(client, auth_headers, withdrawn_item):
    r = client.post("/api/v1/tags", headers=auth_headers("Librarian"), json={
        "epc": "E28011606000020000000002", "target_type": "item", "item_id": str(withdrawn_item.id)})
    assert r.status_code == 422 and "ITEM_WITHDRAWN" in r.json()["error"]

def test_ac02_retag_retires_previous(client, auth_headers, tagged_item):
    h = auth_headers("Librarian")
    old = tagged_item.active_epc
    client.post("/api/v1/tags", headers=h, json={"epc": "E28011606000020000000003", "target_type": "item",
                                                 "item_id": str(tagged_item.id)})
    hist = client.get(f"/api/v1/items/{tagged_item.id}", headers=h).json()["tag_history"]
    assert {t["epc"]: t["status"] for t in hist} == {old: "retired", "E28011606000020000000003": "active"}

def test_fr05_epc_already_active_elsewhere(client, auth_headers, tagged_item, sample_item):
    r = client.post("/api/v1/tags", headers=auth_headers("Librarian"), json={
        "epc": tagged_item.active_epc, "target_type": "item", "item_id": str(sample_item.id)})
    assert r.status_code == 409 and r.json()["code"] == "TAG_IN_USE"

def test_fr05_member_card_tag(client, auth_headers, sample_member):
    r = client.post("/api/v1/tags", headers=auth_headers("Librarian"), json={
        "epc": "E28011606000020000000009", "target_type": "member", "member_id": str(sample_member.id)})
    assert r.status_code == 201
```
- [ ] **Steps 2–4: run (fail) → implement → run (green).**
- [ ] **Step 5: Commit.** `git commit -am "feat: validated tag association, re-tagging and tag monitoring (FR 05, AC 02)"`

---

### Task 14: Handheld inventory

**Files:**
- Create: `backend/app/services/inventory.py`, `backend/app/middleware_rfid/handlers/inventory.py`, `backend/app/api/v1/inventory.py`
- Test: `backend/tests/acceptance/test_ac05_inventory.py`

**Interfaces:**
- Produces:
  - `InventoryService(session)`:
    - `.start(shelf_code, device_code, actor) -> InventorySession`
    - `.record_reads(session_id, epcs) -> list[ReadOutcome(epc, result: found|misplaced|unknown, item_id, home_shelf)]`. Repeat reads of the same EPC in a session are ignored.
    - `.close(session_id, actor) -> InventoryReport(found: list, misplaced: list, missing: list, unknown: list)`. Missing = active-tagged items whose home shelf is this one and whose status is not `on_loan`/`withdrawn`, minus those read. On close, missing items are **not** changed automatically; the Librarian confirms with `POST /inventory/sessions/{id}/mark-missing`, which sets the status to `missing`.
  - `TagsRead` handler: when `payload.session_id` is present, call `record_reads`. For each outcome, send `Beep` and `Light` to the handheld (found → `ok`/green, misplaced → `warn`/amber, unknown → `error`/red), and publish `inventory.read {session_id, outcome, beep, light}` on the live hub. The event `result` stores the outcomes, so tests can check the confirmations without a device socket.

- [ ] **Step 1: Failing test**

`backend/tests/acceptance/test_ac05_inventory.py`:
```python
import uuid
from datetime import UTC, datetime
import pytest

pytestmark = [pytest.mark.db, pytest.mark.acceptance]

def test_ac05_shelf_inventory_reports_missing_and_misplaced(client, auth_headers, device_hh, shelf_world):
    h = auth_headers("Librarian")
    sess = client.post("/api/v1/inventory/sessions", headers=h,
                       json={"shelf_code": "A-01", "device_code": device_hh.code}).json()
    present = shelf_world.a01_epcs[:-2]                  # two left off the sweep
    foreign = shelf_world.b01_epcs[0]                    # belongs on B-01
    r = client.post(f"/api/v1/devices/{device_hh.code}/events", headers={"X-Device-Key": device_hh.raw_key}, json={
        "event_id": str(uuid.uuid4()), "device_type": "handheld", "type": "TagsRead",
        "occurred_at": datetime.now(UTC).isoformat(), "epcs": present + [foreign],
        "payload": {"session_id": sess["id"], "mode": "bulk"}})
    assert r.status_code == 202
    live = client.get(f"/api/v1/inventory/sessions/{sess['id']}", headers=h).json()
    confirmations = {x["epc"]: (x["light"], x["beep"]) for x in live["reads"]}
    assert confirmations[present[0]] == ("green", "ok")
    assert confirmations[foreign] == ("amber", "warn")
    report = client.post(f"/api/v1/inventory/sessions/{sess['id']}/close", headers=h).json()
    assert sorted(m["epc"] for m in report["missing"]) == sorted(shelf_world.a01_epcs[-2:])
    assert report["misplaced"][0]["epc"] == foreign and report["misplaced"][0]["home_shelf"] == "B-01"

def test_fr06_repeat_reads_counted_once(client, auth_headers, device_hh, shelf_world):
    h = auth_headers("Librarian")
    sess = client.post("/api/v1/inventory/sessions", headers=h,
                       json={"shelf_code": "A-01", "device_code": device_hh.code}).json()
    for _ in range(2):
        client.post(f"/api/v1/devices/{device_hh.code}/events", headers={"X-Device-Key": device_hh.raw_key}, json={
            "event_id": str(uuid.uuid4()), "device_type": "handheld", "type": "TagsRead",
            "occurred_at": datetime.now(UTC).isoformat(), "epcs": shelf_world.a01_epcs[:1],
            "payload": {"session_id": sess["id"], "mode": "bulk"}})
    assert len(client.get(f"/api/v1/inventory/sessions/{sess['id']}", headers=h).json()["reads"]) == 1
```
`shelf_world` fixture: 6 tagged items on A-01 and 3 on B-01, exposing `a01_epcs` and `b01_epcs`.

- [ ] **Steps 2–4: run (fail) → implement → run (green).**
- [ ] **Step 5: Commit.** `git commit -am "feat: handheld inventory sessions with missing/misplaced detection and confirmations (FR 06, AC 05)"`

---

### Task 15: Security gate, CCTV snapshot and notification outbox

**Files:**
- Create: `backend/app/services/gate.py`, `backend/app/services/notifications.py`, `backend/app/middleware_rfid/handlers/gate.py`, `backend/app/integrations/{notify_mock,camera_mock}.py`, `backend/app/worker.py`, `backend/app/api/v1/{gate,notifications}.py`
- Modify: `backend/app/main.py` (start the outbox worker on startup when `RUN_WORKER=true`; default true)
- Test: `backend/tests/acceptance/test_ac06_gate_event.py`, `backend/tests/integration/test_outbox.py`

**Interfaces:**
- Produces:
  - `GateService(session).handle_passage(device, event) -> GateEvent`:
    1. Resolve the EPC to an active tag and item.
    2. `authorised = item is on_loan` (open loan exists). `alarm = direction == "out" and (tag.security_bit or unknown EPC)`.
    3. Record `accession_no`, `offline_decision` from the payload, and `occurred_at` from the event.
    4. On alarm: `CameraProvider.snapshot(device.config["camera"], {...})` → `photo_jpeg`.
    5. `NotificationsService.queue(channel="email", template="gate_alert", recipients=app_setting["gate_alert_recipients"], related=("gate_event", id))`.
    6. Publish `gate.alert`.
    7. Audit `gate.alarm`.
  - Duplicates: a replayed event with the same `event_id` is already stopped by ingest (Task 12).
  - `Footfall` events: upsert the hourly counts.
  - `NotificationsService(session)`:
    - `.queue(channel, template, recipients, context, related) -> list[NotificationOutbox]`
    - `.queue_for_member(member, template, context)`: respects `notify_email/sms/print`
  - `worker.run_once(session, now) -> int` (number sent): picks `queued` rows with `attempts < 5` and `next_attempt_at <= now`, sends via `get_adapter(channel)`, and on failure sets `attempts += 1`, `next_attempt_at = now + 2^attempts s`, `status = failed` when attempts reach 5. (Add the column `next_attempt_at` to `notification_outbox` in migration `0003_outbox_retry.py`.)
  - `MockEmail/MockSms/MockPrint.send` write `outbox/<channel>/<id>.eml|txt|pdf`. `MockEmail` fails the first N sends when `MOCK_EMAIL_FAIL_FIRST=N`.
  - `MockCamera.snapshot` uses Pillow to draw a 640×360 JPEG with the camera code, timestamp and accession number.
  - Templates (`gate_alert`, `overdue_notice`, `due_reminder`) are Python format strings in `services/notification_templates.py`. Circulation queues `overdue_notice` on an overdue check-in for members who opted in.

- [ ] **Step 1: Failing tests**

`backend/tests/acceptance/test_ac06_gate_event.py`:
```python
import uuid
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy import select
from app.db.models import GateEvent, NotificationOutbox

pytestmark = [pytest.mark.db, pytest.mark.acceptance]

def gate_ev(epc, offline=False, when=None, event_id=None):
    return {"event_id": event_id or str(uuid.uuid4()), "device_type": "gate", "type": "GatePassage",
            "occurred_at": (when or datetime.now(UTC)).isoformat(), "epcs": [epc],
            "payload": {"direction": "out", "security_bit": True, "offline_decision": offline}}

def test_ac06_unissued_item_triggers_alarm_photo_and_email(client, db_session, auth_headers, device_gate,
                                                           camera, tagged_item):
    r = client.post(f"/api/v1/devices/{device_gate.code}/events", headers={"X-Device-Key": device_gate.raw_key},
                    json=gate_ev(tagged_item.active_epc))
    assert r.status_code == 202
    ge = db_session.scalars(select(GateEvent)).one()
    assert ge.alarm and not ge.authorised and ge.accession_no == tagged_item.accession_no
    assert ge.photo_jpeg[:2] == b"\xff\xd8"
    out = db_session.scalars(select(NotificationOutbox).where(NotificationOutbox.related_id == str(ge.id))).all()
    assert [o.channel for o in out] == ["email"] and out[0].status == "queued"
    photo = client.get(f"/api/v1/gate/events/{ge.id}/photo", headers=auth_headers("Librarian"))
    assert photo.headers["content-type"] == "image/jpeg"

def test_ac06_issued_item_passes_silently(client, db_session, device_gate, camera, active_loan):
    client.post(f"/api/v1/devices/{device_gate.code}/events", headers={"X-Device-Key": device_gate.raw_key},
                json=gate_ev(active_loan.item_epc))
    ge = db_session.scalars(select(GateEvent)).one()
    assert ge.authorised and not ge.alarm

def test_fr07_offline_replay_out_of_order(client, db_session, auth_headers, device_gate, camera, tagged_item):
    h = {"X-Device-Key": device_gate.raw_key}
    early = gate_ev(tagged_item.active_epc, offline=True, when=datetime.now(UTC) - timedelta(minutes=10))
    late = gate_ev(tagged_item.active_epc, when=datetime.now(UTC))
    client.post(f"/api/v1/devices/{device_gate.code}/events", headers=h, json=late)
    client.post(f"/api/v1/devices/{device_gate.code}/events", headers=h, json=early)   # replay arrives later
    client.post(f"/api/v1/devices/{device_gate.code}/events", headers=h, json=early)   # duplicate replay
    events = client.get("/api/v1/gate/events", headers=auth_headers("Librarian")).json()
    assert len(events) == 2 and events[0]["occurred_at"] > events[1]["occurred_at"]
    assert any(e["offline_decision"] for e in events)
    assert db_session.query(NotificationOutbox).count() == 2
```
`backend/tests/integration/test_outbox.py`:
```python
import pytest
from datetime import UTC, datetime, timedelta
from app.worker import run_once

pytestmark = pytest.mark.db

def test_fr09_outbox_retries_then_sends(db_session, queued_email, monkeypatch, tmp_path):
    monkeypatch.setenv("MOCK_EMAIL_FAIL_FIRST", "1")
    monkeypatch.setenv("OUTBOX_DIR", str(tmp_path))
    now = datetime.now(UTC)
    assert run_once(db_session, now) == 0
    db_session.refresh(queued_email); assert queued_email.attempts == 1 and queued_email.status == "queued"
    assert run_once(db_session, now + timedelta(seconds=5)) == 1
    db_session.refresh(queued_email); assert queued_email.status == "sent"
    assert list((tmp_path / "email").glob("*.eml"))

def test_fr09_member_preferences_respected(db_session, sample_member):
    from app.services.notifications import NotificationsService
    sample_member.notify_email, sample_member.notify_sms = True, False
    rows = NotificationsService(db_session).queue_for_member(sample_member, "due_reminder", {"title": "X",
                                                                                              "due": "2026-10-10"})
    assert [r.channel for r in rows] == ["email"]
```
- [ ] **Steps 2–4: run (fail) → implement → run (green).**
- [ ] **Step 5: Commit.** `git commit -am "feat: gate alarm handling with CCTV snapshot, notification outbox and retrying worker (FR 07, FR 09, AC 06)"`

---

### Task 16: Smart-card staff login

**Files:**
- Create: `backend/app/integrations/credentials_mock.py`, `backend/app/middleware_rfid/handlers/card.py`, `backend/app/services/smartcard.py`
- Modify: `backend/app/api/v1/auth.py`, `frontend/src/pages/LoginPage.tsx`
- Test: `backend/tests/acceptance/test_ac07_smartcard_rbac.py`

**Interfaces:**
- Produces:
  - `SmartcardChallenges` (in-memory, thread-safe dict):
    - `.open(reader_code) -> challenge_id`
    - `.bind(reader_code, identity | None)`: binds to the newest open challenge for that reader
    - `.consume(reader_code, challenge_id) -> StaffIdentity` (single use, 60 s TTL; errors `CARD_CHALLENGE_INVALID`, `CARD_UNKNOWN`)
  - `CardTapped` handler: `CredentialProvider.resolve(uid)`, then `.bind`, publish `auth.card {reader_code, challenge_id, ok}`, and audit `auth.card.tap` (UID masked).
  - Endpoints `POST /auth/smartcard/challenge` and `POST /auth/smartcard`.
  - Login page: "Tap staff card" opens a challenge, listens on `/ws/live` (anonymous subscription restricted to the `auth.card` topic for that `challenge_id`), then completes the login.

- [ ] **Step 1: Failing test**

`backend/tests/acceptance/test_ac07_smartcard_rbac.py`:
```python
import uuid
from datetime import UTC, datetime
import pytest

pytestmark = [pytest.mark.db, pytest.mark.acceptance]

def tap(client, reader, uid):
    return client.post(f"/api/v1/devices/{reader.code}/events", headers={"X-Device-Key": reader.raw_key}, json={
        "event_id": str(uuid.uuid4()), "device_type": "smartcard_reader", "type": "CardTapped",
        "occurred_at": datetime.now(UTC).isoformat(), "epcs": [], "payload": {"card_uid": uid}})

def card_login(client, reader, uid):
    ch = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": reader.code}).json()
    tap(client, reader, uid)
    return client.post("/api/v1/auth/smartcard", json={"reader_code": reader.code,
                                                       "challenge_id": ch["challenge_id"]})

def test_ac07_card_login_and_role_enforcement(client, db_session, device_card):
    from tests.factories import make_staff
    make_staff(db_session, "CirculationClerk", username="clerkcard", smartcard_uid="04A1B2C3")
    make_staff(db_session, "Auditor", username="audcard", smartcard_uid="04D4E5F6")
    clerk = {"Authorization": f"Bearer {card_login(client, device_card, '04A1B2C3').json()['access_token']}"}
    aud = {"Authorization": f"Bearer {card_login(client, device_card, '04D4E5F6').json()['access_token']}"}
    assert client.get("/api/v1/admin/users", headers=clerk).status_code == 403
    assert client.post("/api/v1/migration/batches", headers=clerk).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=aud).status_code == 200
    assert client.post("/api/v1/circulation/checkout", headers=aud,
                       json={"member_card_no": "x", "item": "y"}).status_code == 403

def test_ac07_unknown_card_rejected_and_audited(client, db_session, device_card):
    from sqlalchemy import select
    from app.db.models import AuditLog
    r = card_login(client, device_card, "DEADBEEF")
    assert r.status_code == 401 and r.json()["code"] == "CARD_UNKNOWN"
    row = db_session.scalars(select(AuditLog).where(AuditLog.action == "auth.card.tap")).one()
    assert "DEADBEEF" not in str(row.details)

def test_ac07_challenge_single_use(client, db_session, device_card):
    from tests.factories import make_staff
    make_staff(db_session, "Librarian", username="libcard", smartcard_uid="04AAAAAA")
    ch = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": device_card.code}).json()
    tap(client, device_card, "04AAAAAA")
    body = {"reader_code": device_card.code, "challenge_id": ch["challenge_id"]}
    assert client.post("/api/v1/auth/smartcard", json=body).status_code == 200
    assert client.post("/api/v1/auth/smartcard", json=body).status_code == 401
```
> `/migration/batches` doesn't exist until Task 22. Register a stub router in this task that only declares `require("migration.run")` and returns 501, so the RBAC assertion holds. Task 22 replaces the stub.

- [ ] **Steps 2–4: run (fail) → implement → run (green).**
- [ ] **Step 5: Commit.** `git commit -am "feat: smart-card staff login via mock credential provider with challenge handshake (AC 07)"`

---

### Task 17: NCIP 2.0 subset and SIP2 adapter boundary

**Files:**
- Create: `backend/app/interop/{__init__,ncip,sip2,sip2_server}.py`, `backend/app/api/v1/ncip.py`, `backend/app/db/migrations/versions/0004_agency.py` (table `nexus.agency(code, name, api_key_hash)`)
- Test: `backend/tests/acceptance/test_ac03_circulation_interop.py`, `backend/tests/unit/test_sip2.py`

**Interfaces:**
- Consumes: `CirculationService`, `MembersService`.
- Produces:
  - `ncip.handle(xml_bytes: bytes, session, agency) -> bytes`. Parses with `defusedxml.ElementTree.fromstring`, so XXE is blocked. Namespace `http://www.niso.org/2008/ncip`. Dispatches on the first child of `NCIPMessage`, and builds the responses listed in interface design §3.1. `CirculationRefused(code)` becomes `<Problem><ProblemType>{code}</ProblemType><ProblemDetail>{message}</ProblemDetail></Problem>`. An unknown service gives `Unsupported Service`.
  - `POST /ncip` (header `X-Agency-Key`; 1 MB body limit).
  - `Sip2Adapter.handle(message: str) -> str`, using `Sip2Codec.parse(msg) -> (code, fixed, fields: dict[str, str])` and `Sip2Codec.build(code, fixed, fields) -> str` (adds `AY<seq>AZ<checksum>`).
  - `sip2_checksum(s: str) -> str`: the SIP2 checksum, `(-sum(bytes) & 0xFFFF)` as 4 uppercase hex digits.
  - `sip2_server.start(host, port)`: an asyncio TCP server, only when `SIP2_LISTENER_ENABLED`.

- [ ] **Step 1: Failing tests**

`backend/tests/unit/test_sip2.py`:
```python
from app.interop.sip2 import Sip2Codec, sip2_checksum

def test_fr03_sip2_checksum_known_value():
    msg = "9900302.00AY1AZ"
    assert sip2_checksum(msg) == f"{(-sum(msg.encode()) & 0xFFFF):04X}"

def test_fr03_sip2_parse_checkout_fields():
    code, fixed, fields = Sip2Codec.parse("11YN20261005    10150020261005    101500AOMAIN|AAM123456|ABACC-000001|AC|AY1AZF00F")
    assert code == "11" and fields["AA"] == "M123456" and fields["AB"] == "ACC-000001"
```
`backend/tests/acceptance/test_ac03_circulation_interop.py`:
```python
import re
import pytest
from sqlalchemy import select
from app.db.models import AuditLog, Loan

pytestmark = [pytest.mark.db, pytest.mark.acceptance]
NS = 'xmlns="http://www.niso.org/2008/ncip" version="http://www.niso.org/schemas/ncip/v2_02/ncip_v2_02.xsd"'

def ncip(client, agency, body):
    return client.post("/api/v1/ncip", content=f"<NCIPMessage {NS}>{body}</NCIPMessage>",
                       headers={"Content-Type": "application/xml", "X-Agency-Key": agency.raw_key})

def test_ac03_ncip_checkout_renew_checkin_audited(client, db_session, agency, sample_member, tagged_item):
    u = f"<UserId><UserIdentifierValue>{sample_member.card_no}</UserIdentifierValue></UserId>"
    i = f"<ItemId><ItemIdentifierValue>{tagged_item.accession_no}</ItemIdentifierValue></ItemId>"
    r1 = ncip(client, agency, f"<CheckOutItem>{u}{i}</CheckOutItem>")
    assert r1.status_code == 200 and "<DateDue>" in r1.text and "Problem" not in r1.text
    r2 = ncip(client, agency, f"<RenewItem>{u}{i}</RenewItem>")
    assert "<DateDue>" in r2.text
    r3 = ncip(client, agency, f"<CheckInItem>{i}</CheckInItem>")
    assert "Problem" not in r3.text
    loan = db_session.scalars(select(Loan).where(Loan.item_id == tagged_item.id)).one()
    assert loan.channel == "ncip" and loan.renew_count == 1 and loan.returned_at is not None
    actions = [a.action for a in db_session.scalars(select(AuditLog).order_by(AuditLog.id))
               if a.details.get("channel") == "ncip"]
    assert actions == ["circulation.checkout", "circulation.renew", "circulation.checkin"]

def test_ac04_ncip_refusal_matches_ui_code(client, agency, blocked_member, tagged_item):
    r = ncip(client, agency, f"<CheckOutItem><UserId><UserIdentifierValue>{blocked_member.card_no}"
             f"</UserIdentifierValue></UserId><ItemId><ItemIdentifierValue>{tagged_item.accession_no}"
             f"</ItemIdentifierValue></ItemId></CheckOutItem>")
    assert "<ProblemType>MEMBER_BLOCKED</ProblemType>" in r.text

def test_nfr02_ncip_rejects_xxe(client, agency):
    evil = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><NCIPMessage>&e;</NCIPMessage>'
    r = client.post("/api/v1/ncip", content=evil, headers={"Content-Type": "application/xml",
                                                          "X-Agency-Key": agency.raw_key})
    assert r.status_code == 400 and "root:" not in r.text

def test_ac03_sip2_checkout_renew_checkin(db_session, sample_member, tagged_item):
    from app.interop.sip2 import Sip2Adapter
    a = Sip2Adapter(db_session)
    co = a.handle(f"11YN20261005    101500                  AOMAIN|AA{sample_member.card_no}|AB{tagged_item.accession_no}|AC|")
    assert co.startswith("121")                   # ok = 1
    rn = a.handle(f"29NN20261005    101500                  AOMAIN|AA{sample_member.card_no}|AB{tagged_item.accession_no}|")
    assert rn.startswith("301")
    ci = a.handle(f"09N20261005    10150020261005    101500AP|AOMAIN|AB{tagged_item.accession_no}|AC|")
    assert ci.startswith("101")
    loan = db_session.scalars(select(Loan).where(Loan.item_id == tagged_item.id)).one()
    assert loan.channel == "sip2" and loan.returned_at is not None
```
- [ ] **Steps 2–4: run (fail) → implement → run (green).** The fixture `agency` creates an agency `KIOSK-01` with `.raw_key`.
- [ ] **Step 5: Commit.** `git commit -am "feat: NCIP 2.0 message subset and SIP2 adapter boundary over shared circulation (FR 03, AC 03)"`

---

### Task 18: Device simulator

**Files:**
- Create: `device-sim/sim.py`, `device-sim/requirements.txt` (pinned `httpx`, `fastapi`, `uvicorn`, `websockets`), `device-sim/Dockerfile`, `device-sim/panel.html`, `device-sim/test_sim.py`
- Modify: `docker-compose.yml` (service `devsim`, profile `demo`, port 8100)

**Interfaces:**
- Produces:
  - CLI: `python sim.py <command>` where command is one of:
    - `tap --reader CARD-01 --uid 04A1B2C3`
    - `scan --station STAFF-01 --epc ...`
    - `sweep --handheld HH-01 --shelf A-01 --session <id> [--omit N] [--add-foreign B-01]`
    - `gate --gate GATE-01 --epc ... [--direction out]`
    - `offline on|off`
    - `heartbeat --all`
  - The panel at `:8100` has buttons for the same commands and lists shelf EPCs fetched from the API with a demo Librarian token entered in the panel.
  - `OfflineQueue(path="sim-queue.jsonl")`: events that fail to send (connection error, 5xx) or are sent in `offline on` mode are appended to the queue with their original `event_id` and `occurred_at`. `flush()` replays them in order when the API is back. In offline mode, the gate decides locally from the `security_bit` it holds in its tag cache (`/tags?status=active` snapshot), sets `offline_decision=true`, and prints/plays the alarm.
  - Device keys come from `ops/demo-credentials.txt` or the `SIM_DEVICE_KEYS` env var.

- [ ] **Step 1: Failing test**

`device-sim/test_sim.py`:
```python
import json
from sim import OfflineQueue

def test_offline_queue_preserves_event_identity(tmp_path):
    q = OfflineQueue(tmp_path / "q.jsonl")
    e1 = {"event_id": "a", "occurred_at": "2026-10-05T10:00:00Z"}
    e2 = {"event_id": "b", "occurred_at": "2026-10-05T10:01:00Z"}
    q.append(e1); q.append(e2)
    sent = []
    q.flush(lambda ev: sent.append(ev) or True)
    assert [e["event_id"] for e in sent] == ["a", "b"]
    assert q.size() == 0

def test_offline_queue_stops_on_failure_and_keeps_rest(tmp_path):
    q = OfflineQueue(tmp_path / "q.jsonl")
    for i in range(3):
        q.append({"event_id": str(i)})
    q.flush(lambda ev: ev["event_id"] != "1")
    assert q.size() == 2
```
Run: `cd device-sim && python -m pytest -q`. Expected: FAIL (no `sim`).

- [ ] **Step 2: Implement `sim.py`** (CLI via `argparse`, panel via a FastAPI app serving `panel.html` and the `/do/<command>` endpoints, and the `OfflineQueue` as tested).
- [ ] **Step 3: Run the tests, then manually check that gate offline mode works end to end:**
  1. `docker compose stop api`
  2. `python sim.py gate --gate GATE-01 --epc <unissued>`: prints "ALARM (offline decision)" and queues the event
  3. `docker compose start api`
  4. `python sim.py offline off`: flushes the queue
  5. The gate monitor shows the event with an offline badge
- [ ] **Step 4: Commit.** `git commit -am "feat: device simulator with CLI, panel and offline event queue (FR 03, FR 07)"`

---

### Task 19: RFID UI screens

**Files:**
- Create: `frontend/src/pages/{TaggingPage,InventoryPage,GateMonitorPage,DevicesPage,OutboxPage}.tsx`, `frontend/src/lib/{live.ts,audio.ts}`, `frontend/src/lib/audio.test.ts`
- Modify: `frontend/src/pages/ItemPage.tsx` (tag panel), `frontend/src/pages/LoginPage.tsx` (card button enabled)

**Interfaces:**
- Produces:
  - `useLive(topic, handler)`: WebSocket hook with auto-reconnect.
  - `playConfirmation(kind: "ok"|"warn"|"error", ctx?: AudioContext)`. Web Audio patterns:
    - `ok`: one 880 Hz beep, 120 ms
    - `warn`: two 660 Hz beeps, 100 ms each, 80 ms gap
    - `error`: one 300 Hz tone, 600 ms

- [ ] **Step 1: Failing test**

`frontend/src/lib/audio.test.ts`:
```ts
import { it, expect, vi } from "vitest";
import { playConfirmation, PATTERNS } from "./audio";

it("defines distinct patterns", () => {
  expect(PATTERNS.ok.length).toBe(1);
  expect(PATTERNS.warn.length).toBe(2);
  expect(PATTERNS.error[0].freq).toBeLessThan(PATTERNS.ok[0].freq);
});

it("schedules one oscillator per tone", () => {
  const start = vi.fn(), stop = vi.fn();
  const ctx: any = { currentTime: 0, destination: {},
    createOscillator: () => ({ frequency: { value: 0 }, connect: () => ({ connect: () => {} }), start, stop }),
    createGain: () => ({ gain: { value: 0 }, connect: () => {} }) };
  playConfirmation("warn", ctx);
  expect(start).toHaveBeenCalledTimes(2);
});
```
- [ ] **Step 2: Implement the screens.**
  - **Tagging:** pick an item, run validation, "Waiting for tag on STAFF-01…" (`tag.read` topic), associate, and show the tag history.
  - **Inventory:** choose a shelf, start a session, and show a live grid that colours each read green, amber or red and plays the pattern. On close, show the report with missing/misplaced lists and a "mark missing" action.
  - **Gate monitor:** a live alert list with the CCTV image, accession number, offline badge, and notification status.
  - **Devices:** online/offline status and last heartbeat.
  - **Outbox:** queued, sent and failed messages, with the recipient masked.
- [ ] **Step 3: Verify.** Run `npx vitest run && npm run build`. Then manual demo rehearsal of AC 02, 05, 06 and 07 through the simulator panel; save screenshots to `docs/06-testing/evidence/stage5/`.
- [ ] **Step 4: Commit.** `git commit -am "feat: tagging, inventory with audible confirmation, gate monitor, devices and outbox screens"`

### Task 20: Stage 5 gate

- [ ] Run the full suite plus `ops/ci-local.sh`.
- [ ] Update the RTM: FR 03, 05, 06, 07, 09 and AC 02, 03, 05, 06, 07 → Done/Mock, with test IDs.
- [ ] Record the SOP bullet "Test retries, timeouts, duplicate events, and offline behaviour" with these test IDs as evidence: `test_fr03_command_times_out_and_retries`, `test_fr03_duplicate_event_ignored`, `test_fr09_outbox_retries_then_sends`, `test_fr07_offline_replay_out_of_order`, and the simulator offline queue tests.
- [ ] Write `stage-gates/stage-5.md`, update the progress log, merge `--no-ff`, tag `sop-stage-5`, and branch `stage/6-migration`.

---

# SOP Stage 6: Migration and resilience (branch `stage/6-migration`)

### Task 21: Synthetic 20k spreadsheet generator and profiler

**Files:**
- Create: `migration/gen_sample.py`, `migration/profile.py`, `migration/mapping.yaml`, `migration/rules.yaml`, `migration/requirements.txt` (pinned `openpyxl`, `Faker`, `PyYAML`), `migration/test_gen_sample.py`

**Interfaces:**
- Produces:
  - `generate(path, rows=20000, invalid_rate=0.03, dup_rate=0.02, seed=42) -> Manifest(rows, invalid_rows: list[int], duplicate_rows: list[int])`. Writes the `.xlsx` plus `<file>.manifest.json` with the injected defect row numbers, so the reconciliation can be checked against ground truth.
  - Injected defects:
    - missing title
    - bad ISBN checksum
    - year 2099
    - malformed accession number (`AC#12`)
    - unknown `item_type`
    - negative price
  - Messy-but-valid cells: ISBN stored as a number, Excel date serial in `acquired_on`, trailing spaces, mixed-case `item_type`.
  - Duplicates: an exact repeat of an earlier row (same accession number), and a "likely duplicate" (same normalised title, author and year with a different accession number, flagged rather than rejected).
  - Accession numbers start at `ACC-100001`, so they never collide with the seeded `legacy_ilms` range (`ACC-000001`…).
  - `profile(path) -> dict`: row count, null counts per column, distinct counts, sample values. Written to `docs/05-data-migration/profile-report.md`.

- [ ] **Step 1: Failing test**

`migration/test_gen_sample.py`:
```python
import json
from openpyxl import load_workbook
from gen_sample import generate

def test_fr10_generator_counts_and_manifest(tmp_path):
    f = tmp_path / "s.xlsx"
    m = generate(f, rows=1000, seed=1)
    ws = load_workbook(f, read_only=True).active
    assert ws.max_row == 1001
    assert 20 <= len(m.invalid_rows) <= 40 and 10 <= len(m.duplicate_rows) <= 30
    assert json.loads((tmp_path / "s.xlsx.manifest.json").read_text())["rows"] == 1000

def test_fr10_generator_is_deterministic(tmp_path):
    a = generate(tmp_path / "a.xlsx", rows=200, seed=7)
    b = generate(tmp_path / "b.xlsx", rows=200, seed=7)
    assert a.invalid_rows == b.invalid_rows
```
- [ ] **Step 2: Implement → Step 3: Run green → generate the real file:**
  ```bash
  python migration/gen_sample.py --rows 20000 --out migration/samples/library-export-20k.xlsx
  python migration/profile.py migration/samples/library-export-20k.xlsx > docs/05-data-migration/profile-report.md
  ```
- [ ] **Step 4: Commit.** `git commit -am "feat: synthetic 20k library export generator with defect manifest and profiler (FR 10)"`

---

### Task 22: Migration engine, API, CLI and console

**Files:**
- Create: `backend/app/services/migration/{__init__,reader,validate,dedupe,commit,report}.py`, `backend/app/api/v1/migration.py` (replaces the Task 16 stub), `migration/nexus_migrate.py` (CLI calling the API), `frontend/src/pages/MigrationPage.tsx`
- Test: `backend/tests/unit/test_migration_validate.py`, `backend/tests/acceptance/test_ac01_migration.py`

**Interfaces:**
- Produces:
  - `read_rows(file: BinaryIO, filename: str, mapping: dict) -> Iterator[RawRow(row_no, cells: dict)]` (xlsx via openpyxl read-only; csv via `csv` with UTF-8, falling back to cp1252).
  - `normalise(cells) -> dict`: strip, collapse whitespace, ISBN digits only (numbers → str without `.0`), Excel serial → date, lower-case `item_type`.
  - `validate(row: dict, rules: dict) -> list[str]` (reason codes). Rules are loaded from `migration/rules.yaml`, copied into the image at `app/services/migration/rules.yaml`.
  - `MigrationService(session)`:
    - `.stage(file, filename, actor) -> MigrationBatch`: bulk insert into `staging.import_row` in chunks of 1000 with `session.execute(insert(ImportRow), rows)`.
    - `.validate(batch_id) -> BatchCounts`: sets `status` and `reasons`.
    - `.dedupe(batch_id)`: exact = same `accession_no` earlier in the file, or already in `nexus.item`; likely = same `(lower(title), lower(author), pub_year)` with a different accession number. Likely duplicates are still committed but flagged with reason `LIKELY_DUPLICATE` in the report, with status `valid`. The SOP says "identify duplicates"; exact duplicates are excluded.
    - `.report(batch_id) -> ReconciliationReport(source, valid, rejected, duplicate, likely_duplicate, committed, by_reason: dict, balanced: bool)`
    - `.commit(batch_id, actor) -> ReconciliationReport`:
      1. Run the backup via `ops_backup.run_backup(reason=f"pre-migration-{batch_id}")`.
      2. Record the integrity snapshot (`ops_integrity.snapshot()`).
      3. In one transaction, insert a `Bib` per distinct `(title, author, isbn, pub_year)` and an `Item` per valid row, all tagged with `migration_batch_id`. Set `rows_committed` and `committed_at`.
      4. Re-check integrity and fail the batch if the legacy checksums differ.
      5. Audit `migration.commit`.
    - `.rollback(batch_id, actor)`: deletes `nexus.item`, then orphan `nexus.bib`, `WHERE migration_batch_id = :id` (ORM delete), sets status `rolled_back`, and audits.
  - Backup and integrity helpers are imported from `ops/` as a package installed into the image (`ops/nexus_ops/`). ADR-0003 allows raw SQL there.
  - Endpoints from interface design §1 "Migration" (upload: multipart, `.xlsx`/`.csv` only, checked by extension and the magic bytes `PK\x03\x04` for xlsx, size ≤ `upload_max_mb`).
  - CLI: `python migration/nexus_migrate.py --api https://localhost:8443 --file … [--dry-run] [--commit] [--rollback BATCH]`. Prompts for the admin password; never takes it as an argument.

- [ ] **Step 1: Failing tests**

`backend/tests/unit/test_migration_validate.py`:
```python
import datetime as dt
import pytest
from app.services.migration.validate import load_rules, normalise, validate

RULES = load_rules()

def ok_row(**kw):
    base = {"accession_no": "ACC-100001", "barcode": "BC10000001", "title": "T", "author": "A",
            "isbn": "9780470695067", "pub_year": 2010, "item_type": "lending", "price": 100}
    return {**base, **kw}

@pytest.mark.parametrize("override,code", [
    ({"title": ""}, "TITLE_MISSING"),
    ({"isbn": "9780470695060"}, "ISBN_CHECKSUM"),
    ({"pub_year": 2099}, "YEAR_RANGE"),
    ({"accession_no": "AC#12"}, "ACCESSION_FORMAT"),
    ({"item_type": "loanable"}, "ITEM_TYPE_UNKNOWN"),
    ({"price": -5}, "PRICE_NEGATIVE"),
])
def test_fr10_rule_reason_codes(override, code):
    assert code in validate(ok_row(**override), RULES)

def test_fr10_messy_cells_normalised():
    n = normalise({"isbn": 9780470695067.0, "acquired_on": 45200, "title": "  Wireless   Networks ",
                   "item_type": "Reference", "accession_no": " ACC-100002"})
    assert n["isbn"] == "9780470695067"
    assert n["acquired_on"] == dt.date(2023, 9, 30)
    assert n["title"] == "Wireless Networks" and n["item_type"] == "reference"
    assert n["accession_no"] == "ACC-100002"
    assert validate({**ok_row(), **n}, RULES) == []
```
`backend/tests/acceptance/test_ac01_migration.py`:
```python
import json
import pytest
from sqlalchemy import func, select
from app.db.models import Item

pytestmark = [pytest.mark.db, pytest.mark.acceptance]

def test_ac01_stage_validate_commit_reconcile(client, db_session, auth_headers, sample_xlsx, integrity):
    h = auth_headers("Admin")
    before = integrity.snapshot()
    with open(sample_xlsx.path, "rb") as f:
        b = client.post("/api/v1/migration/batches", headers=h,
                        files={"file": ("export.xlsx", f, "application/vnd.openxmlformats-officedocument."
                                                           "spreadsheetml.sheet")}).json()
    rep = client.post(f"/api/v1/migration/batches/{b['id']}/validate", headers=h).json()
    m = sample_xlsx.manifest
    assert rep["source"] == m.rows
    assert rep["rejected"] == len(m.invalid_rows)
    assert rep["duplicate"] == len(m.exact_duplicate_rows)
    assert rep["source"] == rep["valid"] + rep["rejected"] + rep["duplicate"]
    assert db_session.scalar(select(func.count()).select_from(Item)
                             .where(Item.migration_batch_id == b["id"])) == 0          # dry run wrote nothing
    done = client.post(f"/api/v1/migration/batches/{b['id']}/commit", headers=h).json()
    assert done["committed"] == rep["valid"] and done["balanced"] is True
    assert done["backup_file"].endswith(".dump")
    assert integrity.snapshot() == before
    csv = client.get(f"/api/v1/migration/batches/{b['id']}/report", headers=h, params={"format": "csv"})
    assert "ISBN_CHECKSUM" in csv.text

def test_ac01_batch_rollback(client, db_session, auth_headers, committed_batch):
    h = auth_headers("Admin")
    client.post(f"/api/v1/migration/batches/{committed_batch}/rollback", headers=h)
    assert db_session.scalar(select(func.count()).select_from(Item)
                             .where(Item.migration_batch_id == committed_batch)) == 0

def test_nfr02_upload_rejects_non_spreadsheet(client, auth_headers):
    r = client.post("/api/v1/migration/batches", headers=auth_headers("Admin"),
                    files={"file": ("x.xlsx", b"MZ\x90\x00not-a-zip", "application/octet-stream")})
    assert r.status_code == 422 and r.json()["code"] == "UPLOAD_TYPE_INVALID"
```
Fixtures:
- `sample_xlsx`: generates 2,000 rows into `tmp_path` with the Task 21 generator, imported via `sys.path`.
- `integrity`: wraps `nexus_ops.integrity`.
- `committed_batch`: runs the full flow on 200 rows.

These tests commit for real, because the commit path takes `pg_dump` backups of a real database. They therefore run against `nexus_test` with a clean-up fixture that deletes the batch's rows and resets the staging tables afterwards. The backup directory points at `tmp_path`.

- [ ] **Steps 2–4: run (fail) → implement → run (green).** The Migration console page has upload, a "Validate (dry run)" button, a counts panel with reason breakdown, a downloadable error CSV, a Commit button with a confirmation dialog stating the backup will be taken, and a Rollback button.
- [ ] **Step 5: Full-size timing run (perf evidence).**
  Run:
  ```bash
  time python migration/nexus_migrate.py --api https://localhost:8443 --file migration/samples/library-export-20k.xlsx --commit
  ```
  Record the timings in `docs/05-data-migration/migration-run-report.md` along with the validation and reconciliation reports (copied from the API output). Target: under 5 minutes (Q-08).
- [ ] **Step 6: Commit.** `git commit -am "feat: staged spreadsheet migration with validation, de-duplication, reconciliation and rollback (FR 10, AC 01)"`

---

### Task 23: Backup, restore and integrity tooling

**Files:**
- Create: `ops/nexus_ops/{__init__,integrity,backup}.py`, `ops/integrity.py` (CLI wrapper), `ops/backup.sh`, `ops/backup.ps1`, `ops/restore.sh`, `ops/restore.ps1`, `ops/tests/test_integrity.py`
- Test: `backend/tests/acceptance/test_ac10_restore_integrity.py`

**Interfaces:**
- Produces:
  - `integrity.snapshot(owner_url: str | None = None) -> dict[str, {"rows": int, "sha256": str}]` for every table in `legacy_ilms`. Hash = SHA-256 over `row_to_json(t)::text` for each row, ordered by primary key, streamed with a server-side cursor. Table names come from `information_schema.tables` filtered to the schema, and are quoted with `psycopg.sql.Identifier`.
  - `integrity.compare(a, b) -> list[str]` (the tables that differ).
  - The CLI `python ops/integrity.py snapshot --out FILE` / `compare A B` writes JSON to `ops/reports/`.
  - `backup.run_backup(reason: str) -> Path` runs `pg_dump -Fc` via subprocess with the URL from the environment (password passed through `PGPASSWORD`, never on the command line) and writes a `.sha256` file next to the dump.
  - `backup.run_restore(path: Path) -> None` verifies the SHA-256, then runs `pg_restore --clean --if-exists --no-owner --role=nexus_owner --single-transaction`.
  - The shell/PowerShell wrappers run these inside the `api` container: `docker compose exec api python -m nexus_ops.backup --reason manual`.

- [ ] **Step 1: Failing test**

`backend/tests/acceptance/test_ac10_restore_integrity.py`:
```python
import pytest
from sqlalchemy import func, select
from app.db.models import Item

pytestmark = [pytest.mark.db, pytest.mark.acceptance]

def test_ac10_restore_after_failed_migration_proves_legacy_intact(committed_world_db, integrity, ops_backup):
    legacy_before = integrity.snapshot()
    nexus_items_before = committed_world_db.count(Item)
    dump = ops_backup.run_backup(reason="test-pre-change")
    committed_world_db.simulate_bad_migration(rows=500)          # inserts junk items in nexus
    assert committed_world_db.count(Item) == nexus_items_before + 500
    ops_backup.run_restore(dump)
    assert committed_world_db.count(Item) == nexus_items_before
    assert integrity.snapshot() == legacy_before

def test_ac10_restore_refuses_tampered_backup(ops_backup, tmp_path):
    dump = ops_backup.run_backup(reason="tamper")
    with open(dump, "ab") as f:
        f.write(b"x")
    with pytest.raises(ValueError, match="checksum"):
        ops_backup.run_restore(dump)
```
`committed_world_db` operates on a dedicated database `nexus_restore_test`, created and migrated for this module, so that a restore can't disturb other tests.

- [ ] **Steps 2–4: run (fail) → implement → run (green).**
- [ ] **Step 5: Live rehearsal for evidence** against the dev stack:
  1. `python ops/integrity.py snapshot`
  2. Commit the 20k migration.
  3. Simulate a failure: `docker compose exec db psql -U nexus_owner -c "UPDATE nexus.item SET status='withdrawn' WHERE migration_batch_id=..."`
  4. `ops/restore.sh <pre-migration dump>`
  5. `python ops/integrity.py compare before.json after.json`, which prints `IDENTICAL`.

  Record the output in `docs/05-data-migration/restore-and-integrity-report.md`.
- [ ] **Step 6: Commit.** `git commit -am "feat: verified backup, restore and legacy integrity checksums (NFR 01, AC 10)"`

### Task 24: Stage 6 gate

- [ ] Write `docs/05-data-migration/README.md` (D5): schema pointer, migration list (`alembic history`), sample dataset, import utility usage, links to the validation, reconciliation and restore reports, and the rollback procedure.
- [ ] Update the RTM: FR 10, NFR 01, AC 01, AC 10 → Done.
- [ ] Write `stage-gates/stage-6.md`, mapping the SOP bullets (profile, validation + dry run, reconcile, migrate → rollback → restore).
- [ ] Merge `--no-ff`, tag `sop-stage-6`, and branch `stage/7-verification`.

---

# SOP Stage 7: Verification (branch `stage/7-verification`)

### Task 25: Full verification run and test-to-requirement matrix

**Files:**
- Create: `backend/tests/perf/locustfile.py` (or `perf_async.py` using httpx + asyncio if Locust can't be installed offline), `docs/06-testing/test-plan.md`, `docs/06-testing/test-results.md`, `docs/06-testing/test-to-requirement-matrix.md`, `docs/06-testing/security-checks.md`, `docs/06-testing/performance-results.md`, `docs/06-testing/uat-checklist.md`, `ops/tests/ac09_offline_lifecycle.md`
- Create: `backend/tests/regression/test_api_contract.py`

**Interfaces:**
- Consumes: everything.
- Produces: the evidence for D6.

- [ ] **Step 1: Regression contract test**

`backend/tests/regression/test_api_contract.py`:
```python
import json
import pathlib
from fastapi.testclient import TestClient
from app.main import create_app

SNAPSHOT = pathlib.Path(__file__).parents[3] / "docs" / "08-operations" / "openapi.json"

def test_nfr05_no_endpoint_removed_since_last_release():
    current = TestClient(create_app(check_db=False)).get("/api/openapi.json").json()
    published = json.loads(SNAPSHOT.read_text())
    missing = {(p, m) for p, ops in published["paths"].items() for m in ops} - \
              {(p, m) for p, ops in current["paths"].items() for m in ops}
    assert missing == set()
```
Refresh the snapshot with the Task 11 export command, then run the test. Expected: PASS.

- [ ] **Step 2: Performance.** The async script runs 50 concurrent virtual users for 60 s with this mix:

| Share | Request |
|---|---|
| 70% | OPAC search with random terms |
| 20% | checkout + checkin pairs on a pool of 200 items |
| 10% | dashboard |

It reports p50/p95/p99 and the error rate. Run it against the full stack (`https://localhost:8443`) and record the results, the host spec and the Q-08 targets in `performance-results.md`. Add the 20k migration timing from Task 22. These are observations only; no certification is claimed.

- [ ] **Step 3: Security checks.** Run `bandit -r app`, `pip-audit`, `npm audit`, `ruff`, `mypy`. Then do a short manual review against security-design §2, with these checks:
  - `curl` without a token → 401
  - clerk → admin endpoint → 403
  - patron → another member's loans → 403
  - error responses contain no traces
  - TLS headers present (`curl -kI https://localhost:8443`)
  - `.env` not tracked (`git ls-files | grep -c "^.env$"` → 0)
  - secret scan: `git log -p | grep -E "BEGIN (RSA|EC|OPENSSH) PRIVATE KEY|JWT_SECRET=[^r]"` → nothing

  Record each command and its result in `security-checks.md`.

- [ ] **Step 4: Full functional, integration, regression and acceptance run.**
  Run: `bash ops/ci-local.sh` and `.venv/Scripts/pytest -q -m acceptance --junitxml=../docs/06-testing/junit-acceptance.xml`
  Expected: all green. Paste the summaries into `test-results.md`.

- [ ] **Step 5: Test-to-requirement matrix.** Generate it from test names: a small script `ops/trace_tests.py` greps `test_(fr|nfr|ac)\d+` names and joins them with the JUnit results into a markdown table (requirement → tests → pass/fail). Then copy the test IDs into the RTM.

- [ ] **Step 6: UAT checklist.** One row per AC with: steps (from the demo script), expected result, actual result, evidence screenshot path, and pass/fail. Execute it against the running stack, with screenshots in `docs/06-testing/evidence/uat/`.

- [ ] **Step 7: Defect triage.** Every failure found in Steps 1–6 goes into `defect-log.md` with a severity. Fix S1/S2 on `fix/<id>-*` branches merged into the stage branch, record the retest evidence, and leave S3/S4 as known limitations.

- [ ] **Step 8: Commit, gate, merge, tag.**
  1. Write `stage-gates/stage-7.md`, mapping each SOP bullet: functional, integration, regression, performance, security, migration, backup, restore, offline-update, rollback. Offline update and rollback are covered by Task 26's AC 09 run; finish Task 26 Steps 1–4 before signing this gate.
  2. Merge `--no-ff`, tag `sop-stage-7`.

---

# Release and handover (deliverables D7–D9; branch `release/1.0.0`)

### Task 26: Offline bundle, install, update and rollback (AC 09)

**Files:**
- Create: `ops/build_bundle.sh`, `ops/build_bundle.ps1`, `ops/install.sh`, `ops/install.ps1`, `ops/update.sh`, `ops/update.ps1`, `ops/rollback.sh`, `ops/rollback.ps1`, `ops/licence.py`, `ops/tests/test_bundle_scripts.sh`
- Modify: `backend/app/main.py` (licence check sets `app.state.licence_status` to `valid|missing|invalid`; a missing or invalid licence puts the app in read-only mode for non-admins, which shows the activation path)

**Interfaces:**
- Produces:
  - `build_bundle <version>`:
    1. `docker compose build`
    2. `docker save nexus-api:<v> nexus-web:<v> postgres:16.4-alpine nexus-devsim:<v> | gzip > images.tar.gz`
    3. Copy `docker-compose.yml`, `.env.example`, `ops/*.sh|*.ps1`, `ops/db/init`, `ops/nginx`, `VERSION`, the SBOM and `RELEASE-NOTES.md` into `nexus-<v>/`
    4. Write `SHA256SUMS`
    5. Zip to `ops/bundles/nexus-<v>.zip`
  - `install`:
    1. Verify `SHA256SUMS`.
    2. `docker load`.
    3. Create `.env` from the example with generated secrets (`openssl rand -hex 32`, or `[Convert]::ToHexString(RandomNumberGenerator)` on Windows) if absent.
    4. Generate the TLS certificate.
    5. `docker compose up -d`.
    6. Wait for health.
    7. Run seeding only if `--demo` is given.
    8. Print the URL.
  - `update <bundle>`:
    1. Verify.
    2. `run_backup(reason=pre-update-<from>-<to>)`.
    3. Record `previous_version` in `ops/state.json`.
    4. `docker load`.
    5. Set `NEXUS_VERSION=<to>` in `.env`.
    6. `docker compose up -d`.
    7. Wait for health (120 s); on failure, run `rollback` automatically.
  - `rollback`:
    1. Read `ops/state.json`.
    2. Run `alembic downgrade <previous release's rev>` inside the *new* image (a downgrade needs the newer migration files).
    3. Set `NEXUS_VERSION=<previous>`.
    4. `docker compose up -d`.
    5. Health check.
    6. If the downgrade fails, restore the pre-update backup instead.
  - `licence.py issue --site NAME --expires DATE --key-file K` writes `licence.json`: `{site, expires, features, sig: HMAC-SHA256}`. The app verifies it with `LICENCE_KEY`.
  - Release `1.0.1` is a real but small change: add an `/api/v1/version` field `"build_notes"` plus a migration `0005_release_101.py` that adds `app_setting` key `ui_banner` with a working downgrade. That makes the update visibly change both the API and the schema.

- [ ] **Step 1: Script test.**
  `ops/tests/test_bundle_scripts.sh` builds a bundle and asserts that:
  - the zip contains `SHA256SUMS`, `images.tar.gz` and the scripts
  - `sha256sum -c` passes
  - corrupting one byte of `images.tar.gz` makes `install.sh --verify-only` exit non-zero

  Run: `bash ops/tests/test_bundle_scripts.sh`. Expected: FAIL first (scripts missing), then PASS.

- [ ] **Step 2: Build v1.0.0 and v1.0.1 bundles.**
  1. Tag `v1.0.0` on the release branch and run `ops/build_bundle.sh 1.0.0`.
  2. Make the 1.0.1 change (with a test asserting `build_notes` exists), set `VERSION` to 1.0.1, tag `v1.0.1`, and run `ops/build_bundle.sh 1.0.1`.
  3. Return the working tree to 1.0.1.

- [ ] **Step 3: Offline rehearsal (AC 09 evidence).**
  1. `docker compose down -v`, then remove the nexus images (`docker image rm nexus-api:1.0.0 …`).
  2. Disable networking: Windows `Disable-NetAdapter` on the active adapter, or Docker Desktop with network access off. Record which.
  3. Unzip `nexus-1.0.0.zip` into a scratch folder and run `install.ps1 -Demo`. Expected: healthy; `/version` shows 1.0.0.
  4. Run `update.ps1 nexus-1.0.1.zip`. Expected: backup created; `/version` shows 1.0.1 with `build_notes`; `alembic_rev` = 0005.
  5. Run `rollback.ps1`. Expected: `/version` shows 1.0.0; `alembic_rev` = previous; `integrity.py compare` shows legacy identical; demo data intact.
  6. Re-enable networking.

  Record every command, its output and screenshots in `ops/tests/ac09_offline_lifecycle.md` and `docs/06-testing/evidence/ac09/`.

- [ ] **Step 4: Commit.** `git commit -am "feat: offline bundle build, verified install, update with auto-rollback and documented rollback (FR 12, AC 09)"`

### Task 27: Operational documentation, demonstration pack and final release

**Files:**
- Create:
  - `docs/04-repository/sbom-and-licences.md` (generated by `pip-licenses==5.0.0 --format=markdown --with-urls` and `npx license-checker-rseidelsohn --markdown`, plus container base images and offline-installation notes)
  - `docs/07-deployment/{environment-checklist,installation-guide,configuration-guide,backup-restore,update-rollback}.md`
  - `docs/08-operations/{administrator-guide,user-guide,api-guide,troubleshooting-runbook,training-plan,device-configuration}.md`
  - `docs/09-demo/{demo-script,presentation-outline,known-limitations,production-backlog}.md`
  - `RELEASE-NOTES.md`
- Modify: `README.md`, `docs/01-requirements/rtm.md` (final statuses), `docs/00-project-control/progress-log.md`, `docs/00-project-control/issue-tracker.md`

- [ ] **Step 1: D7 deployment package documents**
  - **Environment checklist:** Windows Server 2022 with Docker (Linux containers through WSL2/Hyper-V) or a Linux VM; CPU/RAM/disk; ports 443 and 6001; certificate; time sync; backup storage.
  - **Installation guide:** step-by-step `install.ps1` / `install.sh`.
  - **Configuration guide:** every `.env` key with its meaning and default; adapter switching.
  - **Backup/restore:** schedule recommendation, commands, verification.
  - **Update/rollback:** commands, the automatic rollback conditions, and the manual fallback.

- [ ] **Step 2: D8 operational documents**
  - **Administrator guide:** users and roles, policies, devices and keys, migrations, audit review, licence activation.
  - **User guide:** one section per role, with screenshots from the evidence folders.
  - **API guide:** authentication, error codes, refusal codes, device event contract, NCIP/SIP2 coverage; links to `openapi.json`.
  - **Troubleshooting runbook:** symptom → check → fix for:
    - API unhealthy
    - DB down
    - device offline
    - gate events not arriving
    - outbox stuck
    - migration failed
    - update failed
    - licence invalid
    - certificate expired
  - **Training plan:** sessions per role, duration, exercises using the simulator, assessment checklist.
  - **Device configuration:** the interface-design §5 table plus how to register a device and rotate keys.

- [ ] **Step 3: D9 demonstration documents**
  - **Demo script:** §1–§10, one per AC, each with exact clicks/commands and expected output; about 15 minutes in total.
  - **Presentation outline:** problem, architecture, SOP stage evidence, AC walkthrough, limitations, backlog.
  - **Known limitations:** every RTM item with status Partial, Mock or Backlog, plus S3/S4 defects.
  - **Production backlog:** real vendor SDK adapters (RFID, CCTV/VMS, SMS gateway, SMTP), full NCIP/SIP2 coverage and conformance testing, ISO 28560 tag encoding, acquisition and serials modules, multi-branch, i18n, HA/replication, native Windows service packaging, PKI licensing, SSO/LDAP, legacy re-sync job, penetration test, accessibility audit, data retention policy.

- [ ] **Step 4: Final checks**
  ```bash
  git log --format='%an <%ae>' | sort -u
  git log --format='%B' | grep -ciE 'co-authored|generated with'
  git ls-files | grep -iE '(^|/)\.env$'
  ```
  Expected:
  - Line 1 prints a single author line.
  - Line 2 prints `0`.
  - Line 3 prints nothing.

  Then confirm the RTM has no row without a status and test IDs (Backlog rows reference the backlog item).

- [ ] **Step 5: Record the demo** (screen capture following the demo script) and store the video outside the repository, linked from `docs/09-demo/README.md`.

- [ ] **Step 6: Final release**
  ```bash
  git add -A
  git commit -m "docs: deployment, operations and demonstration packages for release 1.0.0"
  git checkout main
  git merge --no-ff release/1.0.0 -m "Merge release/1.0.0: release and handover"
  git tag -a v1.0.0-eval -m "Final evaluation release"
  ```
