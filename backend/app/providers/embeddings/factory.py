from app.core.config import Settings, get_settings
from app.providers.embeddings.interface import EmbeddingProvider


def create_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    configured = settings or get_settings()
    if configured.embedding_provider == "gemini":
        from app.providers.embeddings.gemini import GeminiEmbeddingProvider

        return GeminiEmbeddingProvider(configured)

    from app.providers.embeddings.sentence_transformer import (
        SentenceTransformerEmbeddingProvider,
    )

    return SentenceTransformerEmbeddingProvider(configured)
