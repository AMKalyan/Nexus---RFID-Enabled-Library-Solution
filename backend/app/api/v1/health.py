from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(tags=["operations"])
BUILD_NOTES = "1.0.2: security and robustness fixes (DEF-015 to DEF-024); see RELEASE-NOTES.md."


@router.get("/version")
def version(request: Request) -> dict:
    return {
        "version": get_settings().app_version,
        "alembic_rev": getattr(request.app.state, "alembic_rev", None),
        "licence": getattr(request.app.state, "licence_status", "unchecked"),
        "build_notes": BUILD_NOTES,
    }


@router.get("/health")
def health(request: Request) -> JSONResponse:
    """200 when every check passes, 503 otherwise: Docker and the update roll-back read the status code."""
    results = {name: ok for name, ok in (check() for check in request.app.state.health_checks)}
    healthy = all(results.values())
    body = {"status": "ok" if healthy else "degraded", "checks": results}
    return JSONResponse(body, status_code=200 if healthy else 503)
