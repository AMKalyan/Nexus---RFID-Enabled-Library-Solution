"""Mock email, SMS and print channels. Messages are written to the outbox folder instead of being sent.

MOCK_EMAIL_FAIL_FIRST=N makes the email mock fail its first N sends, to exercise retry handling.
"""

import os
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas

from app.core.config import get_settings
from app.integrations.base import DeliveryResult, OutboundMessage


def _outbox(channel: str) -> Path:
    path = Path(os.environ.get("OUTBOX_DIR", get_settings().outbox_dir)) / channel
    path.mkdir(parents=True, exist_ok=True)
    return path


def _name() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"


class MockEmail:
    _failures = 0

    @classmethod
    def reset(cls) -> None:
        cls._failures = 0

    def send(self, message: OutboundMessage) -> DeliveryResult:
        fail_first = int(os.environ.get("MOCK_EMAIL_FAIL_FIRST", "0"))
        if MockEmail._failures < fail_first:
            MockEmail._failures += 1
            return DeliveryResult(ok=False, error="mock SMTP unavailable")
        email = EmailMessage()
        email["From"] = "nexus@example.org"
        email["To"] = message.recipient
        email["Subject"] = message.subject or ""
        email.set_content(message.body)
        (_outbox("email") / f"{_name()}.eml").write_bytes(bytes(email))
        return DeliveryResult(ok=True)


class MockSms:
    def send(self, message: OutboundMessage) -> DeliveryResult:
        text = f"To: {message.recipient}\n\n{message.body[:480]}\n"
        (_outbox("sms") / f"{_name()}.txt").write_text(text, encoding="utf-8")
        return DeliveryResult(ok=True)


class MockPrint:
    def send(self, message: OutboundMessage) -> DeliveryResult:
        buf = BytesIO()
        pdf = canvas.Canvas(buf, pagesize=A5)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, 540, message.subject or "Notice")
        pdf.setFont("Helvetica", 10)
        for i, line in enumerate(message.body.splitlines()[:30]):
            pdf.drawString(40, 510 - 14 * i, line[:90])
        pdf.showPage()
        pdf.save()
        (_outbox("print") / f"{_name()}.pdf").write_bytes(buf.getvalue())
        return DeliveryResult(ok=True)
