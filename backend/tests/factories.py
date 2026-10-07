"""Test data builders. Synthetic values only."""

import random
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    Bib,
    Item,
    ItemStatus,
    ItemType,
    Member,
    MemberStatus,
    RecordSource,
    Role,
    Shelf,
    StaffUser,
)

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


def ensure_shelf(session: Session, code: str = "A-01") -> Shelf:
    shelf = session.get(Shelf, code)
    if shelf is None:
        shelf = Shelf(code=code, name=f"Shelf {code}", location="Test hall")
        session.add(shelf)
        session.flush()
    return shelf


def make_bib(session: Session, title: str = "Test Title", **kw) -> Bib:
    bib = Bib(title=title, source=RecordSource.nexus, **kw)
    session.add(bib)
    session.flush()
    return bib


def make_item(
    session: Session,
    bib: Bib,
    shelf_code: str = "A-01",
    item_type: ItemType = ItemType.lending,
    status: ItemStatus = ItemStatus.available,
    call_no: str | None = None,
) -> Item:
    ensure_shelf(session, shelf_code)
    n = random.randint(100000, 999999)  # noqa: S311 (test data)
    item = Item(
        bib_id=bib.id,
        accession_no=f"ACC-{n}",
        barcode=f"BC{n:08d}",
        call_no=call_no or "000.00 TST",
        shelf_code=shelf_code,
        item_type=item_type,
        status=status,
    )
    session.add(item)
    session.flush()
    return item
