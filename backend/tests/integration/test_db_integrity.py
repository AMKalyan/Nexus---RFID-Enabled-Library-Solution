import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

pytestmark = pytest.mark.db


def test_nfr01_app_role_can_read_legacy(app_conn):
    assert app_conn.execute(text("SELECT count(*) FROM legacy_ilms.catalogue")).scalar() >= 0


@pytest.mark.parametrize(
    "stmt",
    [
        "UPDATE legacy_ilms.catalogue SET title = 'x'",
        "DELETE FROM legacy_ilms.catalogue",
        "INSERT INTO legacy_ilms.catalogue (bib_no, title) VALUES (99, 'x')",
        "TRUNCATE legacy_ilms.catalogue",
    ],
)
def test_nfr01_app_role_cannot_modify_legacy(app_conn, stmt):
    with pytest.raises(ProgrammingError, match="permission denied"):
        app_conn.execute(text(stmt))


def test_nfr02_audit_log_is_append_only(app_conn):
    app_conn.execute(
        text("INSERT INTO nexus.audit_log (actor_type, action, entity_type) VALUES ('system','test','none')")
    )
    with pytest.raises(ProgrammingError, match="permission denied"):
        app_conn.execute(text("UPDATE nexus.audit_log SET action = 'tampered'"))


def test_fr02_search_vector_maintained_by_trigger(app_conn):
    app_conn.execute(
        text(
            "INSERT INTO nexus.bib (id, title, author, source) "
            "VALUES (gen_random_uuid(), 'Wireless Sensor Networks', 'Rao', 'nexus')"
        )
    )
    hits = app_conn.execute(
        text("SELECT count(*) FROM nexus.bib WHERE search_tsv @@ plainto_tsquery('simple', 'sensor rao')")
    ).scalar()
    assert hits == 1
