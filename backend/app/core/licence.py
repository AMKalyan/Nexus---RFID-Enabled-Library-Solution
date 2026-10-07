"""Offline activation by a signed licence file (FR 12), in the format ops/licence.py issues.

Outside development an installation without a valid licence is read-only for everyone except administrators,
who can still sign in and activate it.
"""

import hashlib
import hmac
import json
from datetime import date
from pathlib import Path

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.security import decode_access_token

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ALWAYS_ALLOWED = ("/api/v1/auth/",)


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign(payload: dict, key: str) -> str:
    return hmac.new(key.encode(), canonical(payload), hashlib.sha256).hexdigest()


def check(licence: dict, key: str, today: date | None = None) -> str:
    """'valid', or why the licence is not valid: 'invalid' or 'expired'."""
    sig = licence.get("sig", "")
    payload = {k: v for k, v in licence.items() if k != "sig"}
    if not isinstance(sig, str) or not hmac.compare_digest(sig, sign(payload, key)):
        return "invalid"
    try:
        expires = date.fromisoformat(str(payload["expires"]))
    except (KeyError, ValueError):
        return "invalid"
    return "valid" if expires >= (today or date.today()) else "expired"


def status_from_file(path: Path, key: str) -> str:
    """'valid', 'missing', 'invalid' or 'expired'."""
    if not path.is_file():
        return "missing"
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "invalid"
    return check(content, key) if isinstance(content, dict) else "invalid"


class ReadOnlyUntilLicensed:
    """Installed only when the licence is not valid: refuses changes except by administrators."""

    def __init__(self, app: ASGIApp, status: str) -> None:
        self.app = app
        self.status = status

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS or self._allowed(scope):
            await self.app(scope, receive, send)
            return
        body = json.dumps(
            {
                "error": "This installation is not activated: install a licence file and restart the API "
                "(see the installation guide). Until then it is read-only.",
                "code": "LICENCE_REQUIRED",
                "licence": self.status,
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    def _allowed(scope: Scope) -> bool:
        if scope["path"].startswith(ALWAYS_ALLOWED):
            return True
        auth = dict(scope.get("headers") or []).get(b"authorization", b"").decode("latin-1")
        if not auth.lower().startswith("bearer "):
            return False
        try:
            return decode_access_token(auth[7:]).get("role") == "Admin"
        except Exception:  # noqa: BLE001 - an unreadable token is simply not an administrator
            return False
