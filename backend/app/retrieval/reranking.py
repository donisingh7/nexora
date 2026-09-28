from app.core.config import Settings, get_settings
from app.retrieval.interfaces import RetrievalCandidate


class NoopReranker:
    """Default reranker: preserves RRF ordering without loading any model."""

    enabled = False

    async def rerank(
        self, query: str, candidates: list[RetrievalCandidate], *, limit: int
    ) -> list[RetrievalCandidate]:
        return candidates[:limit]


class CrossEncoderReranker:
    """Optional cross-encoder reranking. Disabled by default and falls back to RRF order."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = None
        self.enabled = self._settings.reranker_enabled

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._settings.reranker_model)
        return self._model

    async def rerank(
        self, query: str, candidates: list[RetrievalCandidate], *, limit: int
    ) -> list[RetrievalCandidate]:
        if not self.enabled or not candidates:
            return candidates[:limit]
        try:
            import asyncio

            pairs = [(query, candidate.text) for candidate in candidates]
            scores = await asyncio.to_thread(lambda: self._get_model().predict(pairs))
            ranked = sorted(
                zip(candidates, scores, strict=True),
                key=lambda row: float(row[1]),
                reverse=True,
            )
            return [candidate for candidate, _ in ranked[:limit]]
        except Exception:
            return candidates[:limit]


def create_reranker(settings: Settings | None = None):
    resolved = settings or get_settings()
    return CrossEncoderReranker(resolved) if resolved.reranker_enabled else NoopReranker()
