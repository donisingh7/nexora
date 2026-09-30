from typing import Protocol
from uuid import UUID


class IngestionJobPublisher(Protocol):
    """Notifies something that a job is ready to process. The database row created by
    `DocumentService.upload` is always the durable source of truth; this is purely a
    wake-up signal for a push-based worker (SQS -> Lambda). Local polling mode never
    depends on it."""

    async def publish(self, job_id: UUID) -> None: ...


class NoopJobPublisher:
    """Used whenever `INGESTION_QUEUE_URL` isn't set - the default for local/dev, where
    the polling worker (`app.workers.run_ingestion`) picks up queued jobs on its own."""

    async def publish(self, job_id: UUID) -> None:
        return None
