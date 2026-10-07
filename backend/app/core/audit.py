import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import mask_mapping
from app.db.models import AuditLog


def audit(
    session: Session,
    *,
    actor_type: str,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Record an audit entry in the caller's transaction. Personal data in details is masked."""
    session.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=mask_mapping(details or {}),
            ip=ip,
        )
    )
