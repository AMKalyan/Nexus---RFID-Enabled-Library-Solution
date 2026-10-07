"""Field validation shared by cataloguing and the spreadsheet migration."""

import re

ACCESSION_RE = re.compile(r"^[A-Z]{2,5}-\d{4,10}$")


def normalise_isbn(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper()


def isbn13_valid(isbn: str) -> bool:
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    return sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(isbn)) % 10 == 0


def isbn10_valid(isbn: str) -> bool:
    if len(isbn) != 10 or not (isbn[:9].isdigit() and (isbn[9].isdigit() or isbn[9] == "X")):
        return False
    total = sum((10 - i) * (10 if ch == "X" else int(ch)) for i, ch in enumerate(isbn))
    return total % 11 == 0


def isbn_is_valid(value: str) -> bool:
    isbn = normalise_isbn(value)
    return isbn13_valid(isbn) or isbn10_valid(isbn)


def accession_is_valid(value: str) -> bool:
    return bool(ACCESSION_RE.match(value))
