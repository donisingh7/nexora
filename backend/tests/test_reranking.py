from uuid import uuid4

import pytest

from app.core.config import Settings
from app.retrieval.interfaces import RetrievalCandidate
from app.retrieval.reranking import CrossEncoderReranker, NoopReranker, create_reranker


def candidates(count: int) -> list[RetrievalCandidate]:
    return [
        RetrievalCandidate(
            chunk_id=uuid4(),
            document_id=uuid4(),
            filename=f"file-{index}.txt",
            text=f"passage {index}",
            score=1.0 / (index + 1),
        )
        for index in range(count)
    ]


def test_reranking_is_disabled_by_default() -> None:
    reranker = create_reranker(Settings(_env_file=None))
    assert isinstance(reranker, NoopReranker)
    assert reranker.enabled is False


@pytest.mark.asyncio
async def test_noop_reranker_preserves_rrf_order_and_limit() -> None:
    items = candidates(4)
    result = await NoopReranker().rerank("query", items, limit=2)
    assert result == items[:2]


@pytest.mark.asyncio
async def test_cross_encoder_falls_back_when_model_unavailable() -> None:
    reranker = CrossEncoderReranker(Settings(_env_file=None, reranker_enabled=True))
    items = candidates(3)

    def explode():
        raise RuntimeError("model weights unavailable")

    reranker._get_model = explode
    assert await reranker.rerank("query", items, limit=3) == items
