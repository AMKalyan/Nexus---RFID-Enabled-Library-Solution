import datetime as dt
from decimal import Decimal

import pytest

from app.services.migration.validate import load_rules, normalise, validate

RULES = load_rules()


def ok_row(**kw):
    base = {
        "accession_no": "ACC-100001",
        "barcode": "BC10000001",
        "title": "T",
        "author": "A",
        "isbn": "9780470695067",
        "pub_year": 2010,
        "item_type": "lending",
        "price": Decimal("100"),
    }
    return {**base, **kw}


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"title": None}, "TITLE_MISSING"),
        ({"accession_no": None}, "ACCESSION_MISSING"),
        ({"isbn": "9780470695060"}, "ISBN_CHECKSUM"),
        ({"pub_year": 2099}, "YEAR_RANGE"),
        ({"accession_no": "AC#12"}, "ACCESSION_FORMAT"),
        ({"item_type": "loanable"}, "ITEM_TYPE_UNKNOWN"),
        ({"price": Decimal("-5")}, "PRICE_NEGATIVE"),
    ],
)
def test_fr10_rule_reason_codes(override, code):
    assert code in validate(ok_row(**override), RULES)


def test_fr10_valid_row_has_no_reasons():
    assert validate(ok_row(), RULES) == []


def test_fr10_messy_cells_normalised():
    values, problems = normalise(
        {
            "isbn": 9780470695067.0,
            "acquired_on": 45200,
            "title": "  Wireless   Networks ",
            "item_type": "Reference",
            "accession_no": " acc-100002",
            "pub_year": "2019",
            "price": "1,250.50",
        }
    )
    assert problems == []
    assert values["isbn"] == "9780470695067"
    assert values["acquired_on"] == dt.date(2023, 10, 1)  # Excel serial 45200
    assert values["title"] == "Wireless Networks" and values["item_type"] == "reference"
    assert values["accession_no"] == "ACC-100002" and values["pub_year"] == 2019
    assert values["price"] == Decimal("1250.50")
    assert validate({**ok_row(), **{k: v for k, v in values.items() if v is not None}}, RULES) == []


def test_fr10_unparseable_cells_are_reported_not_crashed():
    values, problems = normalise({"pub_year": "nineteen ninety", "price": "free", "acquired_on": "someday"})
    assert values["pub_year"] is None and values["price"] is None and values["acquired_on"] is None
    assert set(problems) == {"YEAR_INVALID", "PRICE_INVALID", "DATE_INVALID"}


def test_fr10_isbn10_accepted():
    assert validate(ok_row(isbn="080442957X"), RULES) == []
