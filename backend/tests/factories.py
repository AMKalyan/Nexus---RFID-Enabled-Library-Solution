"""Test data builders. Synthetic values only."""

import random
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import Member, MemberStatus, Role, StaffUser

DEFAULT_PASSWORD = "Passw0rd!x"


def make_staff(
    session: Session,
    role: str,
    username: str | None = None,
    password: str = DEFAULT_PASSWORD,
    smartcard_uid: str | None = None,
) -> StaffUser:
    role_id = session.scalars(select(Role.id).where(Role.name == role)).one()
    user = StaffUser(
        username=username or f"{role.lower()}-{uuid.uuid4().hex[:6]}",
        display_name=f"Test {role}",
        email="staff@example.org",
        password_hash=hash_password(password),
        smartcard_uid=smartcard_uid,
        role_id=role_id,
    )
    session.add(user)
    session.flush()
    return user


def make_member(
    session: Session, category: str = "UG", status: str = "active", password: str | None = None
) -> Member:
    member = Member(
        card_no=f"M{random.randint(100000, 999999)}",  # noqa: S311 (test data)
        full_name="Test Member",
        email="member@example.org",
        phone="+91-00000-01234",
        category_code=category,
        status=MemberStatus(status),
        password_hash=hash_password(password) if password else None,
    )
    session.add(member)
    session.flush()
    return member
