from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_knowledge_query_service
from app.main import app
from app.retrieval.interfaces import RetrievalCandidate
from app.schemas.query import AnswerResponse, CitationRead


class FakeQueryService:
    def __init__(self) -> None:
        self.workspace_id = uuid4()
        self.candidate = RetrievalCandidate(
            chunk_id=uuid4(),
            document_id=uuid4(),
            filename="guide.pdf",
            text="Relevant passage",
            score=0.02,
            page_number=6,
            location={"paragraph": 3},
            dense_score=0.8,
            lexical_score=1.4,
            fused_score=0.02,
        )

    async def retrieve(self, query, *, workspace_id, top_k):
        assert workspace_id == self.workspace_id
        assert top_k == 4
        return [self.candidate], [self.candidate], [self.candidate]

    async def answer(self, query, *, workspace_id, top_k):
        if workspace_id != self.workspace_id:
            raise AssertionError("workspace was not forwarded")
        citation = CitationRead(
            citation_id="S1",
            document_id=self.candidate.document_id,
            filename=self.candidate.filename,
            chunk_id=self.candidate.chunk_id,
            page_number=self.candidate.page_number,
            location=self.candidate.location,
            excerpt=self.candidate.text,
            relevance_score=self.candidate.score,
        )
        return AnswerResponse(
            workspace_id=workspace_id,
            query=query,
            answer="Grounded [S1].",
            citations=[citation],
            retrieval_count=1,
        )


class MissingLLMService:
    async def answer(self, query, *, workspace_id, top_k):
        from app.services.knowledge_query import LLMConfigurationError

        raise LLMConfigurationError("Answer generation is not configured")



def test_retrieval_endpoint_returns_ranked_sources_without_llm() -> None:
    service = FakeQueryService()
    app.dependency_overrides[get_knowledge_query_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query/retrieve",
                json={
                    "workspace_id": str(service.workspace_id),
                    "query": "question",
                    "top_k": 4,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["results"][0]["filename"] == "guide.pdf"
    assert response.json()["results"][0]["dense_score"] == 0.8
    assert response.json()["results"][0]["page_number"] == 6


def test_answer_endpoint_returns_structured_citations() -> None:
    service = FakeQueryService()
    app.dependency_overrides[get_knowledge_query_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query/answer",
                json={
                    "workspace_id": str(service.workspace_id),
                    "query": "question",
                    "top_k": 4,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["answer"] == "Grounded [S1]."
    assert response.json()["citations"][0]["citation_id"] == "S1"


def test_answer_endpoint_explains_missing_generation_configuration() -> None:
    app.dependency_overrides[get_knowledge_query_service] = lambda: MissingLLMService()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/query/answer",
                json={"query": "question"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
