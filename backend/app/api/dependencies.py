from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.providers.embeddings.factory import create_embedding_provider
from app.providers.embeddings.interface import EmbeddingProvider
from app.providers.llm.groq import GroqLLMProvider
from app.providers.llm.interface import TextGenerationProvider
from app.providers.queue.factory import create_job_publisher
from app.providers.queue.interface import IngestionJobPublisher
from app.providers.storage.factory import create_object_storage
from app.providers.storage.interface import ObjectStorage
from app.retrieval.dense import PgVectorDenseRetriever
from app.retrieval.hybrid import HybridRrfRetriever
from app.retrieval.lexical import BM25LexicalRetriever, SqlLexicalChunkSource
from app.retrieval.reranking import create_reranker
from app.services.documents import DocumentService
from app.services.knowledge_query import KnowledgeQueryService
from app.services.workspaces import ensure_development_workspace

_bm25_workspace_indexes = {}


@lru_cache
def get_storage_provider() -> ObjectStorage:
    return create_object_storage()


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return create_embedding_provider()


@lru_cache
def get_llm_provider() -> TextGenerationProvider:
    return GroqLLMProvider()


@lru_cache
def get_job_publisher() -> IngestionJobPublisher:
    return create_job_publisher()


async def get_document_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
    job_publisher: Annotated[IngestionJobPublisher, Depends(get_job_publisher)],
) -> DocumentService:
    return DocumentService(session, storage, settings, job_publisher)


async def get_development_workspace(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    return await ensure_development_workspace(session)


async def get_knowledge_query_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    llm: Annotated[TextGenerationProvider, Depends(get_llm_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeQueryService:
    dense = PgVectorDenseRetriever(session, embeddings)
    lexical = BM25LexicalRetriever(
        SqlLexicalChunkSource(session),
        cache=_bm25_workspace_indexes,
    )
    hybrid = HybridRrfRetriever(
        dense,
        lexical,
        dense_candidate_count=settings.dense_candidate_count,
        lexical_candidate_count=settings.lexical_candidate_count,
        rrf_constant=settings.rrf_constant,
    )
    return KnowledgeQueryService(hybrid, llm, create_reranker(settings))
