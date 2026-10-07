from fastapi import APIRouter, Depends

from app.core.auth import Principal, require
from app.core.errors import AppError

router = APIRouter(prefix="/migration", tags=["migration"])


@router.post("/batches")
def upload_batch(_: Principal = Depends(require("migration.run"))) -> None:
    # Placeholder until the migration engine lands (Stage 6); access control is already enforced.
    raise AppError("NOT_IMPLEMENTED", "Migration upload is not available yet", 501)
