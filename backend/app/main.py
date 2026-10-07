import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from alembic.runtime.migration import MigrationContext
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.api.v1 import (
    admin,
    auth,
    catalog,
    circulation,
    devices,
    fines,
    gate,
    health,
    inventory,
    members,
    migration,
    ncip,
    opac,
    reports,
    tags,
    ws,
)
from app.core.config import DEV_ENVIRONMENTS, get_settings
from app.core.errors import install_error_handlers
from app.core.licence import ReadOnlyUntilLicensed, status_from_file
from app.core.logging import configure_logging
from app.core.ratelimit import limiter
from app.db.base import engine
from app.middleware_rfid import handlers as _event_handlers  # noqa: F401  (registers device event handlers)

log = logging.getLogger("nexus.health")


def _database_check(app: FastAPI) -> tuple[str, bool]:
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
            ctx = MigrationContext.configure(conn, opts={"version_table_schema": "nexus"})
            app.state.alembic_rev = ctx.get_current_revision()
        return "database", True
    except Exception:  # noqa: BLE001 - any failure means unhealthy; details go to the log only
        log.exception("database health check failed")
        return "database", False


@contextlib.asynccontextmanager
async def _with_worker(_: FastAPI) -> AsyncIterator[None]:
    """Background services for the lifetime of the API process: outbox worker and optional SIP2 listener."""
    from app.worker import run_forever

    settings = get_settings()
    stop = asyncio.Event()
    task = asyncio.create_task(run_forever(stop))
    sip2 = None
    if settings.sip2_listener_enabled:
        from app.interop.sip2_server import start

        sip2 = await start(settings.sip2_host, settings.sip2_port, set(settings.sip2_allowed_hosts))
    try:
        yield
    finally:
        stop.set()
        await task
        if sip2 is not None:
            sip2.close()
            await sip2.wait_closed()


def create_app(check_db: bool = True) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        lifespan=_with_worker if check_db and settings.run_worker else None,
        title="Nexus API",
        version=settings.app_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.limiter = limiter
    app.state.health_checks = []
    if check_db:
        app.state.health_checks.append(lambda: _database_check(app))
        _database_check(app)
    install_error_handlers(app)
    app.state.licence_status = status_from_file(
        Path(settings.licence_file), settings.licence_key.get_secret_value()
    )
    if settings.environment not in DEV_ENVIRONMENTS and app.state.licence_status != "valid":
        log.warning("licence %s: the API is read-only for non-administrators", app.state.licence_status)
        app.add_middleware(ReadOnlyUntilLicensed, status=app.state.licence_status)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(_: Request, __: RateLimitExceeded) -> JSONResponse:
        return JSONResponse({"error": "Too many requests", "code": "ERR_RATE_LIMIT"}, status_code=429)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(opac.router, prefix="/api/v1")
    app.include_router(members.router, prefix="/api/v1")
    app.include_router(circulation.router, prefix="/api/v1")
    app.include_router(fines.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(tags.router, prefix="/api/v1")
    app.include_router(inventory.router, prefix="/api/v1")
    app.include_router(gate.router, prefix="/api/v1")
    app.include_router(migration.router, prefix="/api/v1")
    app.include_router(ncip.router, prefix="/api/v1")
    app.include_router(ws.router, prefix="/api/v1")
    return app


app = create_app()
