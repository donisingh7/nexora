from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Nexora"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://localhost:5432/nexora"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    storage_provider: str = "local"
    local_storage_path: Path = Path(".data/objects")
    s3_bucket: str | None = None
    aws_region: str | None = None
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None

    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.1-8b-instant"

    embedding_provider: Literal["sentence_transformers", "gemini"] = "sentence_transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: Literal[384] = 384
    gemini_api_key: SecretStr | None = None
    gemini_embedding_model: str = "gemini-embedding-2"

    ingestion_queue_url: str | None = None

    max_upload_size_bytes: int = Field(default=25_000_000, gt=0)
    allowed_upload_mime_types: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "text/x-markdown",
        ]
    )
    chunk_size_chars: int = Field(default=1200, gt=0)
    chunk_overlap_chars: int = Field(default=180, ge=0)
    dense_candidate_count: int = Field(default=30, gt=0)
    lexical_candidate_count: int = Field(default=30, gt=0)
    default_retrieval_top_k: int = Field(default=8, gt=0)
    rrf_constant: int = Field(default=60, gt=0)
    reranker_enabled: bool = False
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    max_ingestion_attempts: int = Field(default=3, ge=1)
    ingestion_stale_after_seconds: float = Field(default=600.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
