"""Generate a synthetic library export spreadsheet with known defects (A-03).

    python gen_sample.py --rows 20000 --out samples/library-export-20k.xlsx

Writes the workbook and <file>.manifest.json listing the row numbers of every injected defect and
duplicate, so a migration run can be reconciled against ground truth. All data is synthetic (fixed seed).
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
from openpyxl import Workbook

HEADERS = [
    "Accession No",
    "Barcode",
    "Title",
    "Author",
    "ISBN",
    "Publisher",
    "Year",
    "Edition",
    "Subjects",
    "Call No",
    "Shelf",
    "Item Type",
    "Price",
    "Acquired On",
]
DEFECTS = [
    "TITLE_MISSING",
    "ISBN_CHECKSUM",
    "YEAR_RANGE",
    "ACCESSION_FORMAT",
    "ITEM_TYPE_UNKNOWN",
    "PRICE_NEGATIVE",
]
SHELVES = [
    ("A-01", 0, 199),
    ("A-02", 200, 299),
    ("B-01", 300, 399),
    ("B-02", 400, 499),
    ("C-01", 500, 599),
    ("C-02", 600, 699),
    ("D-01", 700, 799),
    ("D-02", 800, 999),
]
EXCEL_EPOCH = date(1899, 12, 30)
FIRST_ACCESSION = 100001  # keeps clear of the seeded legacy range ACC-000001…


@dataclass
class Manifest:
    rows: int
    seed: int
    invalid_rows: list[int] = field(default_factory=list)
    exact_duplicate_rows: list[int] = field(default_factory=list)
    likely_duplicate_rows: list[int] = field(default_factory=list)
    defects: dict[int, str] = field(default_factory=dict)

    @property
    def duplicate_rows(self) -> list[int]:
        return sorted(self.exact_duplicate_rows + self.likely_duplicate_rows)


def isbn13(r: random.Random) -> str:
    digits = [9, 7, 8] + [r.randint(0, 9) for _ in range(9)]
    check = (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10
    return "".join(map(str, [*digits, check]))


def _clean_row(fake: Faker, r: random.Random, n: int) -> list:
    author = fake.name()
    ddc = r.randint(0, 999)
    shelf = next(code for code, lo, hi in SHELVES if lo <= ddc <= hi)
    acquired = date(2000, 1, 1) + timedelta(days=r.randint(0, 9000))
    return [
        f"ACC-{n:06d}",
        f"BC{n:08d}",
        fake.catch_phrase().title(),
        author,
        isbn13(r),
        fake.company(),
        r.randint(1960, 2025),
        r.choice(["1st", "2nd", "3rd", None]),
        "; ".join(fake.words(nb=r.randint(1, 3))),
        f"{ddc:03d}.{r.randint(0, 99):02d} {author.split()[-1][:3].upper()}",
        shelf,
        "reference" if r.random() < 0.1 else "lending",
        round(r.uniform(150, 4500), 2),
        acquired,
    ]


def _messy(row: list, r: random.Random) -> list:
    """Valid but awkward cells, as real exports contain."""
    kind = r.randrange(4)
    if kind == 0:
        row[4] = int(row[4])  # ISBN stored as a number
    elif kind == 1:
        row[13] = (row[13] - EXCEL_EPOCH).days  # Excel date serial
    elif kind == 2:
        row[2] = f"  {row[2]}  "  # stray whitespace
    else:
        row[11] = row[11].upper()  # mixed case
    return row


def _break(row: list, defect: str) -> list:
    if defect == "TITLE_MISSING":
        row[2] = None
    elif defect == "ISBN_CHECKSUM":
        row[4] = row[4][:-1] + str((int(row[4][-1]) + 1) % 10)
    elif defect == "YEAR_RANGE":
        row[6] = 2099
    elif defect == "ACCESSION_FORMAT":
        row[0] = "AC#" + row[0][-2:]
    elif defect == "ITEM_TYPE_UNKNOWN":
        row[11] = "loanable"
    elif defect == "PRICE_NEGATIVE":
        row[12] = -abs(row[12])
    return row


def generate(
    path: Path | str, rows: int = 20000, invalid_rate: float = 0.03, dup_rate: float = 0.02, seed: int = 42
) -> Manifest:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    r = random.Random(seed)  # noqa: S311  # nosec B311 - reproducible synthetic data, not secrets
    manifest = Manifest(rows=rows, seed=seed)

    row_numbers = list(range(1, rows + 1))
    special = r.sample(
        row_numbers[20:], int(rows * (invalid_rate + dup_rate))
    )  # duplicates need earlier rows
    n_invalid = int(rows * invalid_rate)
    invalid, duplicates = set(special[:n_invalid]), special[n_invalid:]
    exact = set(duplicates[: len(duplicates) // 2])
    likely = set(duplicates[len(duplicates) // 2 :])

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Items")
    ws.append(HEADERS)
    written: list[list] = []
    next_accession = FIRST_ACCESSION
    for row_no in row_numbers:
        if row_no in exact or row_no in likely:
            source = r.choice([w for w in written[: row_no - 1] if w is not None])
            if row_no in exact:
                row = list(source)
                manifest.exact_duplicate_rows.append(row_no)
            else:
                row = _clean_row(fake, r, next_accession)
                next_accession += 1
                row[2], row[3], row[6] = source[2], source[3], source[6]  # same title/author/year
                manifest.likely_duplicate_rows.append(row_no)
            written.append(None)  # never copy from a duplicate
        else:
            row = _clean_row(fake, r, next_accession)
            next_accession += 1
            if row_no in invalid:
                defect = r.choice(DEFECTS)
                row = _break(row, defect)
                manifest.invalid_rows.append(row_no)
                manifest.defects[row_no] = defect
                written.append(None)
            else:
                written.append(list(row))
                if r.random() < 0.05:
                    row = _messy(row, r)
        ws.append(row)
    wb.save(path)

    # Make sure every defect kind appears at least once in larger samples (deterministic top-up).
    if rows >= 1000 and set(manifest.defects.values()) != set(DEFECTS):
        return generate(path, rows, invalid_rate, dup_rate, seed + 1000)

    payload = asdict(manifest) | {"duplicate_rows": manifest.duplicate_rows}
    Path(f"{path}.manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--out", default="samples/library-export-20k.xlsx")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    m = generate(args.out, rows=args.rows, seed=args.seed)
    print(
        f"{args.out}: {m.rows} rows, {len(m.invalid_rows)} invalid, {len(m.exact_duplicate_rows)} exact "
        f"duplicates, {len(m.likely_duplicate_rows)} likely duplicates"
    )


if __name__ == "__main__":
    main()
