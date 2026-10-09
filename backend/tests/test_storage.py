import sys

import pytest

from app.core.config import Settings
from app.core.security import sanitize_filename
from app.providers.storage.local import LocalStorageProvider
from app.providers.storage.s3 import S3StorageProvider


@pytest.mark.asyncio
async def test_local_storage_round_trip_and_metadata(tmp_path) -> None:
    storage = LocalStorageProvider(tmp_path)
    uploaded = await storage.upload("workspace/document.txt", b"hello", "text/plain")

    assert uploaded.size_bytes == 5
    assert await storage.read("workspace/document.txt") == b"hello"
    metadata = await storage.get_metadata("workspace/document.txt")
    assert metadata is not None
    assert metadata.content_type == "text/plain"
    assert await storage.get_metadata("missing.txt") is None

    await storage.delete("workspace/document.txt")
    assert await storage.get_metadata("workspace/document.txt") is None


@pytest.mark.asyncio
async def test_local_storage_rejects_path_traversal(tmp_path) -> None:
    storage = LocalStorageProvider(tmp_path)
    with pytest.raises(ValueError):
        await storage.upload("../outside.txt", b"blocked", "text/plain")
    with pytest.raises(ValueError):
        await storage.read("C:\\outside.txt")


def test_filename_sanitization_removes_path_and_hidden_prefix() -> None:
    assert sanitize_filename("../../report final.pdf") == "report final.pdf"
    assert sanitize_filename("..\\.env") == "env"
    assert sanitize_filename("/") == "upload"


class _RecordingBoto3:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def client(self, service: str, **kwargs):
        self.calls.append((service, kwargs))
        return object()


def _s3_settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        storage_provider="s3",
        s3_bucket="test-bucket",
        aws_region="ap-south-1",
        **overrides,
    )


@pytest.fixture
def recording_boto3(monkeypatch) -> _RecordingBoto3:
    fake = _RecordingBoto3()
    monkeypatch.setitem(sys.modules, "boto3", fake)
    return fake


def test_s3_in_lambda_ignores_explicit_keys_and_uses_default_chain(
    monkeypatch, recording_boto3
) -> None:
    """Lambda exports the role's STS key pair as AWS_ACCESS_KEY_ID/SECRET (read by
    Settings); passing them without AWS_SESSION_TOKEN caused InvalidAccessKeyId."""
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "nexora-api")
    storage = S3StorageProvider(
        _s3_settings(aws_access_key_id="ASIATEST", aws_secret_access_key="role-secret")
    )

    storage._get_client()

    assert recording_boto3.calls == [("s3", {"region_name": "ap-south-1"})]


def test_s3_in_lambda_without_keys_uses_default_chain(monkeypatch, recording_boto3) -> None:
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "nexora-ingestion-worker")
    S3StorageProvider(_s3_settings())._get_client()

    assert recording_boto3.calls == [("s3", {"region_name": "ap-south-1"})]


def test_s3_outside_lambda_passes_explicit_local_keys(monkeypatch, recording_boto3) -> None:
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    S3StorageProvider(
        _s3_settings(aws_access_key_id="AKIALOCAL", aws_secret_access_key="local-secret")
    )._get_client()

    assert recording_boto3.calls == [
        (
            "s3",
            {
                "region_name": "ap-south-1",
                "aws_access_key_id": "AKIALOCAL",
                "aws_secret_access_key": "local-secret",
            },
        )
    ]


def test_s3_outside_lambda_without_keys_uses_default_chain(monkeypatch, recording_boto3) -> None:
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    S3StorageProvider(_s3_settings())._get_client()

    assert recording_boto3.calls == [("s3", {"region_name": "ap-south-1"})]
