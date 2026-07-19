from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from ox1audio_backend.shared_constants import allowed_audio_extensions_csv

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG = _BACKEND_ROOT / "config.yaml"


def _config_yaml_files() -> list[Path]:
    """Committed base + optional gitignored personal overlay.

    Order matters: later files win (deep_merge). Env still beats YAML.
    """
    local = _DEFAULT_CONFIG.with_name("config.local.yaml")
    files = [_DEFAULT_CONFIG]
    if local.is_file():
        files.append(local)
    return files


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Deploy wiring / secrets (env)
    database_url: str = "postgresql+asyncpg://ox1audio:ox1audio@127.0.0.1:5432/ox1audio"
    jwt_secret: str = "ox1audio-dev-jwt-secret-change-me"
    cors_origins: str = "http://localhost:5173"

    minio_endpoint: str = "127.0.0.1:9100"
    minio_access_key: str = "ox1audio"
    minio_secret_key: str = "ox1audio-dev-secret"
    minio_bucket: str = "catalog-audio"
    minio_secure: bool = False

    ml_worker_target: str = "127.0.0.1:50051"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"

    # Tunables (config.yaml; env can still override)
    jwt_issuer: str = "ox1audio"
    session_cookie: str = "session"
    session_max_age_seconds: int = 60 * 60 * 24 * 14

    max_upload_bytes: int = 100 * 1024 * 1024
    max_zip_bytes: int = 12 * 1024 * 1024 * 1024
    max_zip_uncompressed_bytes: int = 12 * 1024 * 1024 * 1024
    max_zip_files: int = 2000
    allowed_audio_extensions: str = Field(default_factory=allowed_audio_extensions_csv)
    worker_poll_seconds: float = 2.0

    ml_worker_timeout_seconds: float = 600.0
    ml_search_timeout_seconds: float = 300.0
    presign_expires_seconds: int = 3600

    ollama_model: str = "lfm2.5:8b"
    ollama_title_model: str = "LiquidAI/lfm2.5-1.2b-instruct"
    ollama_timeout_seconds: float = 120.0
    ollama_title_timeout_seconds: float = 30.0
    chat_max_tool_rounds: int = 6
    chat_max_history_messages: int = 20

    @field_validator("qdrant_api_key", mode="before")
    @classmethod
    def _empty_api_key_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(
                settings_cls,
                yaml_file=_config_yaml_files(),
                deep_merge=True,
            ),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
