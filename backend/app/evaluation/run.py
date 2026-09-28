"""Deterministic, offline retrieval evaluation over a small local fixture.

Run from `backend/`:

    python -m app.evaluation.run
    python -m app.evaluation.run --top-k 5

Requires no database, network access, or credentials. It exercises the same
dense+lexical hybrid fusion used in production (`HybridRrfRetriever`), with a
dependency-free bag-of-words stand-in for the real embedding provider so the
fixture stays runnable anywhere the test suite runs.
"""

import argparse
import asyncio
import math
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from app.evaluation.fixtures import FIXTURE_CASES, FIXTURE_DOCUMENTS, WORKSPACE_ID, EvalDocument
from app.evaluation.metrics import mean, recall_at_k, reciprocal_rank
from app.retrieval.hybrid import HybridRrfRetriever
from app.retrieval.interfaces import RetrievalCandidate
from app.retrieval.lexical import BM25LexicalRetriever, LexicalDocument, tokenize


class BagOfWordsDenseRetriever:
    """Dependency-free stand-in for an embedding-based dense retriever.

    Scores documents by cosine similarity of token-frequency vectors. This is not
    the production embedding model - it exists only so the evaluation fixture can
    exercise dense+lexical fusion without downloading anything or calling an API.
    """

    def __init__(self, documents: list[EvalDocument]) -> None:
        self._documents = documents
        self._vectors = [Counter(tokenize(document.text)) for document in documents]

    async def retrieve(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> list[RetrievalCandidate]:
        query_vector = Counter(tokenize(query))
        if not query_vector or limit <= 0:
            return []
        scored = [
            (score, document)
            for document, vector in zip(self._documents, self._vectors, strict=True)
            if (score := _cosine_similarity(query_vector, vector)) > 0
        ]
        scored.sort(key=lambda row: (-row[0], row[1].key))
        return [
            RetrievalCandidate(
                chunk_id=document.chunk_id,
                document_id=document.document_id,
                filename=document.filename,
                text=document.text,
                score=score,
                dense_score=score,
            )
            for score, document in scored[:limit]
        ]


def _cosine_similarity(a: Counter, b: Counter) -> float:
    shared = set(a) & set(b)
    numerator = sum(a[token] * b[token] for token in shared)
    denominator = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(
        sum(v * v for v in b.values())
    )
    return numerator / denominator if denominator else 0.0


class StaticLexicalSource:
    """In-memory `LexicalChunkSource` over the fixed evaluation fixture."""

    def __init__(self, documents: list[EvalDocument]) -> None:
        self._documents = documents

    async def version(self, workspace_id: UUID) -> tuple[str | None, int]:
        return "fixture", len(self._documents)

    async def load(self, workspace_id: UUID) -> list[LexicalDocument]:
        return [
            LexicalDocument(
                chunk_id=document.chunk_id,
                document_id=document.document_id,
                filename=document.filename,
                text=document.text,
                page_number=None,
                location={},
            )
            for document in self._documents
        ]


def build_retriever() -> HybridRrfRetriever:
    dense = BagOfWordsDenseRetriever(FIXTURE_DOCUMENTS)
    lexical = BM25LexicalRetriever(StaticLexicalSource(FIXTURE_DOCUMENTS))
    return HybridRrfRetriever(dense, lexical, dense_candidate_count=10, lexical_candidate_count=10)


@dataclass(frozen=True)
class EvalReport:
    top_k: int
    case_count: int
    recall_at_k: float
    mrr: float


async def evaluate(top_k: int = 3) -> EvalReport:
    retriever = build_retriever()
    recalls: list[float] = []
    ranks: list[float] = []
    for case in FIXTURE_CASES:
        results = await retriever.retrieve(case.query, workspace_id=WORKSPACE_ID, limit=top_k)
        retrieved_ids = [item.chunk_id for item in results]
        relevant = case.relevant_ids()
        recalls.append(recall_at_k(retrieved_ids, relevant, top_k))
        ranks.append(reciprocal_rank(retrieved_ids, relevant))
    return EvalReport(
        top_k=top_k,
        case_count=len(FIXTURE_CASES),
        recall_at_k=mean(recalls),
        mrr=mean(ranks),
    )


def _print_report(report: EvalReport) -> None:
    print(
        f"Nexora retrieval evaluation - {report.case_count} fixture queries, "
        f"top_k={report.top_k}"
    )
    print(f"  Recall@{report.top_k}: {report.recall_at_k:.3f}")
    print(f"  MRR:       {report.mrr:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the local deterministic retrieval evaluation fixture."
    )
    parser.add_argument(
        "--top-k", type=int, default=3, help="Results considered per query (default: 3)"
    )
    args = parser.parse_args()
    report = asyncio.run(evaluate(args.top_k))
    _print_report(report)


if __name__ == "__main__":
    main()
