import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import FineReason, FineStatus, LoanChannel, MemberStatus


class CheckoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    member_card_no: str = Field(min_length=1, max_length=20)
    item: str = Field(min_length=1, max_length=40, description="Accession number, barcode or tag EPC")


class ItemRefIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    item: str = Field(min_length=1, max_length=40)


class RenewIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    item: str | None = Field(default=None, min_length=1, max_length=40)
    loan_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def one_reference(self) -> "RenewIn":
        if (self.item is None) == (self.loan_id is None):
            raise ValueError("give exactly one of item or loan_id")
        return self


class LoanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    item_id: uuid.UUID
    member_id: uuid.UUID
    issued_at: datetime
    due_at: datetime
    returned_at: datetime | None
    renew_count: int
    channel: LoanChannel


class LoanDetailOut(LoanOut):
    accession_no: str
    title: str


class FineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    member_id: uuid.UUID
    loan_id: uuid.UUID | None
    amount: Decimal
    reason: FineReason
    status: FineStatus
    created_at: datetime
    settled_at: datetime | None


class CheckinOut(BaseModel):
    loan: LoanOut
    fine: FineOut | None


class DueOut(BaseModel):
    item_id: uuid.UUID
    accession_no: str
    on_loan: bool
    due_at: datetime | None
    overdue: bool


class ReasonIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=300)


class MemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    card_no: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9-]+$")
    full_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[+0-9 ()-]+$")
    category_code: str = Field(min_length=1, max_length=10)
    notify_email: bool = True
    notify_sms: bool = False
    notify_print: bool = False


class MemberPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[+0-9 ()-]+$")
    category_code: str | None = Field(default=None, min_length=1, max_length=10)
    notify_email: bool | None = None
    notify_sms: bool | None = None
    notify_print: bool | None = None


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    card_no: str
    full_name: str
    email: str | None
    phone: str | None
    category_code: str
    status: MemberStatus
    block_reason: str | None
    notify_email: bool
    notify_sms: bool
    notify_print: bool


class MemberSummaryOut(MemberOut):
    open_fines: Decimal
    fine_limit: Decimal
    open_loans: int
    max_items: int


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    category_code: str
    name: str
    loan_days: int
    max_items: int
    max_renewals: int
    fine_per_day: Decimal
    fine_limit: Decimal
    can_borrow_reference: bool


class PolicyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    loan_days: int | None = Field(default=None, ge=1, le=365)
    max_items: int | None = Field(default=None, ge=0, le=100)
    max_renewals: int | None = Field(default=None, ge=0, le=20)
    fine_per_day: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    fine_limit: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    can_borrow_reference: bool | None = None
