"""Mock smart-card credential provider: maps a card UID to an active staff user."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Role, StaffUser
from app.integrations.base import StaffIdentity


class MockCredentialProvider:
    def __init__(self, session: Session) -> None:
        self.session = session

    def resolve(self, card_uid: str) -> StaffIdentity | None:
        user = self.session.scalar(
            select(StaffUser).where(StaffUser.smartcard_uid == card_uid.strip().upper())
        )
        if user is None or not user.is_active:
            return None
        role = self.session.get(Role, user.role_id)
        return StaffIdentity(user_id=user.id, role=role.name if role else "")
