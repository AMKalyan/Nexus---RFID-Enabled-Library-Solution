import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _password_policy(value: str) -> str:
    if len(value) < 12 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("password must be at least 12 characters and contain a letter and a digit")
    return value


class UserIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: str = Field(min_length=1, max_length=40)
    password: str = Field(max_length=128)
    smartcard_uid: str | None = Field(default=None, max_length=32, pattern=r"^[0-9A-Fa-f]{4,32}$")

    _check_password = field_validator("password")(_password_policy)


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: str | None = Field(default=None, min_length=1, max_length=40)
    is_active: bool | None = None
    password: str | None = Field(default=None, max_length=128)
    smartcard_uid: str | None = Field(default=None, max_length=32, pattern=r"^[0-9A-Fa-f]{4,32}$")

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str | None) -> str | None:
        return None if value is None else _password_policy(value)


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    email: str | None
    role: str
    is_active: bool
    has_smartcard: bool
    last_login_at: datetime | None


class RoleOut(BaseModel):
    name: str
    permissions: list[str]


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    occurred_at: datetime
    actor_type: str
    actor_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any]
    ip: str | None


class AuditPage(BaseModel):
    total: int
    page: int
    size: int
    items: list[AuditOut]


class SettingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Any
