import asyncio

from app.core.config import Settings, get_settings


class GeminiEmbeddingProvider:
    """Google Gemini embeddings, for serverless deployments where bundling a local
    sentence-transformers model into a Lambda package is impractical.

    Uses `output_dimensionality` to match the database's pinned 384-dimension vector
    column (Matryoshka truncation, supported by Gemini's embedding models).

    Not exercised against a live API in this repository - see DECISIONS.md. Written
    against the published `google-genai` SDK shape; verify against a real key before
    relying on it in production.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = None

    @property
    def dimensions(self) -> int:
        return self._settings.embedding_dimensions

    def _get_client(self):
        if self._client is None:
            if self._settings.gemini_api_key is None:
                raise RuntimeError(
                    "GEMINI_API_KEY is required to use the Gemini embedding provider"
                )
            from google import genai

            self._client = genai.Client(api_key=self._settings.gemini_api_key.get_secret_value())
        return self._client

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()

        def _call() -> list[list[float]]:
            response = client.models.embed_content(
                model=self._settings.gemini_embedding_model,
                contents=texts,
                config={"output_dimensionality": self._settings.embedding_dimensions},
            )
            return [list(embedding.values) for embedding in response.embeddings]

        return await asyncio.to_thread(_call)
