"""Notification outbox (FR 09): services queue messages; the worker delivers them through adapters."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import AppSetting, Channel, Member, NotificationOutbox, OutboxStatus
from app.services.notification_templates import TEMPLATES, render

DEFAULT_GATE_RECIPIENTS = ["security@example.org"]
MEMBER_PRINTER = "PRN-01"


class NotificationsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def queue(
        self,
        channel: str,
        template: str,
        recipients: list[str],
        context: dict,
        related: tuple[str, str] | None = None,
    ) -> list[NotificationOutbox]:
        if template not in TEMPLATES:
            raise AppError("TEMPLATE_UNKNOWN", "Unknown notification template", 500)
        subject, body = render(template, context)
        rows = [
            NotificationOutbox(
                channel=Channel(channel),
                recipient=recipient,
                template=template,
                subject=subject,
                body=body,
                related_type=related[0] if related else None,
                related_id=related[1] if related else None,
                status=OutboxStatus.queued,
            )
            for recipient in recipients
        ]
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def queue_for_member(self, member: Member, template: str, context: dict) -> list[NotificationOutbox]:
        """Respect the member's channel preferences."""
        rows: list[NotificationOutbox] = []
        if member.notify_email and member.email:
            rows += self.queue("email", template, [member.email], context, ("member", str(member.id)))
        if member.notify_sms and member.phone:
            rows += self.queue("sms", template, [member.phone], context, ("member", str(member.id)))
        if member.notify_print:
            rows += self.queue("print", template, [MEMBER_PRINTER], context, ("member", str(member.id)))
        return rows

    def setting(self, key: str, default):  # noqa: ANN001, ANN201
        row = self.session.get(AppSetting, key)
        return default if row is None or row.value is None else row.value

    def gate_recipients(self) -> list[str]:
        return list(self.setting("gate_alert_recipients", DEFAULT_GATE_RECIPIENTS))

    def outbox(self, status: OutboxStatus | None = None, limit: int = 200) -> list[NotificationOutbox]:
        query = select(NotificationOutbox).order_by(NotificationOutbox.created_at.desc()).limit(limit)
        if status:
            query = query.where(NotificationOutbox.status == status)
        return list(self.session.scalars(query))
