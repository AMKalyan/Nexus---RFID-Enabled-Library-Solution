"""Tag association, re-tagging and monitoring (FR 05, AC 02)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import AppError
from app.db.models import Item, ItemStatus, Member, MemberStatus, RfidTag, TagStatus, TagTarget
from app.services.catalog import CatalogService
from app.services.common import Actor

# Problems that stop tagging. Others reported by validate_item (e.g. no shelf) are warnings only.
BLOCKING = {"ITEM_WITHDRAWN", "TITLE_MISSING"}


class TaggingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog = CatalogService(session)

    def get(self, epc: str) -> RfidTag:
        tag = self.session.scalar(select(RfidTag).where(RfidTag.epc == epc.upper()))
        if tag is None:
            raise AppError("TAG_NOT_FOUND", "Tag not found", 404)
        return tag

    def _validate_target(
        self, target_type: TagTarget, target_id: uuid.UUID
    ) -> tuple[Item | None, Member | None]:
        if target_type == TagTarget.item:
            item = self.catalog.get_item(target_id)
            problems = BLOCKING.intersection(self.catalog.validate_item(item.id))
            if problems:
                raise AppError(
                    "TAG_TARGET_INVALID", f"Item cannot be tagged: {', '.join(sorted(problems))}", 422
                )
            return item, None
        member = self.session.get(Member, target_id)
        if member is None:
            raise AppError("MEMBER_NOT_FOUND", "Member not found", 404)
        if member.status == MemberStatus.expired:
            raise AppError("TAG_TARGET_INVALID", "Member cannot be tagged: MEMBER_EXPIRED", 422)
        return None, member

    def associate(self, epc: str, target_type: TagTarget, target_id: uuid.UUID, actor: Actor) -> RfidTag:
        epc = epc.upper()
        item, member = self._validate_target(target_type, target_id)
        existing = self.session.scalar(select(RfidTag).where(RfidTag.epc == epc))
        if existing is not None:
            code = "TAG_IN_USE" if existing.status == TagStatus.active else "TAG_RETIRED"
            raise AppError(code, "This tag is already registered", 409)

        current = self.session.scalar(
            select(RfidTag).where(
                RfidTag.status == TagStatus.active,
                (RfidTag.item_id == target_id) if item else (RfidTag.member_id == target_id),
            )
        )
        if current is not None:
            self._retire(current, "retagged", actor)

        tag = RfidTag(
            epc=epc,
            target_type=target_type,
            item_id=item.id if item else None,
            member_id=member.id if member else None,
            # Security bit on means "not checked out": the gate alarms for it.
            security_bit=bool(item and item.status != ItemStatus.on_loan),
            encoded_by=actor.id,
        )
        self.session.add(tag)
        self.session.flush()
        target_ref = item.accession_no if item else member.card_no if member else None
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="tag.associate",
            entity_type="rfid_tag",
            entity_id=epc,
            details={
                "target_type": target_type.value,
                "target": target_ref,
                "replaced": current.epc if current else None,
            },
            ip=actor.ip,
        )
        return tag

    def _retire(self, tag: RfidTag, reason: str, actor: Actor) -> None:
        tag.status, tag.retired_at, tag.retire_reason = TagStatus.retired, datetime.now(UTC), reason
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="tag.retire",
            entity_type="rfid_tag",
            entity_id=tag.epc,
            details={"reason": reason},
            ip=actor.ip,
        )

    def retire(self, epc: str, reason: str, actor: Actor) -> RfidTag:
        tag = self.get(epc)
        if tag.status != TagStatus.active:
            raise AppError("TAG_RETIRED", "Tag is already retired", 409)
        self._retire(tag, reason, actor)
        return tag

    def list_tags(self, status: TagStatus | None, limit: int = 200) -> list[RfidTag]:
        query = select(RfidTag).order_by(RfidTag.encoded_at.desc()).limit(limit)
        if status:
            query = query.where(RfidTag.status == status)
        return list(self.session.scalars(query))

    def resolve(self, epcs: list[str]) -> list[dict]:
        """Describe what each EPC is attached to (used by readers and the tagging screen)."""
        rows = self.session.execute(
            select(RfidTag, Item)
            .outerjoin(Item, Item.id == RfidTag.item_id)
            .where(RfidTag.epc.in_(epcs), RfidTag.status == TagStatus.active)
        ).all()
        found = {tag.epc: (tag, item) for tag, item in rows}
        out = []
        for epc in epcs:
            if epc not in found:
                out.append({"epc": epc, "unknown": True})
                continue
            tag, item = found[epc]
            out.append(
                {
                    "epc": epc,
                    "target_type": tag.target_type.value,
                    "item_id": str(item.id) if item else None,
                    "accession_no": item.accession_no if item else None,
                    "title": item.bib.title if item else None,
                    "status": item.status.value if item else None,
                    "security_bit": tag.security_bit,
                }
            )
        return out
