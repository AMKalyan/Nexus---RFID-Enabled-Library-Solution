import asyncio
import contextlib

from fastapi import APIRouter, Depends, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.auth import Principal, require
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import limiter
from app.db.base import get_session
from app.db.models import Device
from app.middleware_rfid.commands import bus
from app.middleware_rfid.device_auth import authenticate_device, hash_key, new_device_key
from app.middleware_rfid.ingest import device_status, ingest
from app.middleware_rfid.schemas import CommandAckIn, DeviceCreatedOut, DeviceEventIn, DeviceIn, DeviceOut
from app.services.common import Actor

router = APIRouter(prefix="/devices", tags=["rfid middleware"])


def device_out(device: Device) -> DeviceOut:
    return DeviceOut(
        code=device.code,
        device_type=device.device_type,
        name=device.name,
        location=device.location,
        ip_address=str(device.ip_address) if device.ip_address else None,
        config=device.config or {},
        status=device_status(device),
        last_heartbeat_at=device.last_heartbeat_at,
    )


@router.post(
    "/{code}/events", responses={202: {"description": "accepted"}, 200: {"description": "duplicate"}}
)
@limiter.limit(get_settings().rate_limit_devices)
def post_event(
    request: Request,
    code: str,
    body: DeviceEventIn,
    x_device_key: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> JSONResponse:
    device = authenticate_device(session, code, x_device_key)
    status, result = ingest(session, device, body)
    session.commit()
    return JSONResponse(
        {"status": status, "result": result}, status_code=202 if status == "accepted" else 200
    )


@router.get("/{code}/commands")
def poll_commands(
    code: str, x_device_key: str | None = Header(default=None), session: Session = Depends(get_session)
):
    """For devices without a socket: fetch queued commands."""
    authenticate_device(session, code, x_device_key)
    return [{"command_id": c.command_id, "command": c.command, "params": c.params} for c in bus.poll(code)]


@router.post("/{code}/commands/ack")
def ack_command(
    code: str,
    body: CommandAckIn,
    x_device_key: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    authenticate_device(session, code, x_device_key)
    return {"acknowledged": bus.ack(body.command_id, body.response)}


@router.websocket("/{code}/ws")
async def device_socket(websocket: WebSocket, code: str, session: Session = Depends(get_session)) -> None:
    """Push commands to a connected device and receive acknowledgements."""
    try:
        authenticate_device(session, code, websocket.headers.get("x-device-key"))
    except AppError:
        await websocket.close(code=4401)
        return
    await websocket.accept()

    async def push() -> None:
        while True:
            cmd = await bus.next_for(code)
            await websocket.send_json(
                {"command_id": cmd.command_id, "command": cmd.command, "params": cmd.params}
            )

    sender = asyncio.create_task(push())
    try:
        while True:
            message = await websocket.receive_json()
            if isinstance(message, dict) and "command_id" in message:
                bus.ack(str(message["command_id"]), message.get("response") or {})
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender


# --- registry (FR 11, NFR 08 device configuration) ---------------------------------------------------


@router.get("", response_model=list[DeviceOut])
def list_devices(session: Session = Depends(get_session), _: Principal = Depends(require("devices.read"))):
    return [device_out(d) for d in session.scalars(select(Device).order_by(Device.code))]


@router.post("", response_model=DeviceCreatedOut, status_code=201)
def register_device(
    body: DeviceIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("admin.devices.write")),
) -> DeviceCreatedOut:
    if session.get(Device, body.code):
        raise AppError("DEVICE_EXISTS", "Device code already registered", 409)
    key = new_device_key()
    device = Device(**body.model_dump(), api_key_hash=hash_key(key))
    session.add(device)
    session.flush()
    actor = Actor.from_principal(p, request)
    audit(
        session,
        actor_type=actor.type,
        actor_id=actor.id,
        action="device.register",
        entity_type="device",
        entity_id=device.code,
        details={"device_type": body.device_type.value},
        ip=actor.ip,
    )
    session.commit()
    # The key is shown once; only its hash is stored.
    return DeviceCreatedOut(**device_out(device).model_dump(), api_key=key)


@router.post("/{code}/rotate-key", response_model=DeviceCreatedOut)
def rotate_key(
    code: str,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("admin.devices.write")),
) -> DeviceCreatedOut:
    device = session.get(Device, code)
    if device is None:
        raise AppError("DEVICE_NOT_FOUND", "Device not found", 404)
    key = new_device_key()
    device.api_key_hash = hash_key(key)
    actor = Actor.from_principal(p, request)
    audit(
        session,
        actor_type=actor.type,
        actor_id=actor.id,
        action="device.rotate_key",
        entity_type="device",
        entity_id=code,
        ip=actor.ip,
    )
    session.commit()
    return DeviceCreatedOut(**device_out(device).model_dump(), api_key=key)
