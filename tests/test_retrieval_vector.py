"""Tests for dense vector retrieval and the mode dispatch service."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from apps.documents.ingestion import EmbedTexts, ingest_corpus
from apps.retrieval.service import (
    VECTOR_MODE,
    UnsupportedModeError,
    build_context,
    chunk_by_id,
    retrieve,
)

CORPUS_DOCUMENT = (
    "Greeting\n"
    "========\n"
    "\n"
    "Alpha section\n"
    "=============\n"
    "\n"
    "The quick brown fox jumps over the lazy dog.\n"
    "\n"
    "Beta section\n"
    "============\n"
    "\n"
    "Database migrations alter the schema safely.\n"
)


def _fake_embedder(calls: list[list[str]]) -> EmbedTexts:
    """Return a deterministic embedder unrelated to embedding quality tests."""

    def embed(texts: Sequence[str]) -> list[list[float]]:
        recorded = list(texts)
        calls.append(recorded)
        return [[0.5] * 384 for _ in recorded]

    return embed


def _write_corpus(root: Path) -> list[Path]:
    """Create a single-document RST corpus."""
    document = root / "topics" / "greeting.txt"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(CORPUS_DOCUMENT, encoding="utf-8")
    return [document]


@pytest.mark.django_db
def test_retrieve_returns_scored_chunks(tmp_path: Path) -> None:
    """Vector retrieval returns chunks ordered by descending similarity."""
    _write_corpus(tmp_path)
    ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder([]))

    results = retrieve("Anything", mode=VECTOR_MODE, top_k=2, query_vector=[0.5] * 384)

    assert len(results) == 2
    assert results[0].score >= results[1].score
    assert results[0].chunk_id != results[1].chunk_id
    assert results[0].heading_path
    assert results[0].url.startswith("https://docs.djangoproject.com/")


@pytest.mark.django_db
def test_retrieve_top_k_limits_results(tmp_path: Path) -> None:
    """``top_k`` bounds the number of returned chunks."""
    _write_corpus(tmp_path)
    ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder([]))

    results = retrieve("Anything", mode=VECTOR_MODE, top_k=1, query_vector=[0.5] * 384)

    assert len(results) == 1


def test_unimplemented_mode_raises() -> None:
    """Valid but unimplemented modes raise a clear error, not silent baseline."""
    with pytest.raises(UnsupportedModeError):
        retrieve("Anything", mode="hybrid", top_k=1)


def test_unknown_mode_raises_value_error() -> None:
    """An unrecognised mode is rejected."""
    with pytest.raises(ValueError):
        retrieve("Anything", mode="nonsense", top_k=1)


def test_context_and_lookup_helpers() -> None:
    """Context formatting includes chunk IDs and headings; lookup indexes them."""
    from apps.retrieval.types import RetrievedChunk

    chunk = RetrievedChunk(
        chunk_id=7,
        document_id=1,
        title="Greeting",
        source_path="topics/greeting.txt",
        heading_path="Greeting > Alpha",
        anchor="alpha",
        url="https://example.test/",
        text="Hello world.",
        score=0.9,
    )

    assert "[7] Greeting > Alpha" in build_context([chunk])
    assert chunk_by_id([chunk])[7] is chunk
    assert chunk.as_citation()["chunk_id"] == 7
    assert chunk.as_retrieved()["source_path"] == "topics/greeting.txt"