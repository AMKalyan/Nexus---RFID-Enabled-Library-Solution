"""Roles, permissions and circulation policies

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05 09:00:00
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Stable role ids so later migrations and fixtures can refer to them.
_NS = uuid.UUID("6f1c2a4e-1d1b-4c52-9a0e-6b3c5d0a7e11")
ROLES = ["Admin", "Librarian", "CirculationClerk", "Auditor", "Patron"]
ROLE_IDS = {name: uuid.uuid5(_NS, name) for name in ROLES}

PERMISSIONS = {
    "catalog.read": "Read catalogue records",
    "catalog.write": "Create and edit catalogue records",
    "tagging.write": "Associate and retire RFID tags",
    "members.read": "Read member records",
    "members.write": "Create and edit members",
    "members.block": "Block and unblock members",
    "member.pii.read": "See member personal data unmasked",
    "circulation.read": "Read loans and due dates",
    "circulation.checkout": "Issue items",
    "circulation.checkin": "Return items",
    "circulation.renew": "Renew loans",
    "fines.read": "Read fines",
    "fines.write": "Settle and waive fines",
    "inventory.read": "Read inventory sessions",
    "inventory.write": "Run inventory sessions",
    "gate.read": "Read security gate events",
    "devices.read": "Read device status",
    "notifications.read": "Read the notification outbox",
    "reports.read": "Dashboard and reports",
    "audit.read": "Read the audit log",
    "migration.run": "Run data migrations",
    "admin.users.write": "Manage staff users",
    "admin.roles.write": "Manage roles",
    "admin.policies.write": "Manage circulation policies",
    "admin.settings.write": "Manage system settings",
    "admin.devices.write": "Manage devices",
    "admin.health": "Detailed health information",
}

LIBRARIAN = [
    "catalog.read", "catalog.write", "tagging.write", "members.read", "members.write", "members.block",
    "member.pii.read", "circulation.read", "circulation.checkout", "circulation.checkin", "circulation.renew",
    "fines.read", "fines.write", "inventory.read", "inventory.write", "gate.read", "devices.read",
    "notifications.read", "reports.read",
]  # fmt: skip
CLERK = [
    "catalog.read", "members.read", "member.pii.read", "circulation.read", "circulation.checkout",
    "circulation.checkin", "circulation.renew", "fines.read", "gate.read",
]  # fmt: skip
AUDITOR = [
    "catalog.read", "members.read", "circulation.read", "fines.read", "inventory.read", "gate.read",
    "devices.read", "notifications.read", "reports.read", "audit.read",
]  # fmt: skip
GRANTS = {
    "Admin": list(PERMISSIONS),
    "Librarian": LIBRARIAN,
    "CirculationClerk": CLERK,
    "Auditor": AUDITOR,
    "Patron": ["catalog.read"],
}

POLICIES = [
    # category, name, loan_days, max_items, max_renewals, fine_per_day, fine_limit, can_borrow_reference
    ("UG", "Undergraduate", 14, 4, 2, "2.00", "100.00", False),
    ("PG", "Postgraduate", 21, 6, 3, "2.00", "150.00", False),
    ("FAC", "Faculty", 60, 15, 5, "0.00", "500.00", True),
    ("STAFF", "Library staff", 30, 8, 3, "1.00", "200.00", False),
]

role_t = sa.table("role", sa.column("id", sa.UUID()), sa.column("name", sa.String), schema="nexus")
perm_t = sa.table("permission", sa.column("code", sa.String), sa.column("description", sa.Text), schema="nexus")
rp_t = sa.table(
    "role_permission", sa.column("role_id", sa.UUID()), sa.column("permission_code", sa.String), schema="nexus"
)
policy_t = sa.table(
    "circ_policy",
    sa.column("category_code", sa.String),
    sa.column("name", sa.Text),
    sa.column("loan_days", sa.Integer),
    sa.column("max_items", sa.Integer),
    sa.column("max_renewals", sa.Integer),
    sa.column("fine_per_day", sa.Numeric),
    sa.column("fine_limit", sa.Numeric),
    sa.column("can_borrow_reference", sa.Boolean),
    schema="nexus",
)


def upgrade() -> None:
    op.bulk_insert(role_t, [{"id": ROLE_IDS[n], "name": n} for n in ROLES])
    op.bulk_insert(perm_t, [{"code": c, "description": d} for c, d in PERMISSIONS.items()])
    op.bulk_insert(
        rp_t, [{"role_id": ROLE_IDS[role], "permission_code": p} for role, perms in GRANTS.items() for p in perms]
    )
    op.bulk_insert(
        policy_t,
        [
            {
                "category_code": c, "name": n, "loan_days": d, "max_items": m, "max_renewals": r,
                "fine_per_day": Decimal(f), "fine_limit": Decimal(lim), "can_borrow_reference": ref,
            }
            for c, n, d, m, r, f, lim, ref in POLICIES
        ],
    )  # fmt: skip


def downgrade() -> None:
    op.execute(policy_t.delete().where(policy_t.c.category_code.in_([p[0] for p in POLICIES])))
    op.execute(rp_t.delete().where(rp_t.c.role_id.in_(list(ROLE_IDS.values()))))
    op.execute(perm_t.delete().where(perm_t.c.code.in_(list(PERMISSIONS))))
    op.execute(role_t.delete().where(role_t.c.id.in_(list(ROLE_IDS.values()))))
