import asyncio
from typing import Any
from uuid import UUID

import structlog

from app.core.config import Settings

logger = structlog.get_logger(__name__)


class SqsJobPublisher:
    """Publishes a job ID to SQS so the worker Lambda is invoked immediately instead of
    waiting on a poll. Uses the AWS SDK default credential chain (the Lambda execution
    role in production); never requires a committed access key."""

    def __init__(self, settings: Settings) -> None:
        if not settings.ingestion_queue_url:
            raise ValueError("INGESTION_QUEUE_URL must be configured to publish to SQS")
        self._queue_url = settings.ingestion_queue_url
        self._region = settings.aws_region
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("sqs", region_name=self._region)
        return self._client

    async def publish(self, job_id: UUID) -> None:
        try:
            await asyncio.to_thread(
                self._get_client().send_message,
                QueueUrl=self._queue_url,
                MessageBody=str(job_id),
            )
        except Exception:
            # The job row is already committed and durable; a polling worker (if one is
            # running) will still pick it up. In a push-only (Lambda) deployment this
            # means the job stays queued until something else triggers the worker - a
            # real gap, logged loudly rather than swallowed, not a lost upload.
            logger.exception("sqs_publish_failed", job_id=str(job_id), queue_url=self._queue_url)
