"""Profile a source spreadsheet before migration (SOP §9 Stage 6: "Profile the sample spreadsheet").

python profile_sheet.py samples/library-export-20k.xlsx > ../docs/05-data-migration/profile-report.md
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook


def profile(path: Path | str) -> dict:
    ws = load_workbook(path, read_only=True, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    headers = [str(h) for h in next(rows)]
    stats = {h: {"nulls": 0, "values": Counter(), "types": Counter()} for h in headers}
    count = 0
    for row in rows:
        count += 1
        for header, value in zip(headers, row, strict=False):
            s = stats[header]
            if value is None or (isinstance(value, str) and not value.strip()):
                s["nulls"] += 1
                continue
            s["types"][type(value).__name__] += 1
            if len(s["values"]) < 50_000:
                s["values"][str(value).strip()] += 1
    return {
        "file": str(path),
        "rows": count,
        "columns": {
            h: {
                "nulls": s["nulls"],
                "distinct": len(s["values"]),
                "types": dict(s["types"]),
                "samples": [v for v, _ in s["values"].most_common(3)],
                "repeated": sum(1 for _, n in s["values"].items() if n > 1),
            }
            for h, s in stats.items()
        },
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# Source Profile Report",
        "",
        f"- File: `{Path(report['file']).name}`",
        f"- Data rows: {report['rows']:,}",
        "",
        "| Column | Empty | Distinct | Values repeated | Cell types | Most common values |",
        "|---|---|---|---|---|---|",
    ]
    for name, c in report["columns"].items():
        types = ", ".join(f"{t} {n:,}" for t, n in c["types"].items())
        samples = "; ".join(s[:30].replace("|", "/") for s in c["samples"])
        lines.append(
            f"| {name} | {c['nulls']:,} | {c['distinct']:,} | {c['repeated']:,} | {types} | {samples} |"
        )
    lines += [
        "",
        "Observations to act on in the validation rules:",
        "- Columns with mixed cell types (for example ISBN stored as both text and number, or dates stored as "
        "Excel serial numbers) are normalised before validation.",
        "- Repeated accession numbers indicate exact duplicates; they are excluded and reported.",
        "- Empty mandatory cells (title, accession number) are rejected with a reason code.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(to_markdown(profile(sys.argv[1])))
