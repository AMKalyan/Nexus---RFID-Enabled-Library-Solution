from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import AppError
from app.db.models import Bib, Item, ItemStatus, Shelf
from app.schemas.catalog import OpacHit, OpacPage, ShelfSpine


class SearchService:
    """OPAC search over the trigger-maintained full-text vector (FR 02)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(
        self,
        q: str | None,
        page: int,
        size: int,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        available: bool | None = None,
    ) -> OpacPage:
        # Filter bibs first. Copy counts are correlated per bib (bib_id index), so they are computed only
        # for the page being returned, not for every item in the catalogue.
        filters: list[ColumnElement[bool]] = []
        order_by: list[ColumnElement[Any] | InstrumentedAttribute[Any]] = [Bib.title]
        if q:
            tsq = func.websearch_to_tsquery("simple", q)
            filters.append(Bib.search_tsv.op("@@")(tsq))
            order_by = [func.ts_rank(Bib.search_tsv, tsq).desc(), Bib.title]
        if author:
            filters.append(Bib.author.ilike(f"%{author}%"))
        if year_from is not None:
            filters.append(Bib.pub_year >= year_from)
        if year_to is not None:
            filters.append(Bib.pub_year <= year_to)
        is_available = (Item.bib_id == Bib.id) & (Item.status == ItemStatus.available)
        if available:
            filters.append(exists().where(is_available))

        total_copies = (
            select(func.count(Item.id))
            .where(Item.bib_id == Bib.id, Item.status != ItemStatus.withdrawn)
            .scalar_subquery()
        )
        available_copies = select(func.count(Item.id)).where(is_available).scalar_subquery()
        query = select(Bib, total_copies, available_copies).where(*filters).order_by(*order_by)

        total = self.session.scalar(select(func.count(Bib.id)).where(*filters)) or 0
        rows = self.session.execute(query.offset((page - 1) * size).limit(size)).all()
        items = [
            OpacHit(
                id=bib.id,
                title=bib.title,
                author=bib.author,
                publisher=bib.publisher,
                pub_year=bib.pub_year,
                isbn=bib.isbn,
                total_copies=tot,
                available_copies=avail,
            )
            for bib, tot, avail in rows
        ]
        return OpacPage(total=total, page=page, size=size, items=items)

    def virtual_shelf(self, shelf_code: str) -> list[ShelfSpine]:
        if self.session.get(Shelf, shelf_code) is None:
            raise AppError("SHELF_NOT_FOUND", "Shelf not found", 404)
        rows = self.session.execute(
            select(Item, Bib)
            .join(Bib, Bib.id == Item.bib_id)
            .where(Item.shelf_code == shelf_code, Item.status != ItemStatus.withdrawn)
            .order_by(Item.call_no, Item.accession_no)
            .limit(500)
        ).all()
        return [
            ShelfSpine(
                item_id=i.id,
                accession_no=i.accession_no,
                call_no=i.call_no,
                title=b.title,
                author=b.author,
                status=i.status,
            )
            for i, b in rows
        ]
