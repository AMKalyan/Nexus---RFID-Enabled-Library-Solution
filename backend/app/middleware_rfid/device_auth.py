import hashlib
import hmac
import secrets

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Device

# Compared against when the device code is unknown, so both paths cost the same.
_DUMMY = hashlib.sha256(b"no-such-device").hexdigest()


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_device_key() -> str:
    return secrets.token_urlsafe(24)


def authenticate_device(session: Session, code: str, key: str | None) -> Device:
    device = session.get(Device, code)
    expected = device.api_key_hash if device else _DUMMY
    if not key or not hmac.compare_digest(expected, hash_key(key)) or device is None:
        raise AppError("ERR_DEVICE_AUTH", "Device authentication failed", 401)
    return device
