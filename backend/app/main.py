import logging

from alembic.runtime.migration import MigrationContext
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.api.v1 import admin, auth, catalog, circulation, fines, health, members, opac
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.ratelimit import limiter
from app.db.base import engine

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


def create_app(check_db: bool = True) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
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
    return app


app = create_app()
