"""Cell normalisation and rule-based validation for migrated rows."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.services.validation import isbn_is_valid, normalise_isbn

HERE = Path(__file__).resolve().parent
EXCEL_EPOCH = date(1899, 12, 30)
TEXT_FIELDS = ("barcode", "title", "author", "publisher", "edition", "subjects", "call_no", "shelf_code")


@lru_cache
def load_rules() -> dict[str, Any]:
    return yaml.safe_load((HERE / "rules.yaml").read_text(encoding="utf-8"))


@lru_cache
def load_mapping() -> dict[str, str]:
    return yaml.safe_load((HERE / "mapping.yaml").read_text(encoding="utf-8"))["columns"]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _isbn(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return normalise_isbn(str(value)) or None


def _year(value: Any, problems: list[str]) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except ValueError:
        problems.append("YEAR_INVALID")
        return None


def _price(value: Any, problems: list[str]) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip()).quantize(Decimal("0.01"))
    except InvalidOperation:
        problems.append("PRICE_INVALID")
        return None


def _date(value: Any, problems: list[str]) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, int | float):
        return EXCEL_EPOCH + timedelta(days=int(value))  # Excel serial date
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC).date()
        except ValueError:
            continue
    problems.append("DATE_INVALID")
    return None


def normalise(cells: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Turn raw cells into typed values. Unparseable values become None plus a reason code."""
    problems: list[str] = []
    values: dict[str, Any] = {f: _text(cells.get(f)) for f in TEXT_FIELDS}
    accession = _text(cells.get("accession_no"))
    values["accession_no"] = accession.upper() if accession else None
    item_type = _text(cells.get("item_type"))
    values["item_type"] = item_type.lower() if item_type else None
    values["isbn"] = _isbn(cells.get("isbn"))
    values["pub_year"] = _year(cells.get("pub_year"), problems)
    values["price"] = _price(cells.get("price"), problems)
    values["acquired_on"] = _date(cells.get("acquired_on"), problems)
    return values, problems


def validate(row: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for field, code in rules.get("required", {}).items():
        if not row.get(field):
            reasons.append(code)
    for field, spec in rules.get("patterns", {}).items():
        value = row.get(field)
        if value and not re.match(spec["regex"], str(value)):
            reasons.append(spec["code"])
    for field, spec in rules.get("ranges", {}).items():
        value = row.get(field)
        if value is None:
            continue
        upper = date.today().year if spec.get("max") == "current_year" else spec.get("max")
        if ("min" in spec and value < spec["min"]) or (upper is not None and value > upper):
            reasons.append(spec["code"])
    for field, spec in rules.get("allowed", {}).items():
        value = row.get(field)
        if value and value not in spec["values"]:
            reasons.append(spec["code"])
    isbn_rule = rules.get("isbn")
    if isbn_rule and row.get(isbn_rule["field"]) and not isbn_is_valid(row[isbn_rule["field"]]):
        reasons.append(isbn_rule["code"])
    return reasons
