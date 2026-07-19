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

_ML_WORKER_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ESSENTIA = _ML_WORKER_ROOT / "data" / "models" / "essentia"
_DEFAULT_CONFIG = _ML_WORKER_ROOT / "config.yaml"


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
    model_config = SettingsConfigDict(extra="ignore")

    # Deploy wiring (env); sensible local defaults
    host: str = "0.0.0.0"
    port: int = 50051
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: str | None = None
    qdrant_timeout_seconds: float = 30.0

    # Models / paths (yaml; env can override)
    muq_model_id: str = "OpenMuQ/MuQ-MuLan-large"
    language_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
    language_vector_size: int = 384
    essentia_models_dir: Path = Field(default=_DEFAULT_ESSENTIA)

    # Search / profile tunables (yaml)
    audio_search_weight: float = 0.45
    profile_search_weight: float = 0.55
    baseline_sample: int = 256
    min_sample: int = 8
    min_standout_sigma: float = 1.0
    sigma_full_scale: float = 4.0
    tag_boost_sigma: float = 0.15
    profile_sentence_weight: float = 0.5
    profile_label_relative: float = 0.35

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
        # Priority: init > env > .env > yaml (+ local overlay) > defaults
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
