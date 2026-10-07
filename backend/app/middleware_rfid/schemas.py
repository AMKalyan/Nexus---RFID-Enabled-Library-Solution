import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models import DeviceType

Epc = Annotated[str, StringConstraints(pattern=r"^[0-9A-F]{8,32}$")]
EventType = Literal["Heartbeat", "TagsRead", "GatePassage", "CardTapped", "Footfall"]


class DeviceEventIn(BaseModel):
    """Envelope for every device event (interface design §2.2)."""

    model_config = ConfigDict(extra="forbid")
    event_id: uuid.UUID
    device_type: DeviceType
    type: EventType
    occurred_at: datetime
    epcs: list[Epc] = Field(default_factory=list, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)


class IngestOut(BaseModel):
    status: Literal["accepted", "duplicate"]
    result: dict[str, Any] | None = None


class DeviceIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z0-9-]+$")
    device_type: DeviceType
    name: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    ip_address: str | None = Field(default=None, max_length=45)
    config: dict[str, Any] = Field(default_factory=dict)


class DeviceOut(BaseModel):
    code: str
    device_type: DeviceType
    name: str
    location: str | None
    ip_address: str | None
    config: dict[str, Any]
    status: Literal["online", "offline"]
    last_heartbeat_at: datetime | None


class DeviceCreatedOut(DeviceOut):
    api_key: str


class CommandAckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: str = Field(min_length=1, max_length=64)
    response: dict[str, Any] = Field(default_factory=dict)
