"""Security gate events (FR 07, AC 06).

The gate decides locally from each tag's security bit (on = not checked out), so it keeps working when
Nexus is unreachable. Nexus records every passage, confirms the decision against loans, attaches a camera
snapshot to alarms and queues the alert notification.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.db.models import Device, Footfall, GateEvent, Item, Loan, RfidTag, TagStatus
from app.integrations.registry import get_adapter
from app.middleware_rfid.live_hub import hub
from app.middleware_rfid.schemas import DeviceEventIn
from app.services.notifications import NotificationsService

log = logging.getLogger("nexus.gate")


class GateService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def handle_passage(self, device: Device, event: DeviceEventIn) -> list[GateEvent]:
        direction = str(event.payload.get("direction", "out"))
        offline = bool(event.payload.get("offline_decision", False))
        return [self._one(device, event, epc, direction, offline) for epc in event.epcs]

    def _one(
        self, device: Device, event: DeviceEventIn, epc: str, direction: str, offline: bool
    ) -> GateEvent:
        tag = self.session.scalar(
            select(RfidTag).where(RfidTag.epc == epc, RfidTag.status == TagStatus.active)
        )
        item = self.session.get(Item, tag.item_id) if tag and tag.item_id else None
        on_loan = (
            item is not None
            and self.session.scalar(
                select(Loan.id).where(Loan.item_id == item.id, Loan.returned_at.is_(None))
            )
            is not None
        )
        authorised = on_loan or (tag is not None and tag.member_id is not None)  # member cards may pass
        alarm = direction == "out" and not authorised
        record = GateEvent(
            device_code=device.code,
            event_id=event.event_id,
            epc=epc,
            item_id=item.id if item else None,
            accession_no=item.accession_no if item else None,
            direction=direction,
            authorised=authorised,
            alarm=alarm,
            offline_decision=offline,
            occurred_at=event.occurred_at,
        )
        self.session.add(record)
        self.session.flush()
        if alarm:
            self._raise_alarm(device, record, item)
        return record

    def _raise_alarm(self, device: Device, record: GateEvent, item: Item | None) -> None:
        title = item.bib.title if item else "Unknown tag"
        context = {
            "gate": device.code,
            "accession_no": record.accession_no,
            "epc": record.epc,
            "title": title,
            "time": record.occurred_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        camera_code = (device.config or {}).get("camera")
        if camera_code:
            try:
                record.photo_jpeg = get_adapter("camera").snapshot(camera_code, context)
            except Exception:  # noqa: BLE001 - a camera fault must not lose the alarm
                log.exception("camera snapshot failed for %s", camera_code)
        notifier = NotificationsService(self.session)
        notifier.queue(
            "email", "gate_alert", notifier.gate_recipients(), context, ("gate_event", str(record.id))
        )
        record.notified = True
        self.session.flush()
        hub.publish(
            "gate.alert",
            {
                "id": str(record.id),
                "gate": device.code,
                "accession_no": record.accession_no,
                "title": title,
                "epc": record.epc,
                "offline_decision": record.offline_decision,
                "occurred_at": record.occurred_at.isoformat(),
                "has_photo": record.photo_jpeg is not None,
            },
        )
        audit(
            self.session,
            actor_type="device",
            actor_id=None,
            action="gate.alarm",
            entity_type="gate_event",
            entity_id=str(record.id),
            details={
                "gate": device.code,
                "accession_no": record.accession_no,
                "offline_decision": record.offline_decision,
            },
        )

    def record_footfall(self, device: Device, event: DeviceEventIn) -> None:
        hour = event.occurred_at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        ins = int(event.payload.get("in_count", 0))
        outs = int(event.payload.get("out_count", 0))
        stmt = insert(Footfall).values(device_code=device.code, hour=hour, in_count=ins, out_count=outs)
        self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Footfall.device_code, Footfall.hour],
                set_={"in_count": Footfall.in_count + ins, "out_count": Footfall.out_count + outs},
            )
        )

    def events(
        self, *, alarm: bool | None, date_from: datetime | None, date_to: datetime | None, limit: int = 200
    ) -> list[GateEvent]:
        query = select(GateEvent).order_by(GateEvent.occurred_at.desc()).limit(limit)
        if alarm is not None:
            query = query.where(GateEvent.alarm.is_(alarm))
        if date_from:
            query = query.where(GateEvent.occurred_at >= date_from)
        if date_to:
            query = query.where(GateEvent.occurred_at <= date_to)
        return list(self.session.scalars(query))
