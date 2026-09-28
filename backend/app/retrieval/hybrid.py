from uuid import UUID

from app.retrieval.interfaces import (
    DenseRetriever,
    LexicalRetriever,
    RetrievalCandidate,
)


def reciprocal_rank_fusion(
    dense: list[RetrievalCandidate],
    lexical: list[RetrievalCandidate],
    *,
    limit: int,
    constant: int = 60,
) -> list[RetrievalCandidate]:
    if limit <= 0:
        return []
    fused: dict[UUID, tuple[RetrievalCandidate, float, int]] = {}
    components: dict[UUID, dict[str, float]] = {}
    for component_name, candidates in (("dense", dense), ("lexical", lexical)):
        for rank, candidate in enumerate(candidates, start=1):
            prior = fused.get(candidate.chunk_id)
            score = 1 / (constant + rank)
            fused[candidate.chunk_id] = (
                candidate if prior is None else prior[0],
                (prior[1] if prior else 0.0) + score,
                (prior[2] if prior else 0) + 1,
            )
            components.setdefault(candidate.chunk_id, {})[component_name] = candidate.score

    ranked = sorted(fused.values(), key=lambda value: (-value[1], str(value[0].chunk_id)))
    results: list[RetrievalCandidate] = []
    for candidate, score, _ in ranked[:limit]:
        scores = components[candidate.chunk_id]
        results.append(
            RetrievalCandidate(
                chunk_id=candidate.chunk_id,
                document_id=candidate.document_id,
                filename=candidate.filename,
                text=candidate.text,
                score=score,
                page_number=candidate.page_number,
                location=candidate.location,
                dense_score=scores.get("dense"),
                lexical_score=scores.get("lexical"),
                fused_score=score,
            )
        )
    return results


class HybridRrfRetriever:
    def __init__(
        self,
        dense_retriever: DenseRetriever,
        lexical_retriever: LexicalRetriever,
        *,
        dense_candidate_count: int = 30,
        lexical_candidate_count: int = 30,
        rrf_constant: int = 60,
    ) -> None:
        self._dense = dense_retriever
        self._lexical = lexical_retriever
        self._dense_count = dense_candidate_count
        self._lexical_count = lexical_candidate_count
        self._constant = rrf_constant

    async def retrieve(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> list[RetrievalCandidate]:
        dense, lexical = await self._retrieve_lists(query, workspace_id)
        return reciprocal_rank_fusion(
            dense,
            lexical,
            limit=limit,
            constant=self._constant,
        )

    async def retrieve_with_components(
        self, query: str, *, workspace_id: UUID, limit: int
    ) -> tuple[list[RetrievalCandidate], list[RetrievalCandidate], list[RetrievalCandidate]]:
        dense, lexical = await self._retrieve_lists(query, workspace_id)
        fused = reciprocal_rank_fusion(
            dense,
            lexical,
            limit=limit,
            constant=self._constant,
        )
        return dense, lexical, fused

    async def _retrieve_lists(
        self, query: str, workspace_id: UUID
    ) -> tuple[list[RetrievalCandidate], list[RetrievalCandidate]]:
        dense = await self._dense.retrieve(
            query, workspace_id=workspace_id, limit=self._dense_count
        )
        lexical = await self._lexical.retrieve(
            query, workspace_id=workspace_id, limit=self._lexical_count
        )
        return dense, lexical
