from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import dialect

from app.retrieval.dense import PgVectorDenseRetriever, build_dense_statement
from app.retrieval.hybrid import HybridRrfRetriever, reciprocal_rank_fusion
from app.retrieval.interfaces import RetrievalCandidate
from app.retrieval.lexical import BM25LexicalRetriever, LexicalDocument


def candidate(name: str, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=uuid4(),
        document_id=uuid4(),
        filename=f"{name}.txt",
        text=name,
        score=score,
    )


def test_dense_query_is_workspace_scoped_and_uses_cosine_distance() -> None:
    workspace_id = uuid4()
    statement = build_dense_statement([0.0] * 384, workspace_id, 12)
    compiled = statement.compile(dialect=dialect())
    sql = str(compiled)

    assert "JOIN documents" in sql
    assert "cosine_distance" not in sql.lower()
    assert "embedding <=>" in sql
    assert workspace_id in compiled.params.values()
    assert "completed" in compiled.params.values()
    assert 12 in compiled.params.values()


def test_rrf_combines_lists_and_prefers_mutually_retrieved_candidates() -> None:
    shared = candidate("shared", 0.9)
    dense_only = candidate("dense", 0.8)
    lexical_only = candidate("lexical", 7.2)
    lexical_shared = RetrievalCandidate(
        chunk_id=shared.chunk_id,
        document_id=shared.document_id,
        filename=shared.filename,
        text=shared.text,
        score=6.0,
    )

    ranked = reciprocal_rank_fusion(
        [shared, dense_only], [lexical_shared, lexical_only], limit=3, constant=10
    )

    assert ranked[0].chunk_id == shared.chunk_id
    assert ranked[0].dense_score == 0.9
    assert ranked[0].lexical_score == 6.0
    assert ranked[0].fused_score == pytest.approx(2 / 11)
    assert reciprocal_rank_fusion([], [], limit=5) == []


class FakeLexicalSource:
    def __init__(self) -> None:
        self.documents: dict[object, list[LexicalDocument]] = {}
        self.versions: dict[object, tuple[str | None, int]] = {}
        self.loads = 0

    async def version(self, workspace_id):
        return self.versions.get(workspace_id, ("v1", len(self.documents.get(workspace_id, []))))

    async def load(self, workspace_id):
        self.loads += 1
        return self.documents.get(workspace_id, [])


@pytest.mark.asyncio
async def test_bm25_is_workspace_scoped_and_cache_rebuilds_on_version_change() -> None:
    source = FakeLexicalSource()
    first_workspace, second_workspace = uuid4(), uuid4()
    first_doc = LexicalDocument(uuid4(), uuid4(), "first.txt", "policy retention records", 1, {})
    second_doc = LexicalDocument(uuid4(), uuid4(), "second.txt", "policy unrelated text", 1, {})
    source.documents[first_workspace] = [
        first_doc,
        LexicalDocument(uuid4(), uuid4(), "other.txt", "unrelated subject", 1, {}),
        LexicalDocument(uuid4(), uuid4(), "third.txt", "different concepts", 1, {}),
    ]
    source.documents[second_workspace] = [
        second_doc,
        LexicalDocument(uuid4(), uuid4(), "other-workspace.txt", "different", 1, {}),
        LexicalDocument(uuid4(), uuid4(), "other-workspace-2.txt", "separate", 1, {}),
    ]
    source.versions[first_workspace] = ("v1", 3)
    source.versions[second_workspace] = ("v1", 3)
    retriever = BM25LexicalRetriever(source)

    first_results = await retriever.retrieve("retention", workspace_id=first_workspace, limit=5)
    second_results = await retriever.retrieve("retention", workspace_id=second_workspace, limit=5)

    assert [item.document_id for item in first_results] == [first_doc.document_id]
    assert second_results == []
    source.versions[first_workspace] = ("v2", 3)
    await retriever.retrieve("retention", workspace_id=first_workspace, limit=5)
    assert source.loads == 3


@pytest.mark.asyncio
async def test_dense_retriever_embeds_and_maps_database_rows() -> None:
    workspace_id = uuid4()
    chunk = SimpleNamespace(
        id=uuid4(),
        document_id=uuid4(),
        chunk_text="matched text",
        page_number=4,
        location_metadata={"line_start": 2},
    )
    result = SimpleNamespace(all=lambda: [(chunk, "guide.pdf", 0.82)])
    session = AsyncMock()
    session.execute.return_value = result

    class FakeEmbeddings:
        dimensions = 384

        async def embed_texts(self, texts):
            assert texts == ["query"]
            return [[0.25] * 384]

    retriever = PgVectorDenseRetriever(session, FakeEmbeddings())
    candidates = await retriever.retrieve("query", workspace_id=workspace_id, limit=3)

    assert candidates[0].filename == "guide.pdf"
    assert candidates[0].score == 0.82
    assert candidates[0].page_number == 4
    sql = str(session.execute.await_args.args[0].compile(dialect=dialect()))
    assert "embedding <=>" in sql
    assert "JOIN documents" in sql


class FakeRetrieverPart:
    def __init__(self, values):
        self.values = values
        self.call = None

    async def retrieve(self, query, *, workspace_id, limit):
        self.call = (query, workspace_id, limit)
        return self.values


@pytest.mark.asyncio
async def test_hybrid_retriever_passes_workspace_and_candidate_counts() -> None:
    workspace_id = uuid4()
    dense_candidate = candidate("dense", 0.8)
    lexical_candidate = candidate("lexical", 3.0)
    dense = FakeRetrieverPart([dense_candidate])
    lexical = FakeRetrieverPart([lexical_candidate])
    retriever = HybridRrfRetriever(
        dense,
        lexical,
        dense_candidate_count=17,
        lexical_candidate_count=19,
    )

    results = await retriever.retrieve("term", workspace_id=workspace_id, limit=4)

    assert {item.chunk_id for item in results} == {
        dense_candidate.chunk_id,
        lexical_candidate.chunk_id,
    }
    assert dense.call == ("term", workspace_id, 17)
    assert lexical.call == ("term", workspace_id, 19)
