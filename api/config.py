"""Application configuration (env-driven, Render/Streamlit friendly)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "PQC Migration Gateway"
    version: str = "2.0.0"

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database: SQLite locally; set DATABASE_URL to a Postgres URL on Render.
    database_url: str = f"sqlite:///{(DATA / 'pqcg.db').as_posix()}"

    # Security
    secret_key: str = "dev-only-change-me"
    cors_origins: str = "*"

    # PQC engine: auto | demo | liboqs
    pqc_backend: str = "auto"

    # Optional AI
    openai_api_key: str | None = None

    # Public URL of this API (used in connector download snippet)
    public_url: str = "http://127.0.0.1:8000"

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_prefix="PQCG_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    import os

    settings = Settings()
    # Honor Render's standard DATABASE_URL / PORT if present (no PQCG_ prefix).
    db = os.getenv("DATABASE_URL")
    if db:
        # SQLAlchemy needs postgresql:// not postgres://
        settings.database_url = db.replace("postgres://", "postgresql://", 1)
    port = os.getenv("PORT")
    if port and port.isdigit():
        settings.api_port = int(port)
    return settings
