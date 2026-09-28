import asyncio
import json
from pathlib import Path, PurePosixPath

from app.providers.storage.interface import ObjectMetadata


class LocalStorageProvider:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path_for(self, key: str) -> Path:
        relative = PurePosixPath(key)
        if not key or relative.is_absolute() or ".." in relative.parts or "\\" in key:
            raise ValueError("Storage key must be a relative POSIX path")
        path = (self._root / Path(*relative.parts)).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("Storage key escapes the storage root")
        return path

    async def upload(self, key: str, content: bytes, content_type: str) -> ObjectMetadata:
        path = self._path_for(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)
        metadata_path = path.with_name(f"{path.name}.metadata.json")
        metadata_json = json.dumps({"content_type": content_type})
        await asyncio.to_thread(metadata_path.write_text, metadata_json, encoding="utf-8")
        return ObjectMetadata(key=key, size_bytes=len(content), content_type=content_type)

    async def read(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path_for(key).read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path_for(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)
        metadata_path = path.with_name(f"{path.name}.metadata.json")
        await asyncio.to_thread(metadata_path.unlink, missing_ok=True)

    async def get_metadata(self, key: str) -> ObjectMetadata | None:
        path = self._path_for(key)
        try:
            size = await asyncio.to_thread(lambda: path.stat().st_size)
        except FileNotFoundError:
            return None
        metadata_path = path.with_name(f"{path.name}.metadata.json")
        try:
            payload = await asyncio.to_thread(metadata_path.read_text, encoding="utf-8")
            content_type = json.loads(payload).get("content_type")
        except FileNotFoundError:
            content_type = None
        return ObjectMetadata(key=key, size_bytes=size, content_type=content_type)
