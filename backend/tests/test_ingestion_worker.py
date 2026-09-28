import uuid
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.ingestion.parsers import ParsedUnit
from app.services.ingestion import IngestionWorker


class FakeEmbeddingProvider:
    dimensions = 384

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index)] * self.dimensions for index, _ in enumerate(texts)]


class FakeQueue:
    def __init__(self, job) -> None:
        self.job = job
        self.failed = None
        self.requeued = None
        self.completed = False
        self.recover_stale_calls = 0

    async def claim_next(self):
        return self.job

    async def mark_completed(self, job_id):
        self.completed = True
        return True

    async def mark_failed(self, job_id, reason, *, requeue=False):
        self.failed = reason
        self.requeued = requeue
        return True

    async def recover_stale(self, stale_after_seconds):
        self.recover_stale_calls += 1
        return 0


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.executed = []
        self.commits = 0
        self.rollbacks = 0

    def add_all(self, records) -> None:
        self.added.extend(records)

    async def execute(self, statement) -> None:
        self.executed.append(statement)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeStorage:
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def read(self, key: str) -> bytes:
        return self.content


class FakeParserRegistry:
    def parse(self, filename: str, content: bytes):
        return [ParsedUnit("indexed text", page_number=2)]


def make_job(attempts: int = 1):
    document = SimpleNamespace(
        id=uuid.uuid4(), filename="file.txt", storage_key="workspace/file.txt", status="processing"
    )
    return SimpleNamespace(
        id=uuid.uuid4(), document_id=document.id, document=document, attempts=attempts
    )


@pytest.mark.asyncio
async def test_worker_processes_and_persists_chunks() -> None:
    job = make_job()
    session = FakeSession()
    queue = FakeQueue(job)
    worker = IngestionWorker(
        session,
        FakeStorage(b"source"),
        FakeEmbeddingProvider(),
        Settings(_env_file=None),
        queue=queue,
        parsers=FakeParserRegistry(),
    )

    assert await worker.process_next() is True
    assert queue.completed is True
    assert queue.failed is None
    assert queue.recover_stale_calls == 1
    assert len(session.added) == 1
    assert session.added[0].chunk_text == "indexed text"
    assert len(session.added[0].embedding) == 384
    assert session.commits == 0


@pytest.mark.asyncio
async def test_worker_fails_permanently_after_max_attempts() -> None:
    job = make_job(attempts=3)
    session = FakeSession()
    queue = FakeQueue(job)

    class BrokenStorage:
        async def read(self, key: str) -> bytes:
            raise FileNotFoundError("object missing")

    worker = IngestionWorker(
        session,
        BrokenStorage(),
        FakeEmbeddingProvider(),
        Settings(_env_file=None),
        queue=queue,
        parsers=FakeParserRegistry(),
    )

    assert await worker.process_next() is True
    assert queue.completed is False
    assert queue.failed == "FileNotFoundError: object missing"
    assert queue.requeued is False
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_worker_requeues_job_for_retry_when_attempts_remain() -> None:
    job = make_job(attempts=1)
    session = FakeSession()
    queue = FakeQueue(job)

    class BrokenStorage:
        async def read(self, key: str) -> bytes:
            raise FileNotFoundError("object missing")

    worker = IngestionWorker(
        session,
        BrokenStorage(),
        FakeEmbeddingProvider(),
        Settings(_env_file=None, max_ingestion_attempts=3),
        queue=queue,
        parsers=FakeParserRegistry(),
    )

    assert await worker.process_next() is True
    assert queue.completed is False
    assert queue.failed == "FileNotFoundError: object missing"
    assert queue.requeued is True
    assert session.rollbacks == 1
