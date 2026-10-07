"""NFR 06, AC 09: every schema migration can be applied and reverted, so a release can be rolled back."""

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.conftest import BACKEND_DIR, BASE_APP, BASE_OWNER

pytestmark = pytest.mark.db
DB = "nexus_migration_test"


@pytest.fixture(scope="module")
def scratch_db():
    owner_url = make_url(BASE_OWNER).set(database=DB).render_as_string(hide_password=False)
    app_url = make_url(BASE_APP).set(database=DB).render_as_string(hide_password=False)
    admin = create_engine(make_url(BASE_OWNER).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{DB}"'))
    env = {**os.environ, "OWNER_DATABASE_URL": owner_url, "DATABASE_URL": app_url}

    def alembic(*args: str) -> None:
        subprocess.run([sys.executable, "-m", "alembic", *args], check=True, env=env, cwd=BACKEND_DIR)

    engine = create_engine(owner_url)
    yield alembic, engine
    engine.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)'))
    admin.dispose()


def release_rows(engine) -> tuple[int, int]:
    with engine.connect() as c:
        banner = c.scalar(text("SELECT count(*) FROM nexus.app_setting WHERE key = 'maintenance_notice'"))
        version = c.scalar(text("SELECT count(*) FROM nexus.app_version WHERE version = '1.0.1'"))
    return banner or 0, version or 0


def test_ac09_release_101_migration_upgrades_downgrades_and_reapplies(scratch_db):
    alembic, engine = scratch_db
    alembic("upgrade", "head")
    assert release_rows(engine) == (1, 1)
    alembic("downgrade", "0003")
    assert release_rows(engine) == (0, 0)
    alembic("upgrade", "head")
    assert release_rows(engine) == (1, 1)
