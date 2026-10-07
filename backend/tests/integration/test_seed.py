"""Legacy seeding commits on its own owner connection (the app role cannot write legacy tables),
so this module truncates the legacy schema before and after."""

import pytest
from sqlalchemy import create_engine, func, select, text

from app.db.models import Bib, Item, LegacyCatalogue, Member
from app.db.seed import mirror_legacy, seed_legacy
from tests.conftest import BASE_OWNER

pytestmark = pytest.mark.db


@pytest.fixture
def legacy_seeded(migrated_db):
    engine = create_engine(BASE_OWNER)

    def truncate():
        with engine.begin() as c:
            c.execute(text("TRUNCATE legacy_ilms.accession, legacy_ilms.catalogue, legacy_ilms.borrower"))

    truncate()
    with engine.begin() as c:
        seed_legacy(c, n_bibs=50, n_borrowers=20)
    yield engine
    truncate()
    engine.dispose()


def test_nfr01_mirror_copies_without_touching_legacy(legacy_seeded, db_session):
    with legacy_seeded.connect() as c:
        before = c.execute(select(func.count()).select_from(LegacyCatalogue)).scalar()
    counts = mirror_legacy(db_session)
    assert counts["bibs"] == 50 and counts["members"] == 20 and counts["items"] >= 50
    assert db_session.scalar(select(func.count()).select_from(Bib).where(Bib.source == "legacy")) == 50
    assert db_session.scalar(select(func.count()).select_from(Item)) == counts["items"]
    assert db_session.scalar(select(func.count()).select_from(Member)) == 20
    assert mirror_legacy(db_session) == {"bibs": 0, "items": 0, "members": 0}
    with legacy_seeded.connect() as c:
        assert c.execute(select(func.count()).select_from(LegacyCatalogue)).scalar() == before


def test_fr10_seeded_isbns_have_valid_check_digits(legacy_seeded):
    from app.db.seed import isbn13_valid

    with legacy_seeded.connect() as c:
        isbns = c.execute(select(LegacyCatalogue.isbn)).scalars().all()
    assert isbns and all(isbn13_valid(i) for i in isbns)
