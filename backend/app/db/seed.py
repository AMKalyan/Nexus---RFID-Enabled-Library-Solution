"""Synthetic data for development, tests and the demonstration.

    python -m app.db.seed --legacy 2000 --demo

--legacy N  fills the simulated existing ILMS (legacy_ilms) as legacy_owner, only if it is empty.
--demo      mirrors legacy records into nexus and adds shelves, devices, staff users, tags and activity.

Everything is generated from a fixed seed; no real people or institutions are involved. Generated
passwords and device keys are printed once and written to ops/demo-credentials.txt (git-ignored).
This module is operations tooling: it may run `SET ROLE` on the owner connection (ADR-0003).
"""

import argparse
import hashlib
import random
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from faker import Faker
from sqlalchemy import Connection, create_engine, func, insert, select, text
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import SessionLocal
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
    LegacyAccession,
    LegacyBorrower,
    LegacyCatalogue,
    Loan,
    LoanChannel,
    Member,
    RecordSource,
    RfidTag,
    Role,
    Shelf,
    StaffUser,
    TagTarget,
)
from app.integrations.legacy_db import DbLegacyConnector
from app.services.demo import public_password_for
from app.services.validation import isbn13_valid  # noqa: F401  (re-exported for tests)

SEED = 42
CREDENTIALS_FILE = Path(__file__).resolve().parents[3] / "ops" / "demo-credentials.txt"

# Shelf code, name, DDC range covered.
SHELVES = [
    ("A-01", "Generalities & Philosophy", 0, 199),
    ("A-02", "Religion", 200, 299),
    ("B-01", "Social Sciences", 300, 399),
    ("B-02", "Language", 400, 499),
    ("C-01", "Science", 500, 599),
    ("C-02", "Technology", 600, 699),
    ("D-01", "Arts", 700, 799),
    ("D-02", "Literature & History", 800, 999),
]

DEVICES = [
    ("STAFF-01", DeviceType.staff_station, "Circulation desk reader", "Circulation desk", "10.10.20.11", {}),
    ("CARD-01", DeviceType.smartcard_reader, "Staff card reader", "Circulation desk", "10.10.20.12", {}),
    ("HH-01", DeviceType.handheld, "Handheld inventory reader", "Stacks", "10.10.20.21", {}),
    ("GATE-01", DeviceType.gate, "Main exit gate", "Main exit", "10.10.20.31", {"camera": "CAM-01"}),
    ("CAM-01", DeviceType.camera, "Main exit camera", "Main exit", "10.10.20.41", {}),
    ("PRN-01", DeviceType.printer, "Desk printer", "Circulation desk", "10.10.20.51", {}),
]

STAFF = [
    ("admin", "Admin"),
    ("librarian", "Librarian"),
    ("clerk", "CirculationClerk"),
    ("auditor", "Auditor"),
]

LEGACY_STATUS = {
    "AV": ItemStatus.available,
    "IS": ItemStatus.on_loan,
    "LS": ItemStatus.missing,
    "WD": ItemStatus.withdrawn,
}


# --- helpers -----------------------------------------------------------------------------------------


def isbn13(r: random.Random) -> str:
    digits = [9, 7, 8] + [r.randint(0, 9) for _ in range(9)]
    check = (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    return "".join(map(str, [*digits, check]))


def shelf_for_call_no(call_no: str | None) -> str | None:
    try:
        ddc = int((call_no or "")[:3])
    except ValueError:
        return None
    return next((code for code, _, lo, hi in SHELVES if lo <= ddc <= hi), None)


def new_epc(r: random.Random) -> str:
    return "E280" + "".join(r.choice("0123456789ABCDEF") for _ in range(20))


# --- legacy (existing ILMS) --------------------------------------------------------------------------


def seed_legacy(conn: Connection, n_bibs: int = 2000, n_borrowers: int = 300) -> dict[str, int]:
    """Insert synthetic legacy records as legacy_owner. The caller commits."""
    fake = Faker("en_IN")
    fake.seed_instance(SEED)
    r = random.Random(SEED)  # noqa: S311  # nosec B311 - reproducible synthetic data, not secrets

    bibs, accessions, borrowers = [], [], []
    acc_counter = 0
    for bib_no in range(1, n_bibs + 1):
        author = fake.name()
        bibs.append(
            {
                "bib_no": bib_no,
                "title": fake.catch_phrase().title(),
                "author": author,
                "publisher": fake.company(),
                "isbn": isbn13(r),
                "pub_year": r.randint(1965, 2025),
            }
        )
        ddc = r.randint(0, 999)
        for _ in range(2 if r.random() < 0.2 else 1):
            acc_counter += 1
            accessions.append(
                {
                    "acc_no": f"ACC-{acc_counter:06d}",
                    "bib_no": bib_no,
                    "call_no": f"{ddc:03d}.{r.randint(0, 99):02d} {author.split()[-1][:3].upper()}",
                    "location": "Reference" if r.random() < 0.1 else "Stacks",
                    "status": r.choices(["AV", "IS", "LS", "WD"], weights=[87, 10, 2, 1])[0],
                }
            )
    for n in range(1, n_borrowers + 1):
        name = fake.name()
        slug = "".join(ch for ch in name.lower() if ch.isalpha())[:12]
        borrowers.append(
            {
                "borrower_id": f"B{n:05d}",
                "name": name,
                "email": f"{slug}{n}@example.org",
                "phone": f"+91-00000-{n:05d}",
                "category": r.choices(["UG", "PG", "FAC", "STAFF"], weights=[60, 25, 10, 5])[0],
            }
        )

    conn.execute(text("SET ROLE legacy_owner"))
    conn.execute(insert(LegacyCatalogue), bibs)
    conn.execute(insert(LegacyAccession), accessions)
    conn.execute(insert(LegacyBorrower), borrowers)
    conn.execute(text("RESET ROLE"))
    return {"bibs": len(bibs), "accessions": len(accessions), "borrowers": len(borrowers)}


# --- mirror legacy into nexus ------------------------------------------------------------------------


def mirror_legacy(session: Session) -> dict[str, int]:
    """Copy legacy records into nexus tables by reference. Never writes to legacy_ilms. Idempotent."""
    connector = DbLegacyConnector(session)
    shelves = set(session.scalars(select(Shelf.code)))
    bib_ids = {
        ref: bib_id
        for ref, bib_id in session.execute(
            select(Bib.legacy_ref, Bib.id).where(Bib.source == RecordSource.legacy)
        )
    }
    known_items = set(session.scalars(select(Item.legacy_ref).where(Item.legacy_ref.is_not(None))))
    known_members = set(session.scalars(select(Member.legacy_ref).where(Member.legacy_ref.is_not(None))))
    counts = {"bibs": 0, "items": 0, "members": 0}

    for cat in connector.iter_catalogue():
        ref = str(cat.bib_no)
        if ref in bib_ids:
            continue
        bib = Bib(
            title=cat.title,
            author=cat.author,
            publisher=cat.publisher,
            isbn=cat.isbn,
            pub_year=cat.pub_year,
            source=RecordSource.legacy,
            legacy_ref=ref,
        )
        session.add(bib)
        session.flush()
        bib_ids[ref] = bib.id
        counts["bibs"] += 1

    for acc in connector.iter_accessions():
        if acc.acc_no in known_items:
            continue
        shelf = shelf_for_call_no(acc.call_no)
        session.add(
            Item(
                bib_id=bib_ids[str(acc.bib_no)],
                accession_no=acc.acc_no,
                barcode="BC" + acc.acc_no.split("-")[-1].rjust(8, "0"),
                call_no=acc.call_no,
                shelf_code=shelf if shelf in shelves else None,
                item_type=ItemType.reference if acc.location == "Reference" else ItemType.lending,
                status=LEGACY_STATUS.get(acc.status, ItemStatus.available),
                legacy_ref=acc.acc_no,
            )
        )
        counts["items"] += 1

    for b in connector.iter_borrowers():
        if b.borrower_id in known_members:
            continue
        session.add(
            Member(
                card_no=b.borrower_id,
                full_name=b.name,
                email=b.email,
                phone=b.phone,
                category_code=b.category,
                legacy_ref=b.borrower_id,
            )
        )
        counts["members"] += 1

    session.flush()
    if any(counts.values()):
        audit(
            session,
            actor_type="system",
            actor_id=None,
            action="legacy.mirror",
            entity_type="legacy",
            details=counts,
        )
    return counts


# --- demo data ---------------------------------------------------------------------------------------


def seed_demo(session: Session) -> dict[str, str]:
    """Shelves, devices, staff, tags and some activity. Returns generated credentials."""
    r = random.Random(SEED)  # noqa: S311  # nosec B311 - reproducible synthetic data, not secrets
    creds: dict[str, str] = {}

    for code, name, lo, hi in SHELVES:
        if session.get(Shelf, code) is None:
            session.add(
                Shelf(
                    code=code,
                    name=name,
                    location="Main hall",
                    call_no_from=f"{lo:03d}",
                    call_no_to=f"{hi:03d}",
                )
            )
    session.flush()
    mirror_legacy(session)

    for code, dtype, name, location, ip, config in DEVICES:
        if session.get(Device, code) is None:
            key = secrets.token_urlsafe(24)
            creds[f"device {code} key"] = key
            session.add(
                Device(
                    code=code,
                    device_type=dtype,
                    name=name,
                    location=location,
                    ip_address=ip,
                    config=config,
                    api_key_hash=hashlib.sha256(key.encode()).hexdigest(),
                )
            )

    roles = {name: role_id for name, role_id in session.execute(select(Role.name, Role.id))}
    for username, role in STAFF:
        if session.scalar(select(StaffUser).where(StaffUser.username == username)) is None:
            password = public_password_for(get_settings(), username) or secrets.token_urlsafe(12)
            uid = secrets.token_hex(4).upper()
            creds[f"staff {username} ({role}) password"] = password
            creds[f"staff {username} smart-card UID"] = uid
            session.add(
                StaffUser(
                    username=username,
                    display_name=f"Demo {role}",
                    email=f"{username}@example.org",
                    password_hash=hash_password(password),
                    smartcard_uid=uid,
                    role_id=roles[role],
                )
            )

    patrons = session.scalars(select(Member).order_by(Member.card_no).limit(3)).all()
    for m in patrons:
        if m.password_hash is None:
            password = public_password_for(get_settings(), m.card_no) or secrets.token_urlsafe(12)
            creds[f"patron {m.card_no} password"] = password
            m.password_hash = hash_password(password)
    session.flush()

    if session.scalar(select(func.count()).select_from(RfidTag)) == 0:
        _seed_activity(session, r)
    return creds


def _seed_activity(session: Session, r: random.Random) -> None:
    now = datetime.now(UTC)
    items = list(
        session.scalars(select(Item).where(Item.status != ItemStatus.withdrawn).order_by(Item.accession_no))
    )
    tagged = [i for i in items if r.random() < 0.6]
    for item in tagged:
        session.add(
            RfidTag(
                epc=new_epc(r),
                target_type=TagTarget.item,
                item_id=item.id,
                security_bit=item.status != ItemStatus.on_loan,
            )
        )

    members = session.scalars(select(Member).order_by(Member.card_no)).all()
    on_loan = [i for i in tagged if i.status == ItemStatus.on_loan]
    for idx, item in enumerate(on_loan):
        member = members[idx % len(members)]
        issued = now - timedelta(days=r.randint(1, 30))
        due = issued + timedelta(days=14)
        loan = Loan(
            item_id=item.id,
            member_id=member.id,
            issued_at=issued,
            due_at=due,
            channel=r.choice([LoanChannel.ui, LoanChannel.ui, LoanChannel.ncip]),
        )
        session.add(loan)
        if due < now and r.random() < 0.5:
            session.flush()
            days = (now - due).days
            session.add(
                Fine(
                    member_id=member.id, loan_id=loan.id, amount=Decimal(2 * days), reason=FineReason.overdue
                )
            )

    available_tagged = [i for i in tagged if i.status == ItemStatus.available][:6]
    for n, item in enumerate(available_tagged):
        session.add(
            GateEvent(
                device_code="GATE-01",
                event_id=uuid.uuid4(),
                epc="SEEDED",
                item_id=item.id,
                accession_no=item.accession_no,
                direction="out",
                authorised=False,
                alarm=True,
                occurred_at=now - timedelta(hours=n * 9),
            )
        )
    session.flush()


# --- CLI ---------------------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic Nexus data")
    parser.add_argument("--legacy", type=int, metavar="N", help="seed N legacy bibliographic records")
    parser.add_argument("--demo", action="store_true", help="mirror legacy data and add demo data")
    args = parser.parse_args()

    if args.legacy:
        engine = create_engine(get_settings().owner_database_url)
        with engine.begin() as conn:
            existing = conn.execute(select(func.count()).select_from(LegacyCatalogue)).scalar()
            if existing:
                print(f"legacy_ilms already has {existing} records; skipping")
            else:
                print("legacy:", seed_legacy(conn, n_bibs=args.legacy))

    if args.demo:
        with SessionLocal() as session:
            creds = seed_demo(session)
            session.commit()
            counts = {m.__name__: session.scalar(select(func.count()).select_from(m))
                      for m in (Bib, Item, Member, RfidTag, Loan, Device, StaffUser)}  # fmt: skip
        print("nexus:", counts)
        if creds:
            CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with CREDENTIALS_FILE.open("a", encoding="utf-8") as f:
                f.write(f"# generated {datetime.now(UTC).isoformat()}\n")
                f.writelines(f"{k}: {v}\n" for k, v in creds.items())
            print(f"{len(creds)} generated credentials written to {CREDENTIALS_FILE}")


if __name__ == "__main__":
    main()
