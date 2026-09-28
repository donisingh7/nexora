import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from rank_bm25 import BM25Okapi
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.retrieval.interfaces import RetrievalCandidate

_TOKEN_PATTERN = re.compile(r"[\w]+", flags=re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.casefold())


@dataclass(frozen=True)
class LexicalDocument:
    chunk_id: UUID
    document_id: UUID
    filename: str
    text: str
    page_number: int | None
    location: dict[str, object]


class LexicalChunkSource(Protocol):
    async def version(self, workspace_id: UUID) -> tuple[str | None, int]: ...

    async def load(self, workspace_id: UUID) -> list[LexicalDocument]: ...


class SqlLexicalChunkSource:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def version(self, workspace_id: UUID) -> tuple[str | None, int]:
        statement = select(func.max(Document.updated_at), func.count(Document.id)).where(
            Document.workspace_id == workspace_id,
            Document.status == "completed",
        )
        latest, count = (await self._session.execute(statement)).one()
        return latest.isoformat() if latest else None, int(count)

    async def load(self, workspace_id: UUID) -> list[LexicalDocument]:
        statement = (
            select(DocumentChunk, Document.filename)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.workspace_id == workspace_id, Document.status == "completed")
            .order_by(Document.id, DocumentChunk.chunk_index)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            LexicalDocument(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                filename=filename,
                text=chunk.chunk_text,
                page_number=chunk.page_number,
                location=chunk.location_metadata or {},
            )
            for chunk, filename in rows
        ]


@dataclass
class _WorkspaceIndex:
    version: tuple[str | None, int]
    documents: list[LexicalDocument]
    bm25: BM25Okapi | None


class BM25LexicalRetriever:
    """Workspace-scoped in-process BM25 cache backed by authoritative chunk rows."""

    def __init__(
        self,
        source: LexicalChunkSource,
        cache: dict[UUID, _WorkspaceIndex] | None = None,
    ) -> None:
        self._source = source
        self._indexes = cache if cache is not None else {}

    async def invalidate(self, workspace_id: UUID) -> None:
        self._indexes.pop(workspace_id, None)

    async def _index(self, workspace_id: UUID) -> _WorkspaceIndex:
        version = await self._source.version(workspace_id)
        cached = self._indexes.get(workspace_id)
        if cached is None or cached.version != version:
            documents = await self._source.load(workspace_id)
            tokens = [tokenize(document.text) for document in documents]
            bm25 = BM25Okapi(tokens) if tokens and any(tokens) else None
            cached = _WorkspaceIndex(version, documents, bm25)
            self._indexes[workspace_id] = cached
        return cached

    async def retrieve(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> list[RetrievalCandidate]:
        if limit <= 0 or not tokenize(query):
            return []
        index = await self._index(workspace_id)
        if index.bm25 is None:
            return []
        scores = index.bm25.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda row: (-float(row[1]), row[0]))
        return [
            RetrievalCandidate(
                chunk_id=index.documents[position].chunk_id,
                document_id=index.documents[position].document_id,
                filename=index.documents[position].filename,
                text=index.documents[position].text,
                score=float(score),
                page_number=index.documents[position].page_number,
                location=index.documents[position].location,
                lexical_score=float(score),
            )
            for position, score in ranked[:limit]
            if score > 0
        ]
