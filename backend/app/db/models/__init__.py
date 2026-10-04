"""All ORM models. Importing this package registers every table on Base.metadata."""

from app.db.models.catalog import (
    Bib,
    Item,
    ItemStatus,
    ItemType,
    RecordSource,
    RfidTag,
    Shelf,
    TagStatus,
    TagTarget,
)
from app.db.models.circulation import Fine, FineReason, FineStatus, Loan, LoanChannel
from app.db.models.devices import (
    Device,
    DeviceEvent,
    DeviceType,
    Footfall,
    GateEvent,
    InventoryRead,
    InventoryResult,
    InventorySession,
)
from app.db.models.identity import Permission, RefreshToken, Role, RolePermission, StaffUser, SubjectType
from app.db.models.legacy import LegacyAccession, LegacyBorrower, LegacyCatalogue
from app.db.models.members import CircPolicy, Member, MemberStatus
from app.db.models.notify import Channel, NotificationOutbox, OutboxStatus
from app.db.models.ops import AppSetting, AppVersion, AuditLog, BatchStatus, MigrationBatch
from app.db.models.staging import ImportRow, ImportStatus

__all__ = [
    "AppSetting", "AppVersion", "AuditLog", "BatchStatus", "Bib", "Channel", "CircPolicy", "Device",
    "DeviceEvent", "DeviceType", "Fine", "FineReason", "FineStatus", "Footfall", "GateEvent", "ImportRow",
    "ImportStatus", "InventoryRead", "InventoryResult", "InventorySession", "Item", "ItemStatus", "ItemType",
    "LegacyAccession", "LegacyBorrower", "LegacyCatalogue", "Loan", "LoanChannel", "Member", "MemberStatus",
    "MigrationBatch", "NotificationOutbox", "OutboxStatus", "Permission", "RecordSource", "RefreshToken",
    "RfidTag", "Role", "RolePermission", "Shelf", "StaffUser", "SubjectType", "TagStatus", "TagTarget",
]  # fmt: skip
