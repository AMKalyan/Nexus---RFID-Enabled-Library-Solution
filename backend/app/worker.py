"""Outbox delivery worker (FR 09). Runs inside the API process on a timer; safe to run more than one."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import NotificationOutbox, OutboxStatus
from app.integrations.base import DeliveryResult, OutboundMessage
from app.integrations.registry import get_adapter

log = logging.getLogger("nexus.worker")
MAX_ATTEMPTS = 5
BATCH = 50
INTERVAL_S = 5


def run_once(session: Session, now: datetime | None = None) -> int:
    """Deliver due messages. Returns how many were sent. Failures back off exponentially."""
    now = now or datetime.now(UTC)
    due = session.scalars(
        select(NotificationOutbox)
        .where(
            NotificationOutbox.status == OutboxStatus.queued,
            NotificationOutbox.next_attempt_at <= now,
        )
        .order_by(NotificationOutbox.created_at)
        .limit(BATCH)
        .with_for_update(skip_locked=True)
    ).all()
    sent = 0
    for row in due:
        message = OutboundMessage(row.channel.value, row.recipient, row.subject, row.body)
        try:
            result = get_adapter(row.channel.value).send(message)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 - adapter failures must not stop the batch
            log.exception("notification adapter error")
            result = DeliveryResult(ok=False, error=type(exc).__name__)
        if result.ok:
            row.status, row.sent_at = OutboxStatus.sent, now
            sent += 1
        else:
            row.attempts += 1
            row.last_error = (result.error or "delivery failed")[:500]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = OutboxStatus.failed
            else:
                row.next_attempt_at = now + timedelta(seconds=2**row.attempts)
    session.commit()
    return sent


async def run_forever(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(_tick)
        except Exception:  # noqa: BLE001 - keep the worker alive; errors are logged
            log.exception("outbox worker tick failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), INTERVAL_S)


def _tick() -> None:
    with SessionLocal() as session:
        run_once(session)
