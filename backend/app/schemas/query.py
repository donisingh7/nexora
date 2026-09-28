import uuid

from pydantic import BaseModel, Field

from app.services.workspaces import DEFAULT_DEVELOPMENT_WORKSPACE_ID


class QueryRequest(BaseModel):
    workspace_id: uuid.UUID = DEFAULT_DEVELOPMENT_WORKSPACE_ID
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=8, ge=1, le=50)


class CitationRead(BaseModel):
    citation_id: str
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    page_number: int | None = None
    location: dict[str, object] = Field(default_factory=dict)
    excerpt: str
    relevance_score: float
    dense_score: float | None = None
    lexical_score: float | None = None


class RetrievedChunkRead(CitationRead):
    text: str
    fused_score: float | None = None


class RetrievalResponse(BaseModel):
    workspace_id: uuid.UUID
    query: str
    dense: list[RetrievedChunkRead]
    lexical: list[RetrievedChunkRead]
    results: list[RetrievedChunkRead]


class AnswerResponse(BaseModel):
    workspace_id: uuid.UUID
    query: str
    answer: str
    citations: list[CitationRead]
    retrieval_count: int
