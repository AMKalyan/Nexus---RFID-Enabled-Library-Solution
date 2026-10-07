from collections.abc import Callable
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.integrations.camera_mock import MockCamera
from app.integrations.credentials_mock import MockCredentialProvider
from app.integrations.legacy_db import DbLegacyConnector
from app.integrations.notify_mock import MockEmail, MockPrint, MockSms

AdapterKind = Literal["email", "sms", "print", "camera", "credentials", "legacy"]
Factory = Callable[[Session | None], Any]

# kind -> {configured value -> factory(session)}. A vendor adapter is added by registering another value.
_FACTORIES: dict[str, dict[str, Factory]] = {
    "legacy": {"db": lambda s: DbLegacyConnector(s)},  # type: ignore[arg-type]
    "email": {"mock": lambda _s: MockEmail()},
    "sms": {"mock": lambda _s: MockSms()},
    "print": {"mock": lambda _s: MockPrint()},
    "camera": {"mock": lambda _s: MockCamera()},
    "credentials": {"mock": lambda s: MockCredentialProvider(s)},  # type: ignore[arg-type]
}


def register(kind: str, name: str, factory: Factory) -> None:
    _FACTORIES.setdefault(kind, {})[name] = factory


def get_adapter(kind: AdapterKind, session: Session | None = None) -> Any:
    configured = getattr(get_settings(), f"adapter_{kind}")
    factory = _FACTORIES.get(kind, {}).get(configured)
    if factory is None:
        raise AppError("ERR_CONFIG", f"No adapter '{configured}' for {kind}", 500)
    return factory(session)
