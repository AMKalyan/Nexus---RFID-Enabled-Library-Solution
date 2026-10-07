from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.integrations.legacy_db import DbLegacyConnector

AdapterKind = Literal["email", "sms", "print", "camera", "credentials", "legacy"]

# kind -> {configured value -> factory(session)}. Mock adapters register here as they are added.
_FACTORIES: dict[str, dict[str, Any]] = {
    "legacy": {"db": DbLegacyConnector},
}


def register(kind: str, name: str, factory: Any) -> None:
    _FACTORIES.setdefault(kind, {})[name] = factory


def get_adapter(kind: AdapterKind, session: Session | None = None) -> Any:
    configured = getattr(get_settings(), f"adapter_{kind}")
    factory = _FACTORIES.get(kind, {}).get(configured)
    if factory is None:
        raise AppError("ERR_CONFIG", f"No adapter '{configured}' for {kind}", 500)
    return factory(session) if session is not None else factory()
