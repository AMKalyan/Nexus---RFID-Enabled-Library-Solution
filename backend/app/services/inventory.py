"""Shelf inventory with a handheld reader (FR 06, AC 05)."""

import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import AppError
from app.db.models import (
    Bib,
    Device,
    DeviceType,
    InventoryRead,
    InventoryResult,
    InventorySession,
    Item,
    ItemStatus,
    RfidTag,
    Shelf,
    TagStatus,
)
from app.services.common import Actor

# Confirmation shown and played on the handheld and the inventory screen for each read.
CONFIRMATION = {
    InventoryResult.found: ("green", "ok"),
    InventoryResult.misplaced: ("amber", "warn"),
    InventoryResult.unknown: ("red", "error"),
}
# Items that are expected on their home shelf (on-loan and withdrawn items are not).
EXPECTED_STATUSES = (ItemStatus.available, ItemStatus.missing, ItemStatus.in_repair)


@dataclass
class ReadOutcome:
    epc: str
    result: str
    item_id: str | None
    accession_no: str | None
    title: str | None
    home_shelf: str | None
    light: str
    beep: str


class InventoryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _get(self, session_id: uuid.UUID) -> InventorySession:
        inv = self.session.get(InventorySession, session_id)
        if inv is None:
            raise AppError("INVENTORY_NOT_FOUND", "Inventory session not found", 404)
        return inv

    def _expected(self, shelf_code: str):  # noqa: ANN202
        return (
            select(RfidTag.epc, Item.id, Item.accession_no, Bib.title)
            .join(Item, Item.id == RfidTag.item_id)
            .join(Bib, Bib.id == Item.bib_id)
            .where(
                Item.shelf_code == shelf_code,
                Item.status.in_(EXPECTED_STATUSES),
                RfidTag.status == TagStatus.active,
            )
        )

    def start(self, shelf_code: str, device_code: str, actor: Actor) -> InventorySession:
        device = self.session.get(Device, device_code)
        if device is None or device.device_type != DeviceType.handheld:
            raise AppError("DEVICE_NOT_HANDHELD", "Inventory needs a registered handheld reader", 422)
        if self.session.get(Shelf, shelf_code) is None:
            raise AppError("SHELF_NOT_FOUND", "Shelf not found", 404)
        inv = InventorySession(shelf_code=shelf_code, device_code=device_code, started_by=actor.id)
        self.session.add(inv)
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="inventory.start",
            entity_type="inventory_session",
            entity_id=str(inv.id),
            details={"shelf": shelf_code},
            ip=actor.ip,
        )
        return inv

    def expected_count(self, shelf_code: str) -> int:
        return (
            self.session.scalar(select(func.count()).select_from(self._expected(shelf_code).subquery())) or 0
        )

    def record_reads(self, session_id: uuid.UUID, epcs: list[str]) -> list[ReadOutcome]:
        inv = self._get(session_id)
        if inv.status != "open":
            raise AppError("INVENTORY_CLOSED", "Inventory session is closed", 409)
        already = set(
            self.session.scalars(select(InventoryRead.epc).where(InventoryRead.session_id == inv.id))
        )
        rows = self.session.execute(
            select(RfidTag.epc, Item.id, Item.accession_no, Item.shelf_code, Bib.title)
            .join(Item, Item.id == RfidTag.item_id)
            .join(Bib, Bib.id == Item.bib_id)
            .where(RfidTag.epc.in_(epcs), RfidTag.status == TagStatus.active)
        ).all()
        known = {r.epc: r for r in rows}
        outcomes = []
        for epc in dict.fromkeys(epcs):  # de-duplicate within one sweep, keep order
            if epc in already:
                continue
            row = known.get(epc)
            if row is None:
                result = InventoryResult.unknown
            elif row.shelf_code == inv.shelf_code:
                result = InventoryResult.found
            else:
                result = InventoryResult.misplaced
            self.session.add(
                InventoryRead(session_id=inv.id, epc=epc, item_id=row.id if row else None, result=result)
            )
            light, beep = CONFIRMATION[result]
            outcomes.append(
                ReadOutcome(
                    epc=epc,
                    result=result.value,
                    item_id=str(row.id) if row else None,
                    accession_no=row.accession_no if row else None,
                    title=row.title if row else None,
                    home_shelf=row.shelf_code if row else None,
                    light=light,
                    beep=beep,
                )
            )
        self.session.flush()
        return outcomes

    def reads(self, session_id: uuid.UUID) -> list[dict]:
        rows = self.session.execute(
            select(InventoryRead, Item.accession_no, Item.shelf_code, Bib.title)
            .outerjoin(Item, Item.id == InventoryRead.item_id)
            .outerjoin(Bib, Bib.id == Item.bib_id)
            .where(InventoryRead.session_id == session_id)
            .order_by(InventoryRead.read_at)
        ).all()
        out = []
        for read, accession_no, shelf_code, title in rows:
            light, beep = CONFIRMATION[read.result]
            out.append(
                asdict(
                    ReadOutcome(
                        epc=read.epc,
                        result=read.result.value,
                        item_id=str(read.item_id) if read.item_id else None,
                        accession_no=accession_no,
                        title=title,
                        home_shelf=shelf_code,
                        light=light,
                        beep=beep,
                    )
                )
            )
        return out

    def missing(self, inv: InventorySession) -> list[dict]:
        read = select(InventoryRead.epc).where(InventoryRead.session_id == inv.id)
        rows = self.session.execute(self._expected(inv.shelf_code).where(RfidTag.epc.not_in(read))).all()
        return [
            {
                "epc": epc,
                "item_id": str(item_id),
                "accession_no": acc,
                "title": title,
                "light": "red",
                "beep": "error",
            }
            for epc, item_id, acc, title in rows
        ]

    def summary(self, session_id: uuid.UUID) -> dict:
        inv = self._get(session_id)
        return {
            "id": str(inv.id),
            "shelf_code": inv.shelf_code,
            "device_code": inv.device_code,
            "status": inv.status,
            "started_at": inv.started_at,
            "closed_at": inv.closed_at,
            "expected": self.expected_count(inv.shelf_code),
            "reads": self.reads(inv.id),
        }

    def close(self, session_id: uuid.UUID, actor: Actor) -> dict:
        inv = self._get(session_id)
        if inv.status == "open":
            inv.status, inv.closed_at = "closed", datetime.now(UTC)
        reads = self.reads(inv.id)
        report = {
            "id": str(inv.id),
            "shelf_code": inv.shelf_code,
            "found": [r for r in reads if r["result"] == "found"],
            "misplaced": [r for r in reads if r["result"] == "misplaced"],
            "unknown": [r for r in reads if r["result"] == "unknown"],
            "missing": self.missing(inv),
        }
        self.session.flush()
        counts = {k: len(v) for k, v in report.items() if isinstance(v, list)}
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="inventory.close",
            entity_type="inventory_session",
            entity_id=str(inv.id),
            details=counts,
            ip=actor.ip,
        )
        return report

    def mark_missing(self, session_id: uuid.UUID, actor: Actor) -> int:
        """A librarian confirms the missing list; only then do item statuses change."""
        inv = self._get(session_id)
        if inv.status != "closed":
            raise AppError("INVENTORY_OPEN", "Close the session before marking items missing", 409)
        ids = [uuid.UUID(m["item_id"]) for m in self.missing(inv)]
        for item in self.session.scalars(select(Item).where(Item.id.in_(ids))):
            item.status = ItemStatus.missing
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="inventory.mark_missing",
            entity_type="inventory_session",
            entity_id=str(inv.id),
            details={"items": len(ids)},
            ip=actor.ip,
        )
        return len(ids)
