import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import ItemStatus, ItemType, RecordSource, TagStatus


class BibIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=500)
    author: str | None = Field(default=None, max_length=300)
    isbn: str | None = Field(default=None, max_length=20)
    publisher: str | None = Field(default=None, max_length=300)
    pub_year: int | None = Field(default=None, ge=1000, le=2100)
    edition: str | None = Field(default=None, max_length=100)
    subjects: str | None = Field(default=None, max_length=1000)
    language: str | None = Field(default=None, max_length=20)


class BibPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    author: str | None = Field(default=None, max_length=300)
    isbn: str | None = Field(default=None, max_length=20)
    publisher: str | None = Field(default=None, max_length=300)
    pub_year: int | None = Field(default=None, ge=1000, le=2100)
    edition: str | None = Field(default=None, max_length=100)
    subjects: str | None = Field(default=None, max_length=1000)
    language: str | None = Field(default=None, max_length=20)


class BibOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    author: str | None
    isbn: str | None
    publisher: str | None
    pub_year: int | None
    edition: str | None
    subjects: str | None
    language: str | None
    source: RecordSource


class BibBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    author: str | None
    pub_year: int | None


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    accession_no: str = Field(min_length=1, max_length=20)
    barcode: str = Field(min_length=1, max_length=32)
    call_no: str | None = Field(default=None, max_length=40)
    shelf_code: str | None = Field(default=None, max_length=20)
    item_type: ItemType
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    acquired_on: date | None = None


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    epc: str
    status: TagStatus
    security_bit: bool
    encoded_at: datetime
    retired_at: datetime | None
    retire_reason: str | None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    bib_id: uuid.UUID
    accession_no: str
    barcode: str
    call_no: str | None
    shelf_code: str | None
    item_type: ItemType
    status: ItemStatus
    price: Decimal | None
    acquired_on: date | None
    bib: BibBrief
    active_tag: TagOut | None = None
    tag_history: list[TagOut] = []


class ValidationOut(BaseModel):
    item_id: uuid.UUID
    problems: list[str]


class OpacHit(BaseModel):
    id: uuid.UUID
    title: str
    author: str | None
    publisher: str | None
    pub_year: int | None
    isbn: str | None
    total_copies: int
    available_copies: int


class OpacPage(BaseModel):
    total: int
    page: int
    size: int
    items: list[OpacHit]


class ShelfSpine(BaseModel):
    item_id: uuid.UUID
    accession_no: str
    call_no: str | None
    title: str
    author: str | None
    status: ItemStatus
