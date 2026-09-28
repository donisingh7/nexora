from app.core.config import Settings, get_settings
from app.providers.embeddings.interface import EmbeddingProvider
from app.providers.embeddings.sentence_transformer import SentenceTransformerEmbeddingProvider


def create_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    return SentenceTransformerEmbeddingProvider(settings or get_settings())
