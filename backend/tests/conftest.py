import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASE_APP = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://nexus_app:devapp@localhost:5433/nexus_test"
)
BASE_OWNER = os.environ.get(
    "TEST_OWNER_DATABASE_URL", "postgresql+psycopg://nexus_owner:devowner@localhost:5433/nexus_test"
)


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[None]:
    """Fresh test database migrated to head, once per test session."""
    owner = make_url(BASE_OWNER)
    admin = create_engine(owner.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{owner.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{owner.database}"'))
    admin.dispose()
    env = {**os.environ, "OWNER_DATABASE_URL": BASE_OWNER, "DATABASE_URL": BASE_APP}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env, cwd=BACKEND_DIR)
    os.environ["DATABASE_URL"] = BASE_APP
    yield


@pytest.fixture
def owner_conn(migrated_db) -> Iterator:
    eng = create_engine(BASE_OWNER)
    with eng.connect() as c:
        tx = c.begin()
        yield c
        tx.rollback()
    eng.dispose()


@pytest.fixture
def app_conn(migrated_db) -> Iterator:
    eng = create_engine(BASE_APP)
    with eng.connect() as c:
        tx = c.begin()
        yield c
        tx.rollback()
    eng.dispose()


@pytest.fixture
def db_session(app_conn) -> Iterator[Session]:
    s = Session(bind=app_conn, join_transaction_mode="create_savepoint")
    yield s
    s.close()


# --- API fixtures -----------------------------------------------------------------------------------


@pytest.fixture
def client(db_session):
    from fastapi.testclient import TestClient

    from app.core.ratelimit import limiter
    from app.db.base import get_session
    from app.main import create_app

    app = create_app(check_db=False)
    app.dependency_overrides[get_session] = lambda: db_session
    limiter.reset()
    return TestClient(app)


@pytest.fixture
def auth_headers(db_session):
    """auth_headers("Librarian") -> bearer header for a fresh staff user with that role."""
    from app.core.security import create_access_token
    from tests.factories import make_staff

    def make(role: str) -> dict[str, str]:
        user = make_staff(db_session, role)
        return {"Authorization": f"Bearer {create_access_token(user.id, 'staff', role)}"}

    return make


@pytest.fixture
def make_bib(db_session):
    from tests.factories import make_bib as _make_bib

    return lambda **kw: _make_bib(db_session, **kw)


@pytest.fixture
def sample_item(db_session):
    from tests.factories import make_bib, make_item

    return make_item(db_session, make_bib(db_session, title="Sample Title", author="Sample Author"))


@pytest.fixture
def withdrawn_item(db_session):
    from app.db.models import ItemStatus
    from tests.factories import make_bib, make_item

    return make_item(db_session, make_bib(db_session, title="Old Book"), status=ItemStatus.withdrawn)


@pytest.fixture
def sample_shelf_items(db_session):
    from tests.factories import make_bib, make_item

    call_nos = ["004.20 RAO", "001.10 IYE", "005.75 KUM", "003.00 DAS", "002.50 MEH"]
    return [make_item(db_session, make_bib(db_session, title=f"Book {c}"), call_no=c) for c in call_nos]


# --- circulation fixtures ---------------------------------------------------------------------------


@pytest.fixture
def sample_member(db_session):
    from tests.factories import make_member

    return make_member(db_session, password="Passw0rd!x")


@pytest.fixture
def other_member(db_session):
    from tests.factories import make_member

    return make_member(db_session)


@pytest.fixture
def blocked_member(db_session):
    from tests.factories import make_member

    m = make_member(db_session, status="blocked")
    m.block_reason = "Library card reported stolen"
    db_session.flush()
    return m


@pytest.fixture
def patron_headers(sample_member):
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(sample_member.id, 'patron', 'Patron')}"}


@pytest.fixture
def tagged_item(db_session):
    """Lending item with an active tag; exposes .active_epc."""
    from tests.factories import make_bib, make_item, make_tag

    item = make_item(db_session, make_bib(db_session, title="Tagged Book"))
    item.active_epc = make_tag(db_session, item).epc
    return item


@pytest.fixture
def reference_item(db_session):
    from app.db.models import ItemType
    from tests.factories import make_bib, make_item, make_tag

    item = make_item(db_session, make_bib(db_session, title="Encyclopaedia"), item_type=ItemType.reference)
    make_tag(db_session, item)
    return item


@pytest.fixture
def active_loan(db_session, sample_member):
    """Open loan on a tagged item; exposes .item_epc."""
    from tests.factories import make_bib, make_item, make_loan, make_tag

    item = make_item(db_session, make_bib(db_session, title="On Loan"))
    tag = make_tag(db_session, item, security_bit=False)
    loan = make_loan(db_session, item, sample_member)
    loan.item_epc = tag.epc
    return loan


@pytest.fixture
def overdue_loan(db_session, sample_member):
    """Loan that fell due exactly 5 days ago (UG: 2.00 per day)."""
    from tests.factories import make_bib, make_item, make_loan, make_tag

    item = make_item(db_session, make_bib(db_session, title="Overdue"))
    make_tag(db_session, item, security_bit=False)
    return make_loan(db_session, item, sample_member, days_ago=19, loan_days=14)


@pytest.fixture
def member_with_fines(db_session):
    from types import SimpleNamespace

    from tests.factories import make_fine, make_member

    member = make_member(db_session)
    return SimpleNamespace(member=member, set_open_fines=lambda amount: make_fine(db_session, member, amount))


@pytest.fixture
def committed_world(migrated_db):
    """Committed data plus an app whose requests each get a real session, for race tests.

    Cleans up its own rows (and their audit entries) with the owner role afterwards.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from sqlalchemy import delete, func, select
    from sqlalchemy.orm import sessionmaker

    from app.core.security import create_access_token
    from app.db.base import get_session
    from app.db.models import AuditLog, Bib, Fine, Item, Loan, Member, RfidTag, StaffUser
    from app.main import create_app
    from tests.factories import make_bib, make_item, make_member, make_staff, make_tag

    engine = create_engine(BASE_APP, pool_size=5)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    with maker() as s:
        member, clerk = make_member(s), make_staff(s, "CirculationClerk")
        item = make_item(s, make_bib(s, title="Race Book"))
        make_tag(s, item)
        s.commit()
        ids = SimpleNamespace(
            member=member.id,
            card=member.card_no,
            clerk=clerk.id,
            item=item.id,
            bib=item.bib_id,
            accession=item.accession_no,
        )

    app = create_app(check_db=False)

    def real_session():
        with maker() as session:
            yield session

    app.dependency_overrides[get_session] = real_session
    headers = {"Authorization": f"Bearer {create_access_token(ids.clerk, 'staff', 'CirculationClerk')}"}

    def race_checkout(threads: int = 2) -> list[int]:
        barrier = threading.Barrier(threads)
        client = TestClient(app)

        def attempt(_: int) -> int:
            barrier.wait()
            body = {"member_card_no": ids.card, "item": ids.accession}
            return client.post("/api/v1/circulation/checkout", headers=headers, json=body).status_code

        with ThreadPoolExecutor(threads) as pool:
            return list(pool.map(attempt, range(threads)))

    def count_open_loans() -> int:
        with maker() as s:
            q = (
                select(func.count())
                .select_from(Loan)
                .where(Loan.item_id == ids.item, Loan.returned_at.is_(None))
            )
            return s.scalar(q) or 0

    yield SimpleNamespace(race_checkout=race_checkout, count_open_loans=count_open_loans)

    owner = create_engine(BASE_OWNER)
    with owner.begin() as c:
        c.execute(delete(AuditLog).where(AuditLog.actor_id == ids.clerk))
        c.execute(delete(Fine).where(Fine.member_id == ids.member))
        c.execute(delete(Loan).where(Loan.item_id == ids.item))
        c.execute(delete(RfidTag).where(RfidTag.item_id == ids.item))
        c.execute(delete(Item).where(Item.id == ids.item))
        c.execute(delete(Bib).where(Bib.id == ids.bib))
        c.execute(delete(Member).where(Member.id == ids.member))
        c.execute(delete(StaffUser).where(StaffUser.id == ids.clerk))
    owner.dispose()
    engine.dispose()


@pytest.fixture
def activity_world(db_session):
    """Known activity for dashboard/report assertions."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal
    from types import SimpleNamespace

    from app.db.models import LoanChannel
    from tests.factories import (
        make_bib,
        make_device,
        make_fine,
        make_gate_event,
        make_item,
        make_loan,
        make_member,
        make_tag,
    )

    make_device(db_session, "GATE-01", "gate")
    make_device(db_session, "HH-01", "handheld")
    tagged = [make_item(db_session, make_bib(db_session, title=f"Tagged {n}")) for n in range(10)]
    for item in tagged:
        make_tag(db_session, item)
    for n in range(5):
        make_item(db_session, make_bib(db_session, title=f"Untagged {n}"))
    members = [make_member(db_session) for _ in range(3)]
    loans = []
    for n, item in enumerate(tagged[:6]):
        loan = make_loan(db_session, item, members[n % 3], days_ago=20 if n < 2 else 1)
        if n in (2, 3):
            loan.channel = LoanChannel.ncip
        loans.append(loan)
    for amount in ("12.00", "4.50", "3.50"):
        make_fine(db_session, members[0], amount)
    make_gate_event(db_session, tagged[7], alarm=True)
    make_gate_event(db_session, tagged[8], alarm=True)
    make_gate_event(db_session, tagged[9], alarm=False)
    old = make_gate_event(db_session, tagged[9], alarm=False)
    old.occurred_at = datetime.now(UTC) - timedelta(days=3)
    db_session.flush()
    return SimpleNamespace(
        tagged=10,
        untagged=5,
        active_loans=6,
        overdue_loans=2,
        alarms_today=2,
        open_fines_total=str(Decimal("20.00")),
    )


# --- device fixtures (each exposes .raw_key) --------------------------------------------------------


@pytest.fixture
def device_hh(db_session):
    from tests.factories import make_device

    return make_device(db_session, "HH-01", "handheld")


@pytest.fixture
def device_gate(db_session):
    from tests.factories import make_device

    return make_device(db_session, "GATE-01", "gate", config={"camera": "CAM-01"})


@pytest.fixture
def device_staff(db_session):
    from tests.factories import make_device

    return make_device(db_session, "STAFF-01", "staff_station")


@pytest.fixture
def device_card(db_session):
    from tests.factories import make_device

    return make_device(db_session, "CARD-01", "smartcard_reader")


@pytest.fixture
def camera(db_session):
    from tests.factories import make_device

    return make_device(db_session, "CAM-01", "camera")


@pytest.fixture
def device_event():
    """device_event("TagsRead", device_type="handheld", epcs=[...], **payload) -> event body."""
    import uuid
    from datetime import UTC, datetime

    def build(
        event_type="Heartbeat", device_type="handheld", epcs=None, occurred_at=None, event_id=None, **payload
    ):
        return {
            "event_id": event_id or str(uuid.uuid4()),
            "device_type": device_type,
            "type": event_type,
            "occurred_at": (occurred_at or datetime.now(UTC)).isoformat(),
            "epcs": epcs or [],
            "payload": payload,
        }

    return build


@pytest.fixture
def shelf_world(db_session):
    """Six tagged items on A-01 and three on B-01; exposes their EPCs and items."""
    from types import SimpleNamespace

    from tests.factories import make_bib, make_item, make_tag

    def stock(shelf, n):
        items = [
            make_item(db_session, make_bib(db_session, title=f"{shelf} book {i}"), shelf_code=shelf)
            for i in range(n)
        ]
        return items, [make_tag(db_session, item).epc for item in items]

    a_items, a_epcs = stock("A-01", 6)
    b_items, b_epcs = stock("B-01", 3)
    return SimpleNamespace(a01_items=a_items, a01_epcs=a_epcs, b01_items=b_items, b01_epcs=b_epcs)


@pytest.fixture
def agency(db_session):
    """NCIP agency (e.g. a self-check kiosk) with a known key exposed as .raw_key."""
    import hashlib

    from app.db.models import Agency

    raw = "agency-key-for-tests"
    row = Agency(
        code="KIOSK-01", name="Self-check kiosk", api_key_hash=hashlib.sha256(raw.encode()).hexdigest()
    )
    db_session.add(row)
    db_session.flush()
    row.raw_key = raw
    return row
