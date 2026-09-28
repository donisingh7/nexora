from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ObjectMetadata:
    key: str
    size_bytes: int
    content_type: str | None = None


class ObjectStorage(Protocol):
    async def upload(self, key: str, content: bytes, content_type: str) -> ObjectMetadata: ...

    async def read(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def get_metadata(self, key: str) -> ObjectMetadata | None: ...
