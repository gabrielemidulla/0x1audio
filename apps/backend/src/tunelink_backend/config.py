from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://tunelink:tunelink@127.0.0.1:5432/tunelink"
    jwt_secret: str = "tunelink-dev-jwt-secret-change-me"
    jwt_issuer: str = "tunelink"
    session_cookie: str = "session"
    session_max_age_seconds: int = 60 * 60 * 24 * 14
    cors_origins: str = "http://localhost:5173"

    minio_endpoint: str = "127.0.0.1:9100"
    minio_access_key: str = "tunelink"
    minio_secret_key: str = "tunelink-dev-secret"
    minio_bucket: str = "catalog-audio"
    minio_secure: bool = False

    max_upload_bytes: int = 100 * 1024 * 1024
    # Sized for large catalog dumps (e.g. NCS-full ~9 GB / ~1300 tracks).
    max_zip_bytes: int = 12 * 1024 * 1024 * 1024
    max_zip_uncompressed_bytes: int = 12 * 1024 * 1024 * 1024
    max_zip_files: int = 2000
    allowed_audio_extensions: str = ".mp3,.wav,.flac,.m4a,.ogg,.aac"
    worker_poll_seconds: float = 2.0

    ml_worker_target: str = "127.0.0.1:50051"
    ml_worker_timeout_seconds: float = 600.0
    ml_search_timeout_seconds: float = 300.0
    presign_expires_seconds: int = 3600

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "lfm2.5:8b"
    ollama_timeout_seconds: float = 120.0
    chat_max_tool_rounds: int = 6
    chat_max_history_messages: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
