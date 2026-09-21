"""Provider-agnostic LLM access.

The rest of the codebase depends only on the :class:`LLMClient` protocol and
the response/usage dataclasses. Provider SDKs (Anthropic, OpenAI) are imported
lazily inside the concrete clients so that importing this module never requires
a provider SDK or an API key. Tests inject a fake client and never touch a real
provider.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from django.conf import settings

ANTHROPIC_PROVIDER = "anthropic"
OPENAI_PROVIDER = "openai"


class LLMConfigurationError(RuntimeError):
    """Raised when LLM settings are missing or reference an unknown provider."""


@dataclass(frozen=True)
class LLMUsage:
    """Token accounting for one generation call."""

    tokens_in: int = 0
    tokens_out: int = 0


@dataclass(frozen=True)
class LLMResponse:
    """The text produced by an LLM plus its usage metadata."""

    text: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)


class LLMClient(Protocol):
    """The minimal generation surface DocuMind depends on."""

    def generate(self, system: str, user: str) -> LLMResponse: ...


class AnthropicLLMClient:
    """Generate text with the Anthropic Messages API."""

    def __init__(self, model: str, api_key: str) -> None:
        """Store configuration; the SDK is imported on first use."""
        self._model = model
        self._api_key = api_key

    def generate(self, system: str, user: str) -> LLMResponse:
        """Return a single completion from the configured model."""
        import anthropic

        client = anthropic.Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self._model,
            max_tokens=1024,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        )
        return LLMResponse(
            text=text.strip(),
            model=self._model,
            usage=LLMUsage(
                tokens_in=message.usage.input_tokens,
                tokens_out=message.usage.output_tokens,
            ),
        )


class OpenAILLMClient:
    """Generate text with the OpenAI Chat Completions API."""

    def __init__(self, model: str, api_key: str) -> None:
        """Store configuration; the SDK is imported on first use."""
        self._model = model
        self._api_key = api_key

    def generate(self, system: str, user: str) -> LLMResponse:
        """Return a single completion from the configured model."""
        import openai

        client = openai.OpenAI(api_key=self._api_key)
        completion = client.chat.completions.create(
            model=self._model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = completion.choices[0].message.content or ""
        usage = completion.usage
        return LLMResponse(
            text=text.strip(),
            model=self._model,
            usage=LLMUsage(
                tokens_in=usage.prompt_tokens if usage else 0,
                tokens_out=usage.completion_tokens if usage else 0,
            ),
        )


_PROVIDER_FACTORIES: dict[str, Callable[[str, str], LLMClient]] = {
    ANTHROPIC_PROVIDER: AnthropicLLMClient,
    OPENAI_PROVIDER: OpenAILLMClient,
}


def get_llm_client() -> LLMClient:
    """Build the LLM client selected by ``settings.LLM_PROVIDER``."""
    provider = settings.LLM_PROVIDER
    factory = _PROVIDER_FACTORIES.get(provider)
    if factory is None:
        raise LLMConfigurationError(f"Unknown LLM provider: {provider}")
    if not settings.LLM_MODEL:
        raise LLMConfigurationError("LLM_MODEL is not configured.")
    if not settings.LLM_API_KEY:
        raise LLMConfigurationError("LLM_API_KEY is not configured.")
    return factory(settings.LLM_MODEL, settings.LLM_API_KEY)


def generate_answer(
    question: str,
    context: str,
    client: LLMClient | None = None,
) -> LLMResponse:
    """Generate a plain, context-conditioned answer for the given question."""
    active_client = client if client is not None else get_llm_client()
    system, user = build_plain_prompt(question, context)
    return active_client.generate(system, user)


def build_plain_prompt(question: str, context: str) -> tuple[str, str]:
    """Return the Phase 1 plain system/user prompt pair.

    Phase 3 replaces this with the citation-grounded contract. Keeping the plain
    prompt isolated makes that later swap a single, testable change.
    """
    system = (
        "You are a helpful assistant. Answer the user's question using only the "
        "provided context. If the context does not contain the answer, say you "
        "do not know."
    )
    user = f"Context:\n{context}\n\nQuestion: {question}"
    return system, user