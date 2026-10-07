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
    results = {name: ok for name, ok in (check() for check in request.app.state.health_checks)}
    return {"status": "ok" if all(results.values()) else "degraded", "checks": results}
