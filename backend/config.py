"""Application configuration.

All settings are environment-variable / .env driven so the whole stack
remains plug-and-play with sensible defaults.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    """Runtime configuration."""

    # --- core ---
    app_name: str = "PQC Migration Gateway"
    version: str = "0.1.0"
    env: str = Field(default="dev", description="dev / prod")

    # --- server ---
    host: str = "0.0.0.0"
    port: int = 8080

    # --- database ---
    database_url: str = f"sqlite+aiosqlite:///{(DATA_DIR / 'gateway.db').as_posix()}"

    # --- security ---
    secret_key: str = Field(
        default="change-me-in-production-this-is-only-a-default",
        description="JWT signing key. Auto-rotate on first run in production.",
    )
    access_token_minutes: int = 60 * 24

    # --- networking / discovery ---
    discovery_interval_sec: int = 60
    discovery_subnet: str | None = Field(
        default=None,
        description="Override auto-detected subnet, e.g. '192.168.1.0/24'.",
    )
    discovery_interface: str | None = Field(
        default=None,
        description="Override auto-detected interface by name (e.g. 'Wi-Fi').",
    )
    common_ports: tuple[int, ...] = (
        22, 23, 53, 80, 102, 443, 502, 1883, 5060, 8080, 8443, 8883,
    )

    # --- PQC engine ---
    kem_algorithm: str = "ML-KEM-768"
    sig_algorithm: str = "ML-DSA-65"
    aead_algorithm: str = "AES-256-GCM"
    hybrid_classical: bool = True  # X25519 hybrid

    # --- gateway ---
    gateway_listen_base_port: int = 18000
    gateway_max_sessions: int = 1024
    rekey_after_bytes: int = 64 * 1024 * 1024 * 1024  # 64 GiB
    rekey_after_seconds: int = 3600

    # --- ui ---
    static_dir: Path = PROJECT_ROOT / "frontend" / "dist"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="PQCG_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
