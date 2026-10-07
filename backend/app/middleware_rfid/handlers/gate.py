from sqlalchemy.orm import Session

from app.db.models import Device
from app.middleware_rfid.dispatcher import dispatcher
from app.middleware_rfid.schemas import DeviceEventIn
from app.services.gate import GateService


def handle_passage(session: Session, device: Device, event: DeviceEventIn) -> dict:
    records = GateService(session).handle_passage(device, event)
    return {"alarms": sum(1 for r in records if r.alarm), "passages": len(records)}


def handle_footfall(session: Session, device: Device, event: DeviceEventIn) -> dict:
    GateService(session).record_footfall(device, event)
    return {"footfall": True}


dispatcher.register("GatePassage", handle_passage)
dispatcher.register("Footfall", handle_footfall)
