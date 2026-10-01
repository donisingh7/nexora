import uuid
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.ingestion.parsers import ParsedUnit
from app.services.ingestion import IngestionRetryRequested, IngestionWorker


class FakeEmbeddingProvider:
    dimensions = 384

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(index)] * self.dimensions for index, _ in enumerate(texts)]


class FakeQueue:
    def __init__(self, job, job_by_id=None) -> None:
        self.job = job
        self.job_by_id = job_by_id if job_by_id is not None else {}
        self.failed = None
        self.requeued = None
        self.completed = False
        self.recover_stale_calls = 0
        self.stages: list[str] = []

    async def claim_next(self):
        return self.job

    async def claim_job(self, job_id):
        return self.job_by_id.get(job_id)

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

    async def update_stage(self, job_id, stage):
        self.stages.append(stage)


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
    assert queue.stages == ["parsing", "chunking", "embedding", "indexing"]
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


@pytest.mark.asyncio
async def test_process_job_processes_a_specific_queued_job() -> None:
    job = make_job()
    session = FakeSession()
    queue = FakeQueue(job, job_by_id={job.id: job})
    worker = IngestionWorker(
        session,
        FakeStorage(b"source"),
        FakeEmbeddingProvider(),
        Settings(_env_file=None),
        queue=queue,
        parsers=FakeParserRegistry(),
    )

    assert await worker.process_job(job.id) is True
    assert queue.completed is True
    assert queue.stages == ["parsing", "chunking", "embedding", "indexing"]


@pytest.mark.asyncio
async def test_process_job_is_idempotent_for_a_redelivered_sqs_message() -> None:
    """A job that is no longer `queued` (already claimed/completed/failed elsewhere)
    must be skipped, not reprocessed - SQS delivers at-least-once, sometimes twice."""
    job = make_job()
    session = FakeSession()
    queue = FakeQueue(job, job_by_id={})  # claim_job finds nothing - already handled
    worker = IngestionWorker(
        session,
        FakeStorage(b"source"),
        FakeEmbeddingProvider(),
        Settings(_env_file=None),
        queue=queue,
        parsers=FakeParserRegistry(),
    )

    assert await worker.process_job(job.id) is False
    assert queue.completed is False
    assert queue.failed is None
    assert queue.stages == []


class BrokenStorage:
    async def read(self, key: str) -> bytes:
        raise FileNotFoundError("object missing")


def make_broken_worker(queue, session, *, max_attempts: int = 3) -> IngestionWorker:
    return IngestionWorker(
        session,
        BrokenStorage(),
        FakeEmbeddingProvider(),
        Settings(_env_file=None, max_ingestion_attempts=max_attempts),
        queue=queue,
        parsers=FakeParserRegistry(),
    )


@pytest.mark.asyncio
async def test_process_job_requeues_then_raises_retry_when_attempts_remain() -> None:
    """Push mode has no poller: a requeued job must surface as an error so the SQS
    message is redelivered rather than deleted - and only after the DB requeue."""
    job = make_job(attempts=1)
    session = FakeSession()
    queue = FakeQueue(job, job_by_id={job.id: job})
    worker = make_broken_worker(queue, session)

    with pytest.raises(IngestionRetryRequested) as excinfo:
        await worker.process_job(job.id)

    assert excinfo.value.job_id == job.id
    assert queue.requeued is True
    assert queue.failed == "FileNotFoundError: object missing"
    assert queue.completed is False
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_process_job_marks_failed_without_retry_when_attempts_exhausted() -> None:
    job = make_job(attempts=3)
    session = FakeSession()
    queue = FakeQueue(job, job_by_id={job.id: job})
    worker = make_broken_worker(queue, session, max_attempts=3)

    assert await worker.process_job(job.id) is True
    assert queue.requeued is False
    assert queue.failed == "FileNotFoundError: object missing"


@pytest.mark.asyncio
async def test_process_next_swallows_retryable_failure_for_local_poller() -> None:
    """Poll mode finds the requeued job itself, so a retryable failure must not raise
    out of `process_next` and kill `run_forever`."""
    job = make_job(attempts=1)
    queue = FakeQueue(job)
    worker = make_broken_worker(queue, FakeSession())

    assert await worker.process_next() is True
    assert queue.requeued is True


class _FakeSessionFactory:
    async def __aenter__(self):
        return FakeSession()

    async def __aexit__(self, *exc) -> None:
        return None


def _patch_lambda_worker(monkeypatch, job_by_id, storage) -> FakeQueue:
    from app.workers import lambda_handler

    queue = FakeQueue(None, job_by_id=job_by_id)

    def build_worker(session, _storage, embeddings, settings):
        return IngestionWorker(
            session,
            storage,
            embeddings,
            Settings(_env_file=None, max_ingestion_attempts=3),
            queue=queue,
            parsers=FakeParserRegistry(),
        )

    monkeypatch.setattr(lambda_handler, "SessionFactory", _FakeSessionFactory)
    monkeypatch.setattr(lambda_handler, "get_storage_provider", lambda: storage)
    monkeypatch.setattr(lambda_handler, "get_embedding_provider", FakeEmbeddingProvider)
    monkeypatch.setattr(lambda_handler, "IngestionWorker", build_worker)
    return queue


def _sqs_event(*job_ids) -> dict:
    return {"Records": [{"body": str(job_id)} for job_id in job_ids]}


def test_lambda_handler_fails_invocation_on_retryable_failure(monkeypatch) -> None:
    from app.workers.lambda_handler import handler

    job = make_job(attempts=1)
    queue = _patch_lambda_worker(monkeypatch, {job.id: job}, BrokenStorage())

    with pytest.raises(IngestionRetryRequested):
        handler(_sqs_event(job.id), None)
    assert queue.requeued is True


def test_lambda_handler_succeeds_on_final_failure(monkeypatch) -> None:
    from app.workers.lambda_handler import handler

    job = make_job(attempts=3)
    queue = _patch_lambda_worker(monkeypatch, {job.id: job}, BrokenStorage())

    assert handler(_sqs_event(job.id), None) == {"processed": 1, "skipped": 0}
    assert queue.requeued is False


def test_lambda_handler_skips_redelivered_non_queued_job(monkeypatch) -> None:
    from app.workers.lambda_handler import handler

    job = make_job()
    queue = _patch_lambda_worker(monkeypatch, {}, FakeStorage(b"source"))

    assert handler(_sqs_event(job.id), None) == {"processed": 0, "skipped": 1}
    assert queue.failed is None
    assert queue.completed is False


def test_lambda_handler_succeeds_on_successful_ingestion(monkeypatch) -> None:
    from app.workers.lambda_handler import handler

    job = make_job()
    queue = _patch_lambda_worker(monkeypatch, {job.id: job}, FakeStorage(b"source"))

    assert handler(_sqs_event(job.id), None) == {"processed": 1, "skipped": 0}
    assert queue.completed is True
