from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document import Document
from app.models.enums import IngestionStatus
from app.models.ingestion_job import IngestionJob


def build_recover_stale_statement(threshold: datetime):
    """Requeue jobs stuck in `processing` past `threshold` (a crashed or killed worker)."""
    return (
        update(IngestionJob)
        .where(
            IngestionJob.status == IngestionStatus.PROCESSING.value,
            IngestionJob.locked_at.is_not(None),
            IngestionJob.locked_at < threshold,
        )
        .values(status=IngestionStatus.QUEUED.value, locked_at=None)
    )


class IngestionJobQueue(Protocol):
    async def claim_next(self) -> IngestionJob | None: ...

    async def claim_job(self, job_id: UUID) -> IngestionJob | None: ...

    async def mark_completed(self, job_id: UUID) -> bool: ...

    async def mark_failed(self, job_id: UUID, reason: str, *, requeue: bool = False) -> bool: ...

    async def recover_stale(self, stale_after_seconds: float) -> int: ...

    async def update_stage(self, job_id: UUID, stage: str) -> None: ...


class DatabaseIngestionJobQueue:
    """PostgreSQL-backed job operations; row locks allow separate worker processes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_next(self) -> IngestionJob | None:
        statement = (
            select(IngestionJob)
            .options(selectinload(IngestionJob.document))
            .where(IngestionJob.status == IngestionStatus.QUEUED.value)
            .order_by(IngestionJob.created_at, IngestionJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = await self._session.scalar(statement)
        if job is None:
            return None
        job.status = IngestionStatus.PROCESSING.value
        job.locked_at = datetime.now(UTC)
        job.attempts += 1
        await self._session.commit()
        return job

    async def claim_job(self, job_id: UUID) -> IngestionJob | None:
        """Claim one specific queued job by id - for an SQS-driven worker, where the
        message names the job rather than "whatever is next". A redelivered message for
        a job that is no longer `queued` (already claimed, completed, or failed) returns
        None rather than erroring, so at-least-once delivery stays idempotent."""
        statement = (
            select(IngestionJob)
            .options(selectinload(IngestionJob.document))
            .where(IngestionJob.id == job_id, IngestionJob.status == IngestionStatus.QUEUED.value)
            .with_for_update(skip_locked=True)
        )
        job = await self._session.scalar(statement)
        if job is None:
            return None
        job.status = IngestionStatus.PROCESSING.value
        job.locked_at = datetime.now(UTC)
        job.attempts += 1
        await self._session.commit()
        return job

    async def mark_completed(self, job_id: UUID) -> bool:
        return await self._finish(job_id, IngestionStatus.COMPLETED.value, None)

    async def mark_failed(self, job_id: UUID, reason: str, *, requeue: bool = False) -> bool:
        status = IngestionStatus.QUEUED.value if requeue else IngestionStatus.FAILED.value
        return await self._finish(job_id, status, reason)

    async def recover_stale(self, stale_after_seconds: float) -> int:
        """Requeue jobs left `processing` after a worker crashed or was killed mid-job."""
        threshold = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
        result = await self._session.execute(build_recover_stale_statement(threshold))
        await self._session.commit()
        return result.rowcount

    async def update_stage(self, job_id: UUID, stage: str) -> None:
        """Record progress within `processing`, for UI feedback only. Guarded to
        `processing` so a stale/duplicate call can never resurrect a finished job."""
        await self._session.execute(
            update(IngestionJob)
            .where(
                IngestionJob.id == job_id,
                IngestionJob.status == IngestionStatus.PROCESSING.value,
            )
            .values(stage=stage)
        )
        await self._session.commit()

    async def _finish(self, job_id: UUID, status: str, reason: str | None) -> bool:
        job_result = await self._session.execute(
            update(IngestionJob)
            .where(
                IngestionJob.id == job_id,
                IngestionJob.status == IngestionStatus.PROCESSING.value,
            )
            .values(status=status, error_message=reason, locked_at=None)
        )
        if job_result.rowcount == 1:
            await self._session.execute(
                update(Document)
                .where(
                    Document.id
                    == select(IngestionJob.document_id)
                    .where(IngestionJob.id == job_id)
                    .scalar_subquery()
                )
                .values(status=status)
            )
        await self._session.commit()
        return job_result.rowcount == 1
