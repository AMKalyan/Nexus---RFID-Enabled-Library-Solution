"""NFR 02: outside development the API refuses built-in, placeholder or weak secrets (DEF-009)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG = {
    "jwt_secret": "a3f1" * 16,
    "licence_key": "9c2e" * 8,
    "database_url": "postgresql+psycopg://nexus_app:Xq7-strong-app-pass@db:5432/nexus",
    "owner_database_url": "postgresql+psycopg://nexus_owner:Kd9-strong-owner-pass@db:5432/nexus",
}


def settings(**values) -> Settings:
    return Settings(_env_file=None, **values)


def test_nfr02_production_accepts_strong_secrets():
    assert settings(environment="production", **STRONG).environment == "production"


@pytest.mark.parametrize("environment", ["dev", "test"])
def test_nfr02_development_keeps_built_in_defaults(environment):
    assert settings(environment=environment).jwt_secret.get_secret_value() == "dev-only-change-me"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("jwt_secret", "dev-only-change-me"),
        ("jwt_secret", "replace-with-64-random-hex-chars"),
        ("jwt_secret", "short-secret"),
        ("licence_key", "dev-licence-key"),
        ("licence_key", "replace-with-licence-hmac-key"),
        ("database_url", "postgresql+psycopg://nexus_app:devapp@db:5432/nexus"),
        ("owner_database_url", "postgresql+psycopg://nexus_owner:replace-owner-password@db:5432/nexus"),
    ],
)
def test_nfr02_production_refuses_insecure_value(field, value):
    with pytest.raises(ValidationError, match=field.upper()) as err:
        settings(environment="production", **{**STRONG, field: value})
    message = str(err.value)
    secrets = [value, *(v for v in STRONG.values())]
    assert not any(s[-12:] in message for s in secrets)  # no secret, or fragment of one, reaches the log


def test_nfr02_production_is_the_default_inside_the_image():
    from pathlib import Path

    dockerfile = (Path(__file__).parents[2] / "Dockerfile").read_text(encoding="utf-8")
    assert "ENVIRONMENT=production" in dockerfile
