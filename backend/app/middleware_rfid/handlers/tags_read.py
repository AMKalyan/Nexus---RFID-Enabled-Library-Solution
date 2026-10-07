"""Staff-station reads: tell the tagging and circulation screens which tags the desk reader sees."""

from sqlalchemy.orm import Session

from app.db.models import Device, DeviceType
from app.middleware_rfid.dispatcher import dispatcher
from app.middleware_rfid.live_hub import hub
from app.middleware_rfid.schemas import DeviceEventIn
from app.services.tagging import TaggingService


def handle_staff_read(session: Session, device: Device, event: DeviceEventIn) -> dict | None:
    if device.device_type != DeviceType.staff_station or event.payload.get("session_id"):
        return None
    reads = TaggingService(session).resolve(event.epcs)
    hub.publish("tag.read", {"device": device.code, "reads": reads})
    return {
        "resolved": sum(1 for r in reads if not r.get("unknown")),
        "unknown": sum(1 for r in reads if r.get("unknown")),
    }


dispatcher.register("TagsRead", handle_staff_read)
