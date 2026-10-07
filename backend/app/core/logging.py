import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

_EMAIL = re.compile(r"\b([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
_PHONE = re.compile(r"\+?\d[\d\- ]{7,}(\d{2})\b")
PII_KEYS = {"email", "phone", "full_name", "name", "card_uid", "smartcard_uid", "recipient", "password"}


def mask_pii(text: str) -> str:
    """Mask email addresses and phone numbers in free text."""
    text = _EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)
    return _PHONE.sub(lambda m: "***" + m.group(1), text)


def mask_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Mask values whose key is known to hold personal data."""
    return {k: ("***" if k in PII_KEYS and v else v) for k, v in data.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": mask_pii(record.getMessage()),
        }
        ctx = getattr(record, "ctx", None)
        if isinstance(ctx, dict):
            payload["ctx"] = mask_mapping(ctx)
        if record.exc_info:
            payload["exc"] = mask_pii(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
