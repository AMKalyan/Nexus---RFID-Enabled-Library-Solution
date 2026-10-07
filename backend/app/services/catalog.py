import uuid

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.audit import audit
from app.core.errors import AppError
from app.db.models import Bib, Item, ItemStatus, RecordSource, RfidTag, Shelf, TagStatus
from app.schemas.catalog import BibIn, BibPatch, ItemIn
from app.services.common import Actor
from app.services.validation import accession_is_valid, isbn_is_valid, normalise_isbn


class CatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- bibliographic records ---

    def _clean_isbn(self, isbn: str | None) -> str | None:
        if not isbn:
            return None
        if not isbn_is_valid(isbn):
            raise AppError("ISBN_INVALID", "ISBN checksum invalid", 422)
        return normalise_isbn(isbn)

    def get_bib(self, bib_id: uuid.UUID) -> Bib:
        bib = self.session.get(Bib, bib_id)
        if bib is None:
            raise AppError("BIB_NOT_FOUND", "Bibliographic record not found", 404)
        return bib

    def create_bib(self, data: BibIn, actor: Actor) -> Bib:
        values = data.model_dump()
        values["isbn"] = self._clean_isbn(data.isbn)
        bib = Bib(**values, source=RecordSource.nexus)
        self.session.add(bib)
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="bib.create",
            entity_type="bib",
            entity_id=str(bib.id),
            details={"title": bib.title},
            ip=actor.ip,
        )
        return bib

    def update_bib(self, bib_id: uuid.UUID, data: BibPatch, actor: Actor) -> Bib:
        bib = self.get_bib(bib_id)
        changes = data.model_dump(exclude_unset=True)
        if "isbn" in changes:
            changes["isbn"] = self._clean_isbn(changes["isbn"])
        for field, value in changes.items():
            setattr(bib, field, value)
        self.session.flush()
        self.session.refresh(bib)  # pick up the trigger-maintained search vector
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="bib.update",
            entity_type="bib",
            entity_id=str(bib.id),
            details={"fields": sorted(changes)},
            ip=actor.ip,
        )
        return bib

    def list_bibs(self, q: str | None, page: int, size: int) -> list[Bib]:
        query = select(Bib).order_by(Bib.title)
        if q:
            pattern = f"%{q}%"
            query = query.where(or_(Bib.title.ilike(pattern), Bib.author.ilike(pattern), Bib.isbn == q))
        return list(self.session.scalars(query.offset((page - 1) * size).limit(size)))

    # --- items ---

    def add_item(self, bib_id: uuid.UUID, data: ItemIn, actor: Actor) -> Item:
        bib = self.get_bib(bib_id)
        if data.shelf_code and self.session.get(Shelf, data.shelf_code) is None:
            raise AppError("SHELF_NOT_FOUND", "Shelf not found", 404)
        self._ensure_unique(data.accession_no, data.barcode)
        item = Item(bib_id=bib.id, **data.model_dump())
        try:
            with self.session.begin_nested():
                self.session.add(item)
                self.session.flush()
        except IntegrityError as exc:  # concurrent insert of the same identifiers
            self._raise_duplicate(str(exc.orig))
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="item.create",
            entity_type="item",
            entity_id=str(item.id),
            details={"accession_no": item.accession_no, "bib_id": str(bib.id)},
            ip=actor.ip,
        )
        return item

    def _ensure_unique(self, accession_no: str, barcode: str) -> None:
        if self.session.scalar(select(Item.id).where(Item.accession_no == accession_no)):
            raise AppError("ACCESSION_EXISTS", "Accession number already exists", 409)
        if self.session.scalar(select(Item.id).where(Item.barcode == barcode)):
            raise AppError("BARCODE_EXISTS", "Barcode already exists", 409)

    @staticmethod
    def _raise_duplicate(message: str) -> None:
        if "barcode" in message:
            raise AppError("BARCODE_EXISTS", "Barcode already exists", 409)
        raise AppError("ACCESSION_EXISTS", "Accession number already exists", 409)

    def get_item(self, item_id: uuid.UUID) -> Item:
        item = self.session.get(Item, item_id, options=[selectinload(Item.bib)])
        if item is None:
            raise AppError("ITEM_NOT_FOUND", "Item not found", 404)
        return item

    def find_items(
        self, accession_no: str | None = None, barcode: str | None = None, epc: str | None = None
    ) -> list[Item]:
        query = select(Item).options(selectinload(Item.bib)).order_by(Item.accession_no)
        if accession_no:
            query = query.where(Item.accession_no == accession_no)
        if barcode:
            query = query.where(Item.barcode == barcode)
        if epc:
            query = query.join(RfidTag, RfidTag.item_id == Item.id).where(
                RfidTag.epc == epc, RfidTag.status == TagStatus.active
            )
        return list(self.session.scalars(query.limit(50)))

    def get_item_by_ref(self, ref: str) -> Item:
        """Resolve an item from an accession number, barcode or active tag EPC."""
        tag_item = select(RfidTag.item_id).where(RfidTag.epc == ref, RfidTag.status == TagStatus.active)
        item = self.session.scalar(
            select(Item).where(or_(Item.accession_no == ref, Item.barcode == ref, Item.id.in_(tag_item)))
        )
        if item is None:
            raise AppError("ITEM_NOT_FOUND", "Item not found", 404)
        return item

    def tags_for(self, item_id: uuid.UUID) -> list[RfidTag]:
        return list(
            self.session.scalars(
                select(RfidTag).where(RfidTag.item_id == item_id).order_by(RfidTag.encoded_at)
            )
        )

    def validate_item(self, item_id: uuid.UUID) -> list[str]:
        """Checks performed before an item may be tagged or re-tagged (FR 05)."""
        item = self.get_item(item_id)
        problems: list[str] = []
        if item.status == ItemStatus.withdrawn:
            problems.append("ITEM_WITHDRAWN")
        if not (item.bib.title or "").strip():
            problems.append("TITLE_MISSING")
        if not accession_is_valid(item.accession_no):
            problems.append("ACCESSION_FORMAT")
        if not item.shelf_code:
            problems.append("NO_SHELF")
        return problems
