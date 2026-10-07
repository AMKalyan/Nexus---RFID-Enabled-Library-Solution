import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.auth import Principal, require
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.db.base import get_session
from app.services.common import Actor
from app.services.migration.service import MigrationService

router = APIRouter(prefix="/migration", tags=["migration"])


class BatchOut(BaseModel):
    id: uuid.UUID
    source_file: str
    source_sha256: str
    status: str
    rows_total: int
    rows_valid: int
    rows_rejected: int
    rows_duplicate: int
    rows_committed: int
    created_at: datetime
    committed_at: datetime | None


def batch_out(b) -> BatchOut:  # noqa: ANN001
    return BatchOut(
        id=b.id,
        source_file=b.source_file,
        source_sha256=b.source_sha256,
        status=b.status.value,
        rows_total=b.rows_total,
        rows_valid=b.rows_valid,
        rows_rejected=b.rows_rejected,
        rows_duplicate=b.rows_duplicate,
        rows_committed=b.rows_committed,
        created_at=b.created_at,
        committed_at=b.committed_at,
    )


@router.get("/batches", response_model=list[BatchOut])
def list_batches(session: Session = Depends(get_session), _: Principal = Depends(require("migration.run"))):
    return [batch_out(b) for b in MigrationService(session).list_batches()]


@router.post("/batches", response_model=BatchOut, status_code=201)
@limiter.limit(get_settings().rate_limit_migration)
async def upload_batch(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    p: Principal = Depends(require("migration.run")),
) -> BatchOut:
    limit = get_settings().upload_max_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise AppError("UPLOAD_TOO_LARGE", f"Files are limited to {get_settings().upload_max_mb} MB", 413)

    def stage() -> BatchOut:
        batch = MigrationService(session).stage(
            content, file.filename or "upload", Actor.from_principal(p, request)
        )
        session.commit()
        return batch_out(batch)

    return await run_in_threadpool(stage)


@router.post("/batches/{batch_id}/validate")
def validate_batch(
    batch_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("migration.run")),
) -> dict:
    report = MigrationService(session).validate(batch_id, Actor.from_principal(p, request))
    session.commit()
    return asdict(report)


@router.get("/batches/{batch_id}/report")
def batch_report(
    batch_id: uuid.UUID,
    format: Literal["json", "csv"] = "json",
    session: Session = Depends(get_session),
    _: Principal = Depends(require("migration.run")),
):
    service = MigrationService(session)
    if format == "csv":
        return Response(
            service.report_csv(batch_id),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="migration-{batch_id}.csv"'},
        )
    return asdict(service.report(batch_id))


@router.post("/batches/{batch_id}/commit")
def commit_batch(
    batch_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("migration.run")),
) -> dict:
    report = MigrationService(session).commit(batch_id, Actor.from_principal(p, request))
    session.commit()
    return asdict(report)


@router.post("/batches/{batch_id}/rollback")
def rollback_batch(
    batch_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("migration.run")),
) -> dict:
    report = MigrationService(session).rollback(batch_id, Actor.from_principal(p, request))
    session.commit()
    return asdict(report)
