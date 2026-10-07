from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

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
        total_copies = func.count(Item.id)
        available_copies = func.coalesce(func.sum(cast(Item.status == ItemStatus.available, Integer)), 0)
        query = (
            select(Bib, total_copies.label("total"), available_copies.label("available"))
            .outerjoin(Item, (Item.bib_id == Bib.id) & (Item.status != ItemStatus.withdrawn))
            .group_by(Bib.id)
        )
        if q:
            tsq = func.websearch_to_tsquery("simple", q)
            query = query.where(Bib.search_tsv.op("@@")(tsq)).order_by(
                func.ts_rank(Bib.search_tsv, tsq).desc(), Bib.title
            )
        else:
            query = query.order_by(Bib.title)
        if author:
            query = query.where(Bib.author.ilike(f"%{author}%"))
        if year_from is not None:
            query = query.where(Bib.pub_year >= year_from)
        if year_to is not None:
            query = query.where(Bib.pub_year <= year_to)
        if available:
            query = query.having(available_copies > 0)

        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
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
