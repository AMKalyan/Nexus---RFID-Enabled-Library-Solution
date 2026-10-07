"""AC 10: restore from backup after a simulated failed migration or integration change, and prove that the
original data remains intact.

Runs against its own database so a real pg_restore cannot disturb the rest of the suite.
"""

import os
import shutil
import subprocess
import sys
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, insert, select, text, update
from sqlalchemy.engine import make_url

from app.db.models import Bib, Item, ItemStatus, ItemType, LegacyCatalogue, RecordSource
from nexus_ops import backup, integrity
from tests.conftest import BACKEND_DIR, BASE_APP, BASE_OWNER

pytestmark = [pytest.mark.db, pytest.mark.acceptance]
DB = "nexus_restore_test"


@pytest.fixture(scope="module")
def restore_world():
    owner_url = make_url(BASE_OWNER).set(database=DB).render_as_string(hide_password=False)
    app_url = make_url(BASE_APP).set(database=DB).render_as_string(hide_password=False)
    admin = create_engine(make_url(BASE_OWNER).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{DB}"'))
    env = {**os.environ, "OWNER_DATABASE_URL": owner_url, "DATABASE_URL": app_url}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env, cwd=BACKEND_DIR)

    from app.db.seed import seed_legacy

    owner = create_engine(owner_url)
    with owner.begin() as c:
        seed_legacy(c, n_bibs=60, n_borrowers=10)
        bib = uuid.uuid4()
        c.execute(insert(Bib).values(id=bib, title="Original record", source=RecordSource.nexus))
        c.execute(
            insert(Item).values(
                id=uuid.uuid4(),
                bib_id=bib,
                accession_no="ACC-000999",
                barcode="BC00000999",
                item_type=ItemType.lending,
                status=ItemStatus.available,
            )
        )

    def count(model) -> int:
        with owner.connect() as c:
            return c.scalar(select(func.count()).select_from(model)) or 0

    def simulate_bad_migration(rows: int) -> None:
        """A faulty batch: junk items inserted and an existing record damaged."""
        with owner.begin() as c:
            junk = uuid.uuid4()
            c.execute(insert(Bib).values(id=junk, title="JUNK", source=RecordSource.migration))
            c.execute(
                insert(Item),
                [
                    {
                        "id": uuid.uuid4(),
                        "bib_id": junk,
                        "accession_no": f"ACC-9{n:05d}",
                        "barcode": f"BCX{n:07d}",
                        "item_type": ItemType.lending,
                        "status": ItemStatus.available,
                    }
                    for n in range(rows)
                ],
            )
            c.execute(
                update(Item).where(Item.accession_no == "ACC-000999").values(status=ItemStatus.withdrawn)
            )

    def damage_legacy() -> None:
        """An integration change that (wrongly) altered existing ILMS data."""
        with owner.begin() as c:
            c.execute(text("SET ROLE legacy_owner"))
            c.execute(update(LegacyCatalogue).where(LegacyCatalogue.bib_no == 1).values(title="TAMPERED"))

    def item_status(accession: str) -> str:
        with owner.connect() as c:
            return c.scalar(select(Item.status).where(Item.accession_no == accession))

    yield SimpleNamespace(
        owner_url=owner_url,
        count=count,
        simulate_bad_migration=simulate_bad_migration,
        damage_legacy=damage_legacy,
        item_status=item_status,
    )
    owner.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def ops(restore_world, monkeypatch, tmp_path):
    monkeypatch.setenv("OPS_DATABASE_URL", restore_world.owner_url)
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path))
    if shutil.which("pg_dump") is None:
        monkeypatch.setenv("PG_TOOLS_CONTAINER", os.environ.get("PG_TOOLS_CONTAINER", "nexus-db-1"))
    return restore_world


def test_ac10_restore_after_failed_migration_proves_original_data_intact(ops):
    legacy_before = integrity.snapshot()
    items_before = ops.count(Item)
    dump = backup.run_backup("test-pre-change")

    ops.simulate_bad_migration(rows=500)
    assert ops.count(Item) == items_before + 500 and ops.item_status("ACC-000999") == "withdrawn"

    backup.run_restore(dump)
    assert ops.count(Item) == items_before
    assert ops.item_status("ACC-000999") == "available"
    assert integrity.compare(legacy_before, integrity.snapshot()) == []


def test_ac10_integrity_check_detects_a_changed_legacy_row_and_restore_repairs_it(ops):
    before = integrity.snapshot()
    dump = backup.run_backup("test-pre-integration")
    ops.damage_legacy()
    assert integrity.compare(before, integrity.snapshot()) == ["catalogue"]
    backup.run_restore(dump)
    assert integrity.compare(before, integrity.snapshot()) == []


def test_ac10_restore_refuses_tampered_backup(ops):
    dump = backup.run_backup("tamper")
    with open(dump, "ab") as f:
        f.write(b"x")
    with pytest.raises(ValueError, match="checksum"):
        backup.run_restore(dump)


def test_ac10_restore_refuses_backup_without_checksum(ops):
    dump = backup.run_backup("no-checksum")
    os.remove(f"{dump}.sha256")
    with pytest.raises(ValueError, match="checksum"):
        backup.run_restore(dump)


def test_ac10_snapshot_counts_every_legacy_table(ops):
    snap = integrity.snapshot()
    assert set(snap) == {"accession", "borrower", "catalogue"} and snap["catalogue"]["rows"] == 60
