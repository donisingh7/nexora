from uuid import UUID


def recall_at_k(retrieved_ids: list[UUID], relevant_ids: set[UUID], k: int) -> float:
    """Fraction of relevant chunks found within the top `k` retrieved results."""
    if not relevant_ids:
        return 0.0
    hits = len(set(retrieved_ids[:k]) & relevant_ids)
    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[UUID], relevant_ids: set[UUID]) -> float:
    """1/rank of the first relevant result, or 0.0 if none appears."""
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
