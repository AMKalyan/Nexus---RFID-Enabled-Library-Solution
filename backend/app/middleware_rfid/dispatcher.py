from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Device
from app.middleware_rfid.schemas import DeviceEventIn

Handler = Callable[[Session, Device, DeviceEventIn], dict[str, Any] | None]


class Dispatcher:
    """Routes each device event type to the handlers registered for it."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def register(self, event_type: str, handler: Handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def dispatch(self, session: Session, device: Device, event: DeviceEventIn) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for handler in self._handlers.get(event.type, []):
            result.update(handler(session, device, event) or {})
        return result


dispatcher = Dispatcher()
