import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Device, DeviceEvent
from app.middleware_rfid.dispatcher import dispatcher
from app.middleware_rfid.schemas import DeviceEventIn

log = logging.getLogger("nexus.devices")
OFFLINE_AFTER = timedelta(seconds=30)


def device_status(device: Device, now: datetime | None = None) -> Literal["online", "offline"]:
    seen = device.last_heartbeat_at
    return "online" if seen and (now or datetime.now(UTC)) - seen <= OFFLINE_AFTER else "offline"


def ingest(session: Session, device: Device, event: DeviceEventIn) -> tuple[str, dict[str, Any] | None]:
    """Store and dispatch one device event. A repeated event_id is acknowledged but not processed again."""
    if event.device_type != device.device_type:
        raise AppError("DEVICE_TYPE_MISMATCH", "Event device type does not match the registered device", 422)
    record = DeviceEvent(
        event_id=event.event_id,
        device_code=device.code,
        event_type=event.type,
        payload={**event.payload, "epcs": event.epcs},
        occurred_at=event.occurred_at,
    )
    try:
        with session.begin_nested():
            session.add(record)
            session.flush()
    except IntegrityError:
        return "duplicate", None

    device.last_heartbeat_at = datetime.now(UTC)
    try:
        result = dispatcher.dispatch(session, device, event)
    except AppError as exc:
        # The event is kept; the failure is recorded on it for diagnostics.
        log.warning("device event %s rejected by handler: %s", event.event_id, exc.code)
        result = {"error": exc.code}
    record.processed_at = datetime.now(UTC)
    record.result = result
    session.flush()
    return "accepted", result
