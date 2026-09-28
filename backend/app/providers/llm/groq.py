import time

import structlog

from app.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class GroqLLMProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        if self._settings.groq_api_key is None:
            raise RuntimeError("GROQ_API_KEY is required to use Groq text generation")

        from groq import AsyncGroq

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        started = time.perf_counter()
        async with AsyncGroq(api_key=self._settings.groq_api_key.get_secret_value()) as client:
            result = await client.chat.completions.create(
                model=self._settings.groq_model,
                messages=messages,
            )
        usage = getattr(result, "usage", None)
        logger.info(
            "llm_generation_completed",
            provider="groq",
            model=self._settings.groq_model,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage is not None else None,
            completion_tokens=(
                getattr(usage, "completion_tokens", None) if usage is not None else None
            ),
            total_tokens=getattr(usage, "total_tokens", None) if usage is not None else None,
        )
        return result.choices[0].message.content or ""
