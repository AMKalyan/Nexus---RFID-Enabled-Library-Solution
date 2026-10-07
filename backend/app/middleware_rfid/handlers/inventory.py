"""Handheld bulk reads during an inventory session: classify, confirm on the device, publish live."""

import uuid
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.db.models import Device, DeviceType
from app.middleware_rfid.commands import bus
from app.middleware_rfid.dispatcher import dispatcher
from app.middleware_rfid.live_hub import hub
from app.middleware_rfid.schemas import DeviceEventIn
from app.services.inventory import InventoryService

LIGHT_MS = 400


def handle_inventory_read(session: Session, device: Device, event: DeviceEventIn) -> dict | None:
    session_id = event.payload.get("session_id")
    if device.device_type != DeviceType.handheld or not session_id:
        return None
    outcomes = InventoryService(session).record_reads(uuid.UUID(str(session_id)), event.epcs)
    for outcome in outcomes:
        bus.enqueue(device.code, "Beep", {"pattern": outcome.beep})
        bus.enqueue(device.code, "Light", {"color": outcome.light, "ms": LIGHT_MS})
        hub.publish("inventory.read", {"session_id": str(session_id), **asdict(outcome)})
    return {"outcomes": [asdict(o) for o in outcomes]}


dispatcher.register("TagsRead", handle_inventory_read)
