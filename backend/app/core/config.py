from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_version() -> str:
    for p in (Path(__file__).resolve().parents[3] / "VERSION", Path("/app/VERSION")):
        if p.exists():
            return p.read_text().strip()
    return "0.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore")

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
    run_worker: bool = True
    licence_file: str = "licence.json"
    licence_key: SecretStr = SecretStr("dev-licence-key")


@lru_cache
def get_settings() -> Settings:
    return Settings()
