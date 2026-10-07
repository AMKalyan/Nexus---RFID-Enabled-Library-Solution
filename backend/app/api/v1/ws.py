from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.auth import principal_from_token
from app.core.errors import AppError
from app.db.base import get_session
from app.middleware_rfid.live_hub import hub

router = APIRouter(tags=["live"])

# Topic -> permission needed to receive it.
TOPIC_PERMISSIONS = {
    "gate.alert": "gate.read",
    "inventory.read": "inventory.read",
    "device.status": "devices.read",
    "tag.read": "tagging.write",
}


@router.websocket("/ws/live")
async def live(websocket: WebSocket, session: Session = Depends(get_session)) -> None:
    """Authenticated live feed. Browsers cannot set headers on WebSockets, so the token is a query parameter
    that is never logged; it is a short-lived access token."""
    try:
        permissions = principal_from_token(session, websocket.query_params.get("token", "")).permissions
    except AppError:
        await websocket.close(code=4401)
        return
    requested = set(filter(None, websocket.query_params.get("topics", "").split(","))) or set(
        TOPIC_PERMISSIONS
    )
    topics = {t for t in requested if TOPIC_PERMISSIONS.get(t) in permissions}
    await websocket.accept()
    sub = hub.subscribe(topics)
    try:
        while True:
            await websocket.send_json(await sub.queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(sub)
