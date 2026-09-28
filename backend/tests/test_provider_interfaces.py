import pytest

from app.core.config import Settings
from app.providers.embeddings.sentence_transformer import SentenceTransformerEmbeddingProvider
from app.providers.llm.groq import GroqLLMProvider
from app.providers.llm.interface import TextGenerationProvider


class FakeTextGenerator:
    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return f"mock:{prompt}"


async def ask(provider: TextGenerationProvider, prompt: str) -> str:
    return await provider.generate(prompt)


@pytest.mark.asyncio
async def test_generation_interface_accepts_provider_double() -> None:
    assert await ask(FakeTextGenerator(), "hello") == "mock:hello"


@pytest.mark.asyncio
async def test_groq_provider_requires_key_without_network_call() -> None:
    provider = GroqLLMProvider(Settings(_env_file=None))

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        await provider.generate("hello")


@pytest.mark.asyncio
async def test_empty_embedding_batch_does_not_load_model() -> None:
    provider = SentenceTransformerEmbeddingProvider(Settings(_env_file=None))

    assert provider.dimensions == 384
    assert await provider.embed_texts([]) == []
