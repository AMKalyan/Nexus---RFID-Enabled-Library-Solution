import uuid
from enum import StrEnum

from sqlalchemy import Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import mapped_column

NEXUS = {"schema": "nexus"}


def pg_enum(enum_cls: type[StrEnum], name: str, schema: str = "nexus") -> Enum:
    """Native PostgreSQL enum that stores the member values."""
    return Enum(enum_cls, name=name, schema=schema, values_callable=lambda e: [m.value for m in e])


def uuid_pk():  # noqa: ANN201
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
