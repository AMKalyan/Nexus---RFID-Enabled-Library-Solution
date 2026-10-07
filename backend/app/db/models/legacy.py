"""Simulated existing ILMS tables. Owned by legacy_owner; the application role can only SELECT."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

LEGACY = {"schema": "legacy_ilms"}


class LegacyCatalogue(Base):
    __tablename__ = "catalogue"
    __table_args__ = LEGACY

    bib_no: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    isbn: Mapped[str | None] = mapped_column(String(17))
    pub_year: Mapped[int | None]


class LegacyAccession(Base):
    __tablename__ = "accession"
    __table_args__ = LEGACY

    acc_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    bib_no: Mapped[int] = mapped_column(ForeignKey("legacy_ilms.catalogue.bib_no"))
    call_no: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10))


class LegacyBorrower(Base):
    __tablename__ = "borrower"
    __table_args__ = LEGACY

    borrower_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(10))
