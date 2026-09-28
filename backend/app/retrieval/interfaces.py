from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk_id: UUID
    document_id: UUID
    text: str
    score: float
    filename: str = ""
    page_number: int | None = None
    location: dict[str, object] | None = None
    dense_score: float | None = None
    lexical_score: float | None = None
    fused_score: float | None = None


class DenseRetriever(Protocol):
    async def retrieve(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> list[RetrievalCandidate]: ...


class LexicalRetriever(Protocol):
    async def retrieve(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> list[RetrievalCandidate]: ...


class HybridRetriever(Protocol):
    async def retrieve(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> list[RetrievalCandidate]: ...


class Reranker(Protocol):
    async def rerank(
        self, query: str, candidates: list[RetrievalCandidate], *, limit: int
    ) -> list[RetrievalCandidate]: ...
