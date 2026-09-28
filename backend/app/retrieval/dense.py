from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.providers.embeddings.interface import EmbeddingProvider
from app.retrieval.interfaces import RetrievalCandidate


def build_dense_statement(query_embedding: list[float], workspace_id: UUID, limit: int):
    similarity = (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label("score")
    return (
        select(DocumentChunk, Document.filename, similarity)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.workspace_id == workspace_id,
            Document.status == "completed",
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )


class PgVectorDenseRetriever:
    def __init__(self, session: AsyncSession, embeddings: EmbeddingProvider) -> None:
        self._session = session
        self._embeddings = embeddings

    async def retrieve(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> list[RetrievalCandidate]:
        if limit <= 0 or not query.strip():
            return []
        vectors = await self._embeddings.embed_texts([query])
        if not vectors or len(vectors[0]) != self._embeddings.dimensions:
            raise ValueError("Embedding provider returned an invalid query vector")
        result = await self._session.execute(
            build_dense_statement(vectors[0], workspace_id, limit)
        )
        rows: list[Any] = result.all()
        return [
            RetrievalCandidate(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                filename=filename,
                text=chunk.chunk_text,
                score=float(score),
                page_number=chunk.page_number,
                location=chunk.location_metadata or {},
                dense_score=float(score),
            )
            for chunk, filename, score in rows
        ]
