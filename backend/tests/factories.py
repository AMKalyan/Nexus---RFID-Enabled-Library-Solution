"""Test data builders. Synthetic values only."""

import random
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import (
    Bib,
    Device,
    DeviceType,
    Fine,
    FineReason,
    GateEvent,
    Item,
    ItemStatus,
    ItemType,
    Loan,
    LoanChannel,
    Member,
    MemberStatus,
    RecordSource,
    RfidTag,
    Role,
    Shelf,
    StaffUser,
    TagTarget,
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


def make_tag(session: Session, item: Item, epc: str | None = None, security_bit: bool = True) -> RfidTag:
    tag = RfidTag(
        epc=epc or "E280" + uuid.uuid4().hex[:20].upper(),
        target_type=TagTarget.item,
        item_id=item.id,
        security_bit=security_bit,
    )
    session.add(tag)
    session.flush()
    return tag


def make_loan(session: Session, item: Item, member: Member, days_ago: int = 1, loan_days: int = 14) -> Loan:
    issued = datetime.now(UTC) - timedelta(days=days_ago)
    loan = Loan(
        item_id=item.id,
        member_id=member.id,
        issued_at=issued,
        due_at=issued + timedelta(days=loan_days),
        channel=LoanChannel.ui,
    )
    item.status = ItemStatus.on_loan
    session.add(loan)
    session.flush()
    return loan


def make_fine(session: Session, member: Member, amount: str) -> Fine:
    fine = Fine(member_id=member.id, amount=Decimal(amount), reason=FineReason.manual)
    session.add(fine)
    session.flush()
    return fine


def make_device(session: Session, code: str, device_type: str, config: dict | None = None) -> Device:
    """Device with a known raw key exposed as .raw_key (stored hashed)."""
    import hashlib

    raw = f"key-{code}-{uuid.uuid4().hex[:8]}"
    device = session.get(Device, code)
    if device is None:
        device = Device(
            code=code,
            device_type=DeviceType(device_type),
            name=code,
            location="Test",
            config=config or {},
            api_key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        )
        session.add(device)
    else:
        device.api_key_hash = hashlib.sha256(raw.encode()).hexdigest()
        device.config = config or device.config
    session.flush()
    device.raw_key = raw
    return device


def make_gate_event(session: Session, item: Item, alarm: bool, hours_ago: int = 0) -> GateEvent:
    event = GateEvent(
        device_code="GATE-01",
        event_id=uuid.uuid4(),
        epc="E280TEST",
        item_id=item.id,
        accession_no=item.accession_no,
        direction="out",
        authorised=not alarm,
        alarm=alarm,
        occurred_at=datetime.now(UTC) - timedelta(hours=hours_ago),
    )
    session.add(event)
    session.flush()
    return event
