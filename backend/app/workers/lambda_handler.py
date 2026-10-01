"""AWS Lambda entry point for the ingestion worker, triggered by an SQS event source
mapping. Reuses the same `IngestionWorker` as the local polling worker
(`app.workers.run_ingestion`) - only how a job is found differs: the SQS message names
the job directly (`process_job`) instead of polling for whatever is next
(`process_next`).

Not deployed or invoked in this repository - see `backend/lambda/README.md`.
"""

import asyncio
from uuid import UUID

import structlog

from app.api.dependencies import get_embedding_provider, get_storage_provider
from app.core.config import get_settings
from app.db.session import SessionFactory
from app.services.ingestion import IngestionRetryRequested, IngestionWorker

logger = structlog.get_logger(__name__)


def handler(event: dict, context: object) -> dict:
    return asyncio.run(_handle(event))


async def _handle(event: dict) -> dict:
    settings = get_settings()
    storage = get_storage_provider()
    embeddings = get_embedding_provider()

    processed = 0
    skipped = 0
    retry: IngestionRetryRequested | None = None
    async with SessionFactory() as session:
        worker = IngestionWorker(session, storage, embeddings, settings)
        for record in event.get("Records", []):
            job_id = _job_id_from_record(record)
            if job_id is None:
                logger.warning("sqs_record_missing_job_id", record_keys=list(record.keys()))
                continue
            try:
                did_process = await worker.process_job(job_id)
            except IngestionRetryRequested as exc:
                retry = exc
                continue
            if did_process:
                processed += 1
            else:
                skipped += 1

    if retry is not None:
        # Fail the invocation so SQS redelivers after the visibility timeout; the job is
        # already back in `queued`. Records in the same batch that succeeded are skipped
        # idempotently on redelivery (no longer `queued`).
        raise retry
    return {"processed": processed, "skipped": skipped}


def _job_id_from_record(record: dict) -> UUID | None:
    body = record.get("body")
    if not body:
        return None
    try:
        return UUID(body.strip())
    except ValueError:
        logger.warning("sqs_record_body_not_a_job_id", body=body)
        return None
