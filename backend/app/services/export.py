"""Report export to CSV and PDF."""

import csv
import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass
class ReportTable:
    name: str
    title: str
    columns: list[str]
    rows: list[list[Any]] = field(default_factory=list)


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    text = str(value)
    # Spreadsheet formula injection: a leading quote makes the cell plain text in Excel/LibreOffice.
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def to_csv(table: ReportTable) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(table.columns)
    writer.writerows([_cell(v) for v in row] for row in table.rows)
    return buf.getvalue().encode("utf-8-sig")


def to_pdf(table: ReportTable) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=table.title, leftMargin=24, rightMargin=24)
    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=7, leading=8)
    data = [[Paragraph(f"<b>{c}</b>", small) for c in table.columns]]
    data += [
        [Paragraph(_cell(v).replace("&", "&amp;").replace("<", "&lt;"), small) for v in r] for r in table.rows
    ]
    grid = Table(data, repeatRows=1)
    grid.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E7FF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    doc.build(
        [
            Paragraph(table.title, styles["Heading2"]),
            Paragraph(f"Generated {generated} · {len(table.rows)} rows", styles["BodyText"]),
            Spacer(1, 8),
            grid,
        ]
    )
    return buf.getvalue()
