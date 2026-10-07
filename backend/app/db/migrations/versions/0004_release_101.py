"""release 1.0.1: maintenance notice setting and release record

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08 00:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

app_setting = sa.table("app_setting", sa.column("key", sa.String), sa.column("value", sa.JSON), schema="nexus")
app_version = sa.table(
    "app_version",
    sa.column("version", sa.String),
    sa.column("alembic_rev", sa.String),
    sa.column("notes", sa.Text),
    schema="nexus",
)


def upgrade() -> None:
    # ON CONFLICT DO NOTHING: re-applying after a rollback, or on a site that already has the rows, is safe.
    op.execute(insert(app_setting).values(key="maintenance_notice", value="").on_conflict_do_nothing())
    op.execute(
        insert(app_version)
        .values(version="1.0.1", alembic_rev="0004", notes="Maintenance notice setting; build notes")
        .on_conflict_do_nothing()
    )


def downgrade() -> None:
    # Only what 1.0.1 introduced is removed; settings that exist in 1.0.0 are left untouched.
    op.execute(app_setting.delete().where(app_setting.c.key == "maintenance_notice"))
    op.execute(app_version.delete().where(app_version.c.version == "1.0.1"))
