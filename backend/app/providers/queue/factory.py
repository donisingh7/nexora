from app.core.config import Settings, get_settings
from app.providers.queue.interface import IngestionJobPublisher, NoopJobPublisher


def create_job_publisher(settings: Settings | None = None) -> IngestionJobPublisher:
    configured = settings or get_settings()
    if configured.ingestion_queue_url:
        from app.providers.queue.sqs import SqsJobPublisher

        return SqsJobPublisher(configured)
    return NoopJobPublisher()
