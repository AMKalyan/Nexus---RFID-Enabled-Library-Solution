import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2] / "app"
# ADR-0003: raw SQL is allowed only in migrations, model DDL helpers and the seed (operations tooling).
ALLOWED = ("db/migrations", "db/models", "db/seed.py")
# A bare text()/sa_text() call or sqlalchemy.text(); methods such as Pillow's draw.text() do not count.
PATTERN = re.compile(r"(?<![\w.])(sa_)?text\(|sqlalchemy\.text\(|exec_driver_sql\(")


def test_adr0003_no_raw_sql_in_application_code():
    offenders = []
    for f in ROOT.rglob("*.py"):
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith(ALLOWED):
            continue
        if PATTERN.search(f.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert offenders == []


def test_adr0003_guard_pattern():
    assert PATTERN.search("q = text('SELECT 1')") and PATTERN.search("x = sa_text('a')")
    assert PATTERN.search("conn.exec_driver_sql('x')") and PATTERN.search("sqlalchemy.text('x')")
    assert not PATTERN.search("draw.text((0, 0), 'label')") and not PATTERN.search("context_text(")
