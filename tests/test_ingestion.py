"""Tests for the embedder contract and idempotent corpus ingestion."""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from apps.documents.embedder import _validate_vectors
from apps.documents.ingestion import (
    EmbedTexts,
    compute_content_hash,
    derive_url,
    discover_document_paths,
    ingest_corpus,
)
from apps.documents.models import EMBEDDING_DIMENSIONS, Chunk, Document, IngestionJob

SAMPLE_DOCUMENT = (
    "Example\n"
    "=======\n"
    "\n"
    "Intro paragraph describing the example feature.\n"
    "\n"
    "Quick start\n"
    "===========\n"
    "\n"
    ".. _quick-start:\n"
    "\n"
    "Follow these steps to use the feature.\n"
    "\n"
    "Example::\n"
    "\n"
    "    def greet():\n"
    '        return "hello"\n'
)

SECOND_DOCUMENT = "Second\n======\n\nAnother document body.\n"

MULTI_SECTION_DOCUMENT = (
    "Mutable\n"
    "=======\n"
    "\n"
    "Alpha section\n"
    "=============\n"
    "\n"
    "Original alpha body.\n"
    "\n"
    "Stable\n"
    "======\n"
    "\n"
    "This section will not change.\n"
)


def _fake_embedder(calls: list[list[str]]) -> EmbedTexts:
    """Return an embedder that records calls and yields deterministic vectors."""

    def embed(texts: Sequence[str]) -> list[list[float]]:
        recorded = list(texts)
        calls.append(recorded)
        return [[0.01 * (index + 1)] * EMBEDDING_DIMENSIONS for index, _ in enumerate(recorded)]

    return embed


def _write_corpus(root: Path) -> list[Path]:
    """Create a minimal two-file RST corpus under ``root``."""
    first = root / "topics" / "example.txt"
    second = root / "topics" / "second.txt"
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_text(SAMPLE_DOCUMENT, encoding="utf-8")
    second.write_text(SECOND_DOCUMENT, encoding="utf-8")
    return [first, second]


def test_validator_rejects_wrong_shape() -> None:
    """A malformed encoder matrix is rejected rather than silently stored."""
    with pytest.raises(ValueError):
        _validate_vectors(np.zeros((2, 3), dtype=np.float32), expected_rows=2)


def test_validator_accepts_expected_shape() -> None:
    """A correctly shaped matrix is converted to plain Python lists."""
    vectors = _validate_vectors(np.ones((2, EMBEDDING_DIMENSIONS), dtype=np.float32), 2)

    assert len(vectors) == 2
    assert len(vectors[0]) == EMBEDDING_DIMENSIONS


def test_helper_functions_are_stable() -> None:
    """Content hashing and URL derivation are deterministic."""
    assert compute_content_hash("abc") == compute_content_hash("abc")
    assert compute_content_hash("abc") != compute_content_hash("abd")
    assert (
        derive_url("topics/db/models.txt", "5.2")
        == "https://docs.djangoproject.com/en/5.2/topics/db/models/"
    )


@pytest.mark.django_db
def test_ingestion_persists_documents_and_chunks(tmp_path: Path) -> None:
    """A first ingestion creates documents, chunks, and a completed job."""
    paths = _write_corpus(tmp_path)
    calls: list[list[str]] = []

    result = ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder(calls), paths=paths)

    assert result.documents_created == 2
    assert result.documents_updated == 0
    assert Document.objects.count() == 2
    assert Chunk.objects.count() == result.chunks_created
    assert all(chunk.embedding is not None for chunk in Chunk.objects.all())
    assert IngestionJob.objects.get().status == IngestionJob.Status.DONE


@pytest.mark.django_db
def test_reingestion_is_idempotent(tmp_path: Path) -> None:
    """Unchanged files are skipped and no duplicate chunks are created."""
    paths = _write_corpus(tmp_path)
    calls: list[list[str]] = []
    ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder(calls), paths=paths)
    chunk_count = Chunk.objects.count()

    second = ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder(calls), paths=paths)

    assert second.documents_skipped == 2
    assert second.documents_created == 0
    assert Chunk.objects.count() == chunk_count


@pytest.mark.django_db
def test_changed_document_reuses_unchanged_embeddings(tmp_path: Path) -> None:
    """A modified document rebuilds chunks but recycles unchanged vectors."""
    _write_corpus(tmp_path)
    targets = discover_document_paths(tmp_path)
    editable = next(path for path in targets if path.name == "second.txt")
    editable.write_text(MULTI_SECTION_DOCUMENT, encoding="utf-8")

    calls: list[list[str]] = []
    ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder(calls), paths=targets)

    editable.write_text(
        MULTI_SECTION_DOCUMENT.replace("Original alpha body.", "Revised alpha body."),
        encoding="utf-8",
    )

    calls.clear()
    result = ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder(calls), paths=targets)

    # The untouched "Stable" section keeps its embedding; only alpha is re-embedded.
    assert result.documents_updated == 1
    assert result.documents_skipped == 1
    assert result.chunks_reused_embeddings >= 1
    assert result.chunks_embedded >= 1
    assert sum(len(batch) for batch in calls) == result.chunks_embedded


@pytest.mark.django_db
def test_ingestion_records_failure_when_document_errors(tmp_path: Path) -> None:
    """A per-document failure is recorded and the job is marked failed."""
    missing = tmp_path / "topics" / "missing.txt"

    result = ingest_corpus(tmp_path, "5.2", embed_texts=_fake_embedder([]), paths=[missing])

    assert result.errors
    assert IngestionJob.objects.get().status == IngestionJob.Status.FAILED