import pytest
from sqlalchemy import text

from tests.conftest import LOCK_TIMEOUT

pytestmark = pytest.mark.db


def test_nfr05_test_database_fails_fast_on_lock_waits(db_session):
    """A blocked test reports the lock instead of hanging until tokens expire (DEF-012)."""
    assert db_session.execute(text("SHOW lock_timeout")).scalar() == LOCK_TIMEOUT
