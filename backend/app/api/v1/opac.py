from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.schemas.catalog import OpacPage, ShelfSpine
from app.services.search import SearchService

# Public catalogue: no authentication, and responses carry bibliographic data only.
router = APIRouter(prefix="/opac", tags=["opac"])


@router.get("/search", response_model=OpacPage)
def search(
    q: str | None = Query(default=None, max_length=200),
    author: str | None = Query(default=None, max_length=100),
    year_from: int | None = Query(default=None, ge=1000, le=2100),
    year_to: int | None = Query(default=None, ge=1000, le=2100),
    available: bool | None = None,
    page: int = Query(default=1, ge=1, le=1000),
    size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> OpacPage:
    return SearchService(session).search(q, page, size, author, year_from, year_to, available)


@router.get("/shelves/{shelf_code}", response_model=list[ShelfSpine])
def shelf(shelf_code: str, session: Session = Depends(get_session)) -> list[ShelfSpine]:
    return SearchService(session).virtual_shelf(shelf_code)
