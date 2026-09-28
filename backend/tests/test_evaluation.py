from uuid import uuid4

import pytest

from app.evaluation.fixtures import FIXTURE_CASES, FIXTURE_DOCUMENTS
from app.evaluation.metrics import mean, recall_at_k, reciprocal_rank
from app.evaluation.run import evaluate


def test_recall_at_k_counts_relevant_hits_within_top_k() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    assert recall_at_k([a, b, c], {a, c}, k=2) == pytest.approx(0.5)
    assert recall_at_k([a, b, c], {a, c}, k=3) == pytest.approx(1.0)
    assert recall_at_k([], {a}, k=3) == 0.0
    assert recall_at_k([a], set(), k=3) == 0.0


def test_reciprocal_rank_finds_first_relevant_result() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    assert reciprocal_rank([a, b, c], {b}) == pytest.approx(0.5)
    assert reciprocal_rank([a, b, c], {a}) == pytest.approx(1.0)
    assert reciprocal_rank([a, b, c], {uuid4()}) == 0.0


def test_mean_handles_empty_input() -> None:
    assert mean([]) == 0.0
    assert mean([1.0, 0.5]) == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_fixture_evaluation_meets_baseline_recall_and_mrr() -> None:
    """Regression guard: hybrid retrieval over the fixture should not silently degrade."""
    report = await evaluate(top_k=3)

    assert report.case_count == len(FIXTURE_CASES) == len(FIXTURE_DOCUMENTS)
    assert report.recall_at_k == pytest.approx(1.0)
    assert report.mrr >= 0.8
