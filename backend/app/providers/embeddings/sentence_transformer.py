import asyncio
from typing import Any

from app.core.config import Settings, get_settings


class SentenceTransformerEmbeddingProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model: Any | None = None

    @property
    def dimensions(self) -> int:
        return self._settings.embedding_dimensions

    def _get_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._settings.embedding_model)
            actual_dimensions = self._model.get_sentence_embedding_dimension()
            if actual_dimensions != self.dimensions:
                raise ValueError(
                    f"Configured embedding dimension {self.dimensions} does not match "
                    f"model dimension {actual_dimensions}"
                )
        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        def encode() -> Any:
            return self._get_model().encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

        vectors = await asyncio.to_thread(encode)
        return vectors.tolist()
