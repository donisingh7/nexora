import pytest

from app.core.security import sanitize_filename
from app.providers.storage.local import LocalStorageProvider


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
