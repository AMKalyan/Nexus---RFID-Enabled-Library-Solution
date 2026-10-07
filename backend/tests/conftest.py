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
