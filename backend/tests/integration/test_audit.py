import pytest
from sqlalchemy import select

from app.core.audit import audit
from app.db.models import AuditLog

pytestmark = pytest.mark.db


def test_nfr02_audit_masks_pii_details(db_session):
    audit(
        db_session,
        actor_type="system",
        actor_id=None,
        action="member.update",
        entity_type="member",
        entity_id="m1",
        details={"email": "x@example.org", "status": "blocked"},
    )
    db_session.flush()
    row = db_session.scalars(select(AuditLog).where(AuditLog.entity_id == "m1")).one()
    assert row.details == {"email": "***", "status": "blocked"}
