"""Dashboard statistics and filterable reports (FR 08, AC 08)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import AppError
from app.db.models import (
    AuditLog,
    Bib,
    CircPolicy,
    Device,
    DeviceEvent,
    Fine,
    FineStatus,
    Footfall,
    GateEvent,
    Item,
    ItemStatus,
    Loan,
    Member,
    MemberStatus,
    RfidTag,
    Role,
    StaffUser,
    TagStatus,
)
from app.services.export import ReportTable


@dataclass(frozen=True)
class ReportFilters:
    date_from: date | None = None
    date_to: date | None = None
    extra: dict[str, str] | None = None

    def get(self, key: str) -> str | None:
        return (self.extra or {}).get(key)


def _range(column: Any, f: ReportFilters) -> list[Any]:
    conds = []
    if f.date_from:
        conds.append(column >= datetime.combine(f.date_from, time.min, UTC))
    if f.date_to:
        conds.append(column < datetime.combine(f.date_to + timedelta(days=1), time.min, UTC))
    return conds


def _bool(value: str | None) -> bool | None:
    return None if value is None else value.lower() in ("1", "true", "yes")


# --- report definitions: (title, columns, query builder) ---------------------------------------------


def _tagged_items(f: ReportFilters) -> Select:
    q = (
        select(
            RfidTag.epc,
            Item.accession_no,
            Bib.title,
            Item.shelf_code,
            RfidTag.status,
            RfidTag.security_bit,
            RfidTag.encoded_at,
        )
        .join(Item, Item.id == RfidTag.item_id)
        .join(Bib, Bib.id == Item.bib_id)
        .where(*_range(RfidTag.encoded_at, f))
        .order_by(RfidTag.encoded_at.desc())
    )
    if shelf_code := f.get("shelf_code"):
        q = q.where(Item.shelf_code == shelf_code)
    if tag_status := f.get("tag_status"):
        q = q.where(RfidTag.status == TagStatus(tag_status))
    return q


def _members(f: ReportFilters) -> Select:
    open_loans = (
        select(func.count()).where(Loan.member_id == Member.id, Loan.returned_at.is_(None)).scalar_subquery()
    )
    open_fines = (
        select(func.coalesce(func.sum(Fine.amount), 0))
        .where(Fine.member_id == Member.id, Fine.status == FineStatus.open)
        .scalar_subquery()
    )
    q = (
        select(
            Member.card_no,
            Member.full_name,
            Member.email,
            Member.phone,
            Member.category_code,
            Member.status,
            open_loans.label("open_loans"),
            open_fines.label("open_fines"),
        )
        .where(*_range(Member.created_at, f))
        .order_by(Member.card_no)
    )
    if category := f.get("category"):
        q = q.where(Member.category_code == category)
    if status := f.get("status"):
        q = q.where(Member.status == MemberStatus(status))
    return q


def _circulation(f: ReportFilters) -> Select:
    q = (
        select(
            Loan.issued_at,
            Item.accession_no,
            Bib.title,
            Member.card_no,
            Loan.channel,
            Loan.due_at,
            Loan.returned_at,
            Loan.renew_count,
            Loan.issued_by,
        )
        .join(Item, Item.id == Loan.item_id)
        .join(Bib, Bib.id == Item.bib_id)
        .join(Member, Member.id == Loan.member_id)
        .where(*_range(Loan.issued_at, f))
        .order_by(Loan.issued_at.desc())
    )
    if channel := f.get("channel"):
        q = q.where(Loan.channel == channel)
    if operator_id := f.get("operator_id"):
        q = q.where(Loan.issued_by == operator_id)
    if member_category := f.get("member_category"):
        q = q.where(Member.category_code == member_category)
    return q


def _operators(f: ReportFilters) -> Select:
    q = (
        select(
            StaffUser.username,
            Role.name,
            AuditLog.action,
            func.count().label("count"),
            func.max(AuditLog.occurred_at).label("last_at"),
        )
        .join(StaffUser, StaffUser.id == AuditLog.actor_id)
        .join(Role, Role.id == StaffUser.role_id)
        .where(AuditLog.actor_type == "staff", *_range(AuditLog.occurred_at, f))
        .group_by(StaffUser.username, Role.name, AuditLog.action)
        .order_by(StaffUser.username, AuditLog.action)
    )
    if operator_id := f.get("operator_id"):
        q = q.where(StaffUser.id == operator_id)
    return q


def _rfid_clients(f: ReportFilters) -> Select:
    ev = aliased(DeviceEvent)
    join_cond = and_(ev.device_code == Device.code, *_range(ev.occurred_at, f))
    q = (
        select(
            Device.code,
            Device.device_type,
            Device.location,
            Device.ip_address,
            func.count(ev.id).label("events"),
            func.max(ev.occurred_at).label("last_event_at"),
            Device.last_heartbeat_at,
        )
        .outerjoin(ev, join_cond)
        .group_by(Device.code)
        .order_by(Device.code)
    )
    if device_code := f.get("device_code"):
        q = q.where(Device.code == device_code)
    if device_type := f.get("device_type"):
        q = q.where(Device.device_type == device_type)
    return q


def _fines(f: ReportFilters) -> Select:
    q = (
        select(Fine.created_at, Member.card_no, Fine.amount, Fine.reason, Fine.status, Fine.settled_at)
        .join(Member, Member.id == Fine.member_id)
        .where(*_range(Fine.created_at, f))
        .order_by(Fine.created_at.desc())
    )
    if status := f.get("status"):
        q = q.where(Fine.status == FineStatus(status))
    return q


def _gate_events(f: ReportFilters) -> Select:
    q = (
        select(
            GateEvent.occurred_at,
            GateEvent.device_code,
            GateEvent.accession_no,
            GateEvent.direction,
            GateEvent.alarm,
            GateEvent.authorised,
            GateEvent.offline_decision,
            GateEvent.notified,
        )
        .where(*_range(GateEvent.occurred_at, f))
        .order_by(GateEvent.occurred_at.desc())
    )
    alarm = _bool(f.get("alarm"))
    if alarm is not None:
        q = q.where(GateEvent.alarm.is_(alarm))
    if device_code := f.get("device_code"):
        q = q.where(GateEvent.device_code == device_code)
    return q


REPORTS: dict[str, tuple[str, list[str], Callable[[ReportFilters], Select]]] = {
    "tagged-items": (
        "Tagged items",
        ["epc", "accession_no", "title", "shelf", "tag_status", "security_bit", "encoded_at"],
        _tagged_items,
    ),
    "members": (
        "Members",
        ["card_no", "full_name", "email", "phone", "category", "status", "open_loans", "open_fines"],
        _members,
    ),
    "circulation": (
        "Circulation",
        [
            "issued_at",
            "accession_no",
            "title",
            "member",
            "channel",
            "due_at",
            "returned_at",
            "renewals",
            "operator_id",
        ],
        _circulation,
    ),
    "operators": ("Operator activity", ["operator", "role", "action", "count", "last_at"], _operators),
    "rfid-clients": (
        "RFID client activity",
        ["device", "type", "location", "ip_address", "events", "last_event_at", "last_heartbeat_at"],
        _rfid_clients,
    ),
    "fines": ("Fines", ["created_at", "member", "amount", "reason", "status", "settled_at"], _fines),
    "gate-events": (
        "Security gate events",
        [
            "occurred_at",
            "gate",
            "accession_no",
            "direction",
            "alarm",
            "authorised",
            "offline_decision",
            "notified",
        ],
        _gate_events,
    ),
}

FILTERS = {
    "tagged-items": ["shelf_code", "tag_status"],
    "members": ["category", "status"],
    "circulation": ["channel", "operator_id", "member_category"],
    "operators": ["operator_id"],
    "rfid-clients": ["device_code", "device_type"],
    "fines": ["status"],
    "gate-events": ["alarm", "device_code"],
}
PII_COLUMNS = {"email", "phone"}
MAX_ROWS = 5000


def _plain(value: Any) -> Any:
    return value.value if hasattr(value, "value") and not isinstance(value, Decimal) else value


class ReportsService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(self, name: str, filters: ReportFilters, mask_pii: bool) -> ReportTable:
        if name not in REPORTS:
            raise AppError("REPORT_NOT_FOUND", "Unknown report", 404)
        title, columns, build = REPORTS[name]
        try:
            rows = self.session.execute(build(filters).limit(MAX_ROWS)).all()
        except ValueError as exc:  # unknown enum value in a filter
            raise AppError("ERR_VALIDATION", "Invalid report filter", 422) from exc
        masked = {i for i, c in enumerate(columns) if c in PII_COLUMNS} if mask_pii else set()
        table = ReportTable(name=name, title=title, columns=columns)
        for row in rows:
            table.rows.append(["***" if i in masked and v else _plain(v) for i, v in enumerate(row)])
        return table

    def dashboard(self) -> dict[str, Any]:
        s = self.session
        now = datetime.now(UTC)
        today = datetime.combine(now.date(), time.min, UTC)
        count = lambda q: s.scalar(q) or 0  # noqa: E731
        active_tag = select(RfidTag.item_id).where(RfidTag.status == TagStatus.active)
        live_items = select(func.count()).select_from(Item).where(Item.status != ItemStatus.withdrawn)
        open_loans = select(func.count()).select_from(Loan).where(Loan.returned_at.is_(None))

        since = (now - timedelta(days=29)).date()
        by_day = dict(
            s.execute(
                select(func.date(Loan.issued_at), func.count())
                .where(Loan.issued_at >= datetime.combine(since, time.min, UTC))
                .group_by(func.date(Loan.issued_at))
            )
            .tuples()
            .all()
        )
        top = s.execute(
            select(Bib.title, func.count(Loan.id).label("n"))
            .join(Item, Item.bib_id == Bib.id)
            .join(Loan, Loan.item_id == Item.id)
            .group_by(Bib.title)
            .order_by(func.count(Loan.id).desc(), Bib.title)
            .limit(5)
        ).all()
        footfall = s.execute(
            select(
                func.coalesce(func.sum(Footfall.in_count), 0), func.coalesce(func.sum(Footfall.out_count), 0)
            ).where(Footfall.hour >= today)
        ).one()
        return {
            "tagged_items": count(live_items.where(Item.id.in_(active_tag))),
            "untagged_items": count(live_items.where(Item.id.not_in(active_tag))),
            "members_active": count(
                select(func.count()).select_from(Member).where(Member.status == MemberStatus.active)
            ),  # noqa: E501
            "members_blocked": count(
                select(func.count()).select_from(Member).where(Member.status == MemberStatus.blocked)
            ),  # noqa: E501
            "loans_active": count(open_loans),
            "loans_overdue": count(open_loans.where(Loan.due_at < now)),
            "fines_open_total": Decimal(
                s.scalar(
                    select(func.coalesce(func.sum(Fine.amount), 0)).where(Fine.status == FineStatus.open)
                )
                or 0
            ),
            "gate_alarms_today": count(
                select(func.count())
                .select_from(GateEvent)
                .where(GateEvent.alarm.is_(True), GateEvent.occurred_at >= today)  # noqa: E501
            ),
            "footfall_today": {"in": int(footfall[0]), "out": int(footfall[1])},
            "loans_by_day": [
                {
                    "date": (since + timedelta(days=n)).isoformat(),
                    "count": by_day.get(since + timedelta(days=n), 0),
                }
                for n in range(30)
            ],
            "top_titles": [{"title": t, "loans": n} for t, n in top],
            "categories": list(
                s.scalars(select(CircPolicy.category_code).order_by(CircPolicy.category_code))
            ),
        }
