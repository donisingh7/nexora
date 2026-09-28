import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.max_upload_size_bytes > 0
    assert "application/pdf" in settings.allowed_upload_mime_types
    assert settings.groq_api_key is None
    assert settings.aws_secret_access_key is None


def test_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_BYTES", "1024")
    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.max_upload_size_bytes == 1024


def test_embedding_dimension_matches_initial_database_schema() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, embedding_dimensions=768)
