from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import dialect

from app.models.enums import IngestionStatus
from app.services.ingestion_jobs import DatabaseIngestionJobQueue, build_recover_stale_statement


@pytest.mark.asyncio
async def test_claim_query_uses_postgres_skip_locked() -> None:
    session = AsyncMock()
    session.scalar.return_value = None
    queue = DatabaseIngestionJobQueue(session)

    assert await queue.claim_next() is None

    statement = session.scalar.await_args.args[0]
    compiled = statement.compile(dialect=dialect())
    sql = str(compiled)
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert IngestionStatus.QUEUED.value in compiled.params.values()


@pytest.mark.asyncio
async def test_completion_is_conditional_on_processing_state() -> None:
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(rowcount=1)
    queue = DatabaseIngestionJobQueue(session)

    assert await queue.mark_completed(uuid4()) is True

    statement = session.execute.await_args_list[0].args[0]
    compiled = statement.compile(dialect=dialect())
    sql = str(compiled)
    assert "UPDATE ingestion_jobs" in sql
    assert IngestionStatus.PROCESSING.value in compiled.params.values()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_failed_requeues_job_for_retry_when_requested() -> None:
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(rowcount=1)
    queue = DatabaseIngestionJobQueue(session)

    assert await queue.mark_failed(uuid4(), "transient error", requeue=True) is True

    statement = session.execute.await_args_list[0].args[0]
    compiled = statement.compile(dialect=dialect())
    sql = str(compiled)
    assert "UPDATE ingestion_jobs" in sql
    assert IngestionStatus.QUEUED.value in compiled.params.values()
    assert "transient error" in compiled.params.values()


@pytest.mark.asyncio
async def test_mark_failed_defaults_to_permanent_failure() -> None:
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(rowcount=1)
    queue = DatabaseIngestionJobQueue(session)

    assert await queue.mark_failed(uuid4(), "fatal error") is True

    statement = session.execute.await_args_list[0].args[0]
    compiled = statement.compile(dialect=dialect())
    assert IngestionStatus.FAILED.value in compiled.params.values()


def test_recover_stale_statement_requeues_processing_jobs_past_threshold() -> None:
    threshold = datetime.now(UTC)
    statement = build_recover_stale_statement(threshold)
    compiled = statement.compile(dialect=dialect())
    sql = str(compiled)

    assert "UPDATE ingestion_jobs" in sql
    assert "locked_at" in sql
    assert IngestionStatus.PROCESSING.value in compiled.params.values()
    assert IngestionStatus.QUEUED.value in compiled.params.values()


@pytest.mark.asyncio
async def test_recover_stale_commits_and_returns_row_count() -> None:
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(rowcount=2)
    queue = DatabaseIngestionJobQueue(session)

    recovered = await queue.recover_stale(600.0)

    assert recovered == 2
    session.commit.assert_awaited_once()
