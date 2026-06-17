"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "PQC Cloud Gateway"
    version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = f"sqlite:///{(DATA / 'gateway.db').as_posix()}"
    secret_key: str = "change-me-in-production-use-long-random-string"
    cors_origins: str = "*"
    openai_api_key: str | None = None
    cloud_public_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_prefix="PQCG_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
