from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

DEV_ENVIRONMENTS = {"dev", "test"}
DEV_PASSWORDS = {"devapp", "devowner"}
MIN_SECRET_LENGTH = 32


def _read_version() -> str:
    for p in (Path(__file__).resolve().parents[3] / "VERSION", Path("/app/VERSION")):
        if p.exists():
            return p.read_text().strip()
    return "0.0.0"


class Settings(BaseSettings):
    # hide_input_in_errors keeps secrets out of validation messages and therefore out of startup logs.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    environment: str = "dev"
    app_version: str = _read_version()
    database_url: str = "postgresql+psycopg://nexus_app:devapp@localhost:5433/nexus"
    owner_database_url: str = "postgresql+psycopg://nexus_owner:devowner@localhost:5433/nexus"
    jwt_secret: SecretStr = SecretStr("dev-only-change-me")
    access_token_minutes: int = 15
    refresh_token_hours: int = 8
    log_level: str = "INFO"
    cors_origins: list[str] = []
    adapter_email: str = "mock"
    adapter_sms: str = "mock"
    adapter_print: str = "mock"
    adapter_camera: str = "mock"
    adapter_credentials: str = "mock"
    adapter_legacy: str = "db"
    outbox_dir: str = "outbox"
    backup_dir: str = "../ops/backups"
    rate_limit_auth: str = "10/minute"
    rate_limit_devices: str = "600/minute"
    rate_limit_migration: str = "10/minute"
    upload_max_mb: int = 25
    sip2_listener_enabled: bool = False
    sip2_host: str = "127.0.0.1"  # set to 0.0.0.0 inside the container, with SIP2_ALLOWED_HOSTS
    sip2_port: int = 6001
    sip2_allowed_hosts: list[str] = []
    run_worker: bool = True
    licence_file: str = "licence.json"
    licence_key: SecretStr = SecretStr("dev-licence-key")

    @model_validator(mode="after")
    def _refuse_insecure_secrets(self) -> "Settings":
        """Outside development, built-in, placeholder or short secrets stop the API from starting (NFR 02)."""
        if self.environment in DEV_ENVIRONMENTS:
            return self
        problems = []
        for name, secret in (("JWT_SECRET", self.jwt_secret), ("LICENCE_KEY", self.licence_key)):
            value = secret.get_secret_value()
            if value.startswith(("dev-", "replace")) or len(value) < MIN_SECRET_LENGTH:
                problems.append(
                    f"{name} must be a generated value of at least {MIN_SECRET_LENGTH} characters"
                )
        for name, url in (
            ("DATABASE_URL", self.database_url),
            ("OWNER_DATABASE_URL", self.owner_database_url),
        ):
            password = make_url(url).password or ""
            if password in DEV_PASSWORDS or password.startswith("replace"):
                problems.append(f"{name} uses a development or placeholder password")
        if problems:
            raise ValueError(
                f"Insecure configuration for environment '{self.environment}': " + "; ".join(problems)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
