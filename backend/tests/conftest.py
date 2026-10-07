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
