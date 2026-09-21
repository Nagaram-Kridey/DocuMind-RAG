"""Tests for plain-prompt question answering and the /api/ask/ endpoint."""

from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.documents.ingestion import ingest_corpus
from apps.qa.generation import answer_question
from apps.qa.llm_client import (
    LLMClient,
    LLMConfigurationError,
    LLMResponse,
    LLMUsage,
    build_plain_prompt,
    get_llm_client,
)
from apps.qa.models import QueryLog

CORPUS_DOCUMENT = (
    "Greeting\n"
    "========\n"
    "\n"
    "Alpha section\n"
    "=============\n"
    "\n"
    "The quick brown fox jumps over the lazy dog.\n"
)


class FakeLLMClient:
    """A deterministic LLM client that records the prompts it received."""

    def __init__(self, text: str = "A grounded answer.") -> None:
        self.text = text
        self.calls: list[tuple[str, str]] = []

    def generate(self, system: str, user: str) -> LLMResponse:
        """Return a fixed completion and record the prompt pair."""
        self.calls.append((system, user))
        return LLMResponse(text=self.text, model="fake-model", usage=LLMUsage(10, 5))


def _fake_embedder(texts: Sequence[str]) -> list[list[float]]:
    """Return deterministic unit-ish vectors for ingestion and query embedding."""
    return [[0.5] * 384 for _ in texts]


def _write_corpus(root: Path) -> None:
    """Create a single-document RST corpus."""
    document = root / "topics" / "greeting.txt"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(CORPUS_DOCUMENT, encoding="utf-8")


def test_build_plain_prompt_contains_context_and_question() -> None:
    """The plain prompt embeds the context and question verbatim."""
    system, user = build_plain_prompt("What is a fox?", "[1] Section\nA fox is quick.")

    assert "only the provided context" in system
    assert "[1] Section" in user
    assert "What is a fox?" in user


def test_get_llm_client_requires_configuration() -> None:
    """Missing provider configuration fails loudly instead of silently."""
    with patch("apps.qa.llm_client.settings") as settings:
        settings.LLM_PROVIDER = "anthropic"
        settings.LLM_MODEL = ""
        settings.LLM_API_KEY = ""
        with pytest.raises(LLMConfigurationError):
            get_llm_client()


def test_get_llm_client_rejects_unknown_provider() -> None:
    """An unknown provider name is rejected."""
    with patch("apps.qa.llm_client.settings") as settings:
        settings.LLM_PROVIDER = "mystery"
        settings.LLM_MODEL = "m"
        settings.LLM_API_KEY = "k"
        with pytest.raises(LLMConfigurationError):
            get_llm_client()


@pytest.mark.django_db
def test_answer_question_returns_answer_citations_and_log(tmp_path: Path) -> None:
    """Answering retrieves chunks, cites them, and writes a query log."""
    _write_corpus(tmp_path)
    ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder)
    client: LLMClient = FakeLLMClient("The fox is quick.")

    with patch("apps.qa.generation.embed_query", return_value=[0.5] * 384):
        result = answer_question("Tell me about the fox.", client=client)

    assert result.answer == "The fox is quick."
    assert result.refused is False
    assert result.citations
    assert result.citations[0]["chunk_id"] == result.retrieved[0].chunk_id
    assert set(result.latency_ms) == {"embed", "retrieve", "rerank", "llm", "total"}
    assert QueryLog.objects.count() == 1
    log = QueryLog.objects.get()
    assert log.mode == "vector"
    assert log.model == "fake-model"
    assert log.tokens_in == 10
    assert log.tokens_out == 5


@pytest.mark.django_db
def test_ask_endpoint_returns_answer(tmp_path: Path) -> None:
    """POST /api/ask/ validates input and returns the assembled payload."""
    _write_corpus(tmp_path)
    ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder)

    with patch("apps.qa.generation.embed_query", return_value=[0.5] * 384), patch(
        "apps.qa.generation.generate_answer",
        return_value=LLMResponse("Mocked reply.", model="fake-model", usage=LLMUsage(1, 2)),
    ):
        response = APIClient().post(
            "/api/ask/", {"question": "Tell me about the fox."}, format="json"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Mocked reply."
    assert body["mode"] == "vector"
    assert isinstance(body["citations"], list)
    assert "latency_ms" in body


def test_ask_endpoint_rejects_blank_question() -> None:
    """A blank question is rejected with HTTP 400."""
    response = APIClient().post("/api/ask/", {"question": ""}, format="json")

    assert response.status_code == 400


def test_ask_endpoint_rejects_invalid_top_k() -> None:
    """``top_k`` outside 1..10 is rejected."""
    response = APIClient().post(
        "/api/ask/", {"question": "Valid?", "top_k": 99}, format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_ask_endpoint_rejects_unimplemented_mode() -> None:
    """Requesting a valid-but-unimplemented mode returns HTTP 400."""
    with patch("apps.qa.generation.embed_query", return_value=[0.5] * 384):
        response = APIClient().post(
            "/api/ask/", {"question": "Valid?", "mode": "hybrid"}, format="json"
        )

    assert response.status_code == 400
    assert "not implemented" in response.json()["detail"]
