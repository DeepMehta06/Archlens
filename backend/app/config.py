"""Application settings, driven by environment variables and an optional .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: str = "development"
    APP_NAME: str = "ArchLens"
    APP_VERSION: str = "0.2.0"
    LOG_SENSITIVE_CONTENT: bool = False

    ARCHLENS_DATA_DIR: Path = Path("./data")
    MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024

    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "gemma4:e4b"
    OLLAMA_EMBED_MODEL: str = "embeddinggemma"
    OLLAMA_TIMEOUT_SECONDS: int = 600
    OLLAMA_NUM_CTX: int = 16384
    OLLAMA_NUM_PREDICT: int = 4096
    OLLAMA_THINK: bool = False

    EMBED_QUERY_PREFIX: str = "task: search result | query: "
    EMBED_DOCUMENT_PREFIX: str = "title: none | text: "

    CHUNK_TARGET_CHARS: int = 1500
    EXTRACTION_BATCH_CHARS: int = 5000
    RRF_K: int = 60
    RRF_DENSE_WEIGHT: float = 2.0
    RETRIEVAL_TOP_K: int = 10

    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def data_dir(self) -> Path:
        return self.ARCHLENS_DATA_DIR.resolve()

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{(self.data_dir / 'archlens.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
