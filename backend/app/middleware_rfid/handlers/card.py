from sqlalchemy.orm import Session

from app.core.audit import audit
from app.db.models import Device, DeviceType
from app.integrations.registry import get_adapter
from app.middleware_rfid.dispatcher import dispatcher
from app.middleware_rfid.live_hub import hub
from app.middleware_rfid.schemas import DeviceEventIn
from app.services.smartcard import challenges


def handle_card_tap(session: Session, device: Device, event: DeviceEventIn) -> dict | None:
    if device.device_type != DeviceType.smartcard_reader:
        return None
    uid = str(event.payload.get("card_uid", ""))
    identity = get_adapter("credentials", session).resolve(uid) if uid else None
    challenge_id = challenges.bind(device.code, identity)
    if challenge_id:
        hub.publish(
            "auth.card",
            {"reader_code": device.code, "challenge_id": challenge_id, "ok": identity is not None},
        )
    # The card UID is never written to the audit log.
    audit(
        session,
        actor_type="device",
        actor_id=identity.user_id if identity else None,
        action="auth.card.tap",
        entity_type="session",
        details={"reader": device.code, "known": identity is not None, "challenge": challenge_id is not None},
    )
    return {"known": identity is not None, "challenge": challenge_id is not None}


dispatcher.register("CardTapped", handle_card_tap)
