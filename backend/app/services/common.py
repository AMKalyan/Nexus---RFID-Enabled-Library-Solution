import uuid
from dataclasses import dataclass

from fastapi import Request

from app.core.auth import Principal


@dataclass(frozen=True)
class Actor:
    """Who performed an action, for the audit trail. Services take an Actor; routers build it."""

    type: str  # staff | member | device | external | system
    id: uuid.UUID | None
    ip: str | None = None

    @staticmethod
    def from_principal(principal: Principal, request: Request) -> "Actor":
        return Actor(
            "staff" if principal.typ == "staff" else "member",
            principal.id,
            request.client.host if request.client else None,
        )


SYSTEM = Actor("system", None)
