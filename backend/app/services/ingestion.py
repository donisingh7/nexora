import time

import structlog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.ingestion.chunking import TextChunker
from app.ingestion.parsers import ParserRegistry
from app.models.document_chunk import DocumentChunk
from app.providers.embeddings.interface import EmbeddingProvider
from app.providers.storage.interface import ObjectStorage
from app.services.ingestion_jobs import DatabaseIngestionJobQueue, IngestionJobQueue

logger = structlog.get_logger(__name__)


class IngestionWorker:
    def __init__(
        self,
        session: AsyncSession,
        storage: ObjectStorage,
        embeddings: EmbeddingProvider,
        settings: Settings,
        queue: IngestionJobQueue | None = None,
        parsers: ParserRegistry | None = None,
    ) -> None:
        self._session = session
        self._storage = storage
        self._embeddings = embeddings
        self._settings = settings
        self._queue = queue or DatabaseIngestionJobQueue(session)
        self._parsers = parsers or ParserRegistry()

    async def process_next(self) -> bool:
        recovered = await self._queue.recover_stale(self._settings.ingestion_stale_after_seconds)
        if recovered:
            logger.warning("ingestion_jobs_recovered_from_stale_lock", count=recovered)

        job = await self._queue.claim_next()
        if job is None:
            return False

        structlog.contextvars.bind_contextvars(
            job_id=str(job.id), document_id=str(job.document_id)
        )
        started = time.perf_counter()
        try:
            document = job.document
            content = await self._storage.read(document.storage_key)
            units = self._parsers.parse(document.filename, content)
            chunks = TextChunker(
                self._settings.chunk_size_chars,
                self._settings.chunk_overlap_chars,
            ).chunk(units)
            if not chunks:
                raise ValueError("Document contains no usable text after parsing")
            vectors = await self._embeddings.embed_texts([chunk.text for chunk in chunks])
            if len(vectors) != len(chunks):
                raise ValueError("Embedding provider returned an unexpected vector count")
            if any(len(vector) != self._embeddings.dimensions for vector in vectors):
                raise ValueError(
                    "Embedding provider returned a vector with an unexpected dimension"
                )

            await self._session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
            )
            self._session.add_all(
                [
                    DocumentChunk(
                        document_id=document.id,
                        chunk_text=chunk.text,
                        chunk_index=chunk.chunk_index,
                        page_number=chunk.page_number,
                        location_metadata=chunk.location_metadata,
                        embedding=vector,
                    )
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ]
            )
            if not await self._queue.mark_completed(job.id):
                raise RuntimeError("Ingestion job was no longer processing during completion")
            logger.info(
                "ingestion_job_completed",
                chunk_count=len(chunks),
                attempts=job.attempts,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return True
        except Exception as exc:
            await self._session.rollback()
            reason = self._useful_error(exc)
            should_retry = job.attempts < self._settings.max_ingestion_attempts
            logger.warning(
                "ingestion_job_failed",
                error_type=type(exc).__name__,
                attempts=job.attempts,
                will_retry=should_retry,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            await self._queue.mark_failed(job.id, reason, requeue=should_retry)
            return True
        finally:
            structlog.contextvars.unbind_contextvars("job_id", "document_id")

    async def run_forever(self, idle_seconds: float = 1.0) -> None:
        import asyncio

        while True:
            did_work = await self.process_next()
            if not did_work:
                await asyncio.sleep(idle_seconds)

    @staticmethod
    def _useful_error(error: Exception) -> str:
        detail = str(error).strip() or type(error).__name__
        return f"{type(error).__name__}: {detail}"[:2000]
