"""End-to-end question answering for Phase 1: retrieve, generate, and log.

This orchestrator embeds the query once, retrieves candidate chunks, builds the
context, calls the LLM through the provider-agnostic client, records per-stage
timings, and writes an auditable QueryLog. Citation-grounded prompting, refusal
handling, and citation validation are introduced in Phase 3; the plain prompt
used here is isolated in ``llm_client.build_plain_prompt`` so that upgrade is a
single change.
"""

from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING

from apps.documents.embedder import embed_query
from apps.retrieval.service import VECTOR_MODE, build_context, retrieve
from apps.retrieval.types import RetrievedChunk

from .llm_client import LLMClient, LLMUsage, generate_answer
from .models import QueryLog

if TYPE_CHECKING:  # pragma: no cover - typing only
    from django.contrib.auth.models import User

DEFAULT_TOP_K = 5


@dataclass(frozen=True)
class AskResult:
    """The assembled answer, its citations, and per-stage latency."""

    answer: str
    refused: bool
    citations: list[dict[str, object]]
    retrieved: list[RetrievedChunk]
    mode: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    latency_ms: dict[str, int] = field(default_factory=dict)

    def as_response(self) -> dict[str, object]:
        """Return the public ``/api/ask/`` response payload."""
        return {
            "answer": self.answer,
            "refused": self.refused,
            "citations": self.citations,
            "mode": self.mode,
            "latency_ms": self.latency_ms,
        }


def answer_question(
    question: str,
    mode: str = VECTOR_MODE,
    top_k: int = DEFAULT_TOP_K,
    *,
    client: LLMClient | None = None,
    user: "User | None" = None,
) -> AskResult:
    """Answer ``question`` using retrieval ``mode`` and the plain LLM prompt."""
    total_start = perf_counter()

    embed_start = perf_counter()
    query_vector = embed_query(question)
    embed_ms = _elapsed_ms(embed_start)

    retrieve_start = perf_counter()
    retrieved = retrieve(question, mode=mode, top_k=top_k, query_vector=query_vector)
    retrieve_ms = _elapsed_ms(retrieve_start)

    context = build_context(retrieved)
    llm_start = perf_counter()
    response = generate_answer(question, context, client=client)
    llm_ms = _elapsed_ms(llm_start)

    latency = {
        "embed": embed_ms,
        "retrieve": retrieve_ms,
        "rerank": 0,
        "llm": llm_ms,
        "total": _elapsed_ms(total_start),
    }
    citations = [chunk.as_citation() for chunk in retrieved]

    _record_query_log(
        user=user,
        question=question,
        mode=mode,
        retrieved=retrieved,
        answer=response.text,
        citations=citations,
        latency=latency,
        model=response.model,
        usage=response.usage,
    )

    return AskResult(
        answer=response.text,
        refused=False,
        citations=citations,
        retrieved=retrieved,
        mode=mode,
        model=response.model,
        usage=response.usage,
        latency_ms=latency,
    )


def _record_query_log(
    *,
    user: "User | None",
    question: str,
    mode: str,
    retrieved: list[RetrievedChunk],
    answer: str,
    citations: list[dict[str, object]],
    latency: dict[str, int],
    model: str,
    usage: LLMUsage,
) -> None:
    """Persist an audit record; logging failure must not break the request."""
    try:
        QueryLog.objects.create(
            user=user if user is not None and user.is_authenticated else None,
            question=question,
            mode=mode,
            retrieved=[chunk.as_retrieved() for chunk in retrieved],
            answer=answer,
            citations=citations,
            refused=False,
            latency_ms=latency,
            model=model,
            tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out,
        )
    except Exception:  # noqa: BLE001 - audit logging must never fail a response
        return


def _elapsed_ms(start: float) -> int:
    """Return integer milliseconds elapsed since ``start``."""
    return int((perf_counter() - start) * 1000)