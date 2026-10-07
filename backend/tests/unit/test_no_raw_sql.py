import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2] / "app"
# ADR-0003: raw SQL is allowed only in migrations, model DDL helpers and the seed (operations tooling).
ALLOWED = ("db/migrations", "db/models", "db/seed.py")
PATTERN = re.compile(r"\b(text\(|sa_text\(|exec_driver_sql\()")


def test_adr0003_no_raw_sql_in_application_code():
    offenders = []
    for f in ROOT.rglob("*.py"):
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith(ALLOWED):
            continue
        if PATTERN.search(f.read_text(encoding="utf-8")):
            offenders.append(rel)
    assert offenders == []
