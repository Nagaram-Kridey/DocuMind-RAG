"""Idempotent corpus ingestion: parse, chunk, embed, and persist.

The ingestion pipeline is deterministic and safe to re-run. A document is
skipped entirely when its source content is unchanged. When a document changes,
its chunks are rebuilt inside a transaction, but embeddings are recycled for any
chunk whose ``content_hash`` is unchanged so re-ingestion does not re-run the
encoder unnecessarily. The embedder is injected so ingestion can be unit tested
without loading a model.
"""

import hashlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from django.db import transaction

from .chunker import DocumentChunk, chunk_document
from .embedder import embed_documents
from .models import Chunk, Document, IngestionJob
from .parser import parse_rst_file

EmbedTexts = Callable[[Sequence[str]], list[list[float]]]

DOCUMENTATION_BASE_URL = "https://docs.djangoproject.com"


@dataclass
class IngestionResult:
    """Aggregate counts produced by one ingestion run."""

    documents_seen: int = 0
    documents_created: int = 0
    documents_updated: int = 0
    documents_skipped: int = 0
    chunks_created: int = 0
    chunks_reused_embeddings: int = 0
    chunks_embedded: int = 0
    chunk_count: int = 0
    errors: list[str] = field(default_factory=list)


def compute_content_hash(text: str) -> str:
    """Return a stable SHA-256 hex digest for idempotency comparisons."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def discover_document_paths(corpus_root: Path) -> list[Path]:
    """Return every RST source file under the corpus root in stable order."""
    return sorted(path for path in corpus_root.rglob("*.txt") if path.is_file())


def derive_url(source_path: str, doc_version: str) -> str:
    """Build the canonical public documentation URL for a source path."""
    slug = source_path.removesuffix(".txt")
    return f"{DOCUMENTATION_BASE_URL}/en/{doc_version}/{slug}/"


def ingest_corpus(
    corpus_root: Path,
    doc_version: str,
    *,
    embed_texts: EmbedTexts = embed_documents,
    paths: Iterable[Path] | None = None,
) -> IngestionResult:
    """Ingest every document under ``corpus_root`` and record a job lifecycle.

    ``paths`` allows a subset of files to be ingested (used by tests and by a
    targeted re-ingestion). An :class:`IngestionJob` is always written so the
    run is auditable even when individual documents fail.
    """
    result = IngestionResult()
    source_paths = list(paths) if paths is not None else discover_document_paths(corpus_root)
    result.documents_seen = len(source_paths)

    job = IngestionJob.objects.create(
        status=IngestionJob.Status.RUNNING,
        started_at=datetime.now(tz=UTC),
    )
    try:
        for path in source_paths:
            try:
                _ingest_document(path, corpus_root, doc_version, embed_texts, result)
            except Exception as error:  # noqa: BLE001 - recorded, not swallowed
                result.errors.append(f"{path}: {error}")
    except Exception as error:
        job.status = IngestionJob.Status.FAILED
        job.error = str(error)
        job.finished_at = datetime.now(tz=UTC)
        job.save(update_fields=["status", "error", "finished_at"])
        raise

    result.chunk_count = Chunk.objects.count()
    job.status = IngestionJob.Status.DONE if not result.errors else IngestionJob.Status.FAILED
    job.doc_count = result.documents_created + result.documents_updated
    job.chunk_count = result.chunk_count
    job.error = "\n".join(result.errors)
    job.finished_at = datetime.now(tz=UTC)
    job.save(update_fields=["status", "doc_count", "chunk_count", "error", "finished_at"])
    return result


def _ingest_document(
    path: Path,
    corpus_root: Path,
    doc_version: str,
    embed_texts: EmbedTexts,
    result: IngestionResult,
) -> None:
    """Parse, chunk, and persist one document idempotently."""
    raw_text = path.read_text(encoding="utf-8")
    document_hash = compute_content_hash(raw_text)

    parsed = parse_rst_file(path, corpus_root)
    existing = Document.objects.filter(
        source_path=parsed.source_path, doc_version=doc_version
    ).first()

    if existing is not None and existing.content_hash == document_hash:
        result.documents_skipped += 1
        return

    with transaction.atomic():
        if existing is None:
            document = Document.objects.create(
                source_path=parsed.source_path,
                title=parsed.title,
                doc_version=doc_version,
                url=derive_url(parsed.source_path, doc_version),
                content_hash=document_hash,
            )
            result.documents_created += 1
            reused_embeddings: dict[str, list[float]] = {}
        else:
            document = existing
            document.title = parsed.title
            document.url = derive_url(parsed.source_path, doc_version)
            document.content_hash = document_hash
            document.save(update_fields=["title", "url", "content_hash"])
            result.documents_updated += 1
            reused_embeddings = _existing_embeddings_by_hash(document)

        chunks = chunk_document(parsed)
        _persist_chunks(document, chunks, embed_texts, reused_embeddings, result)


def _existing_embeddings_by_hash(document: Document) -> dict[str, list[float]]:
    """Collect reusable embeddings keyed by chunk content hash before rewriting."""
    reusable: dict[str, list[float]] = {}
    rows = document.chunks.exclude(embedding=None).values_list("content_hash", "embedding")
    for content_hash, embedding in rows:
        if embedding is not None:
            reusable[content_hash] = list(embedding)
    return reusable


def _persist_chunks(
    document: Document,
    chunks: list[DocumentChunk],
    embed_texts: EmbedTexts,
    reused_embeddings: dict[str, list[float]],
    result: IngestionResult,
) -> None:
    """Replace a document's chunks, embedding only text without a cached vector."""
    document.chunks.all().delete()

    records: list[Chunk] = []
    to_embed: list[str] = []
    for chunk in chunks:
        content_hash = compute_content_hash(chunk.text)
        embedding = reused_embeddings.get(content_hash)
        if embedding is not None:
            result.chunks_reused_embeddings += 1
        else:
            to_embed.append(chunk.text)
        records.append(
            Chunk(
                document=document,
                heading_path=chunk.heading_path,
                anchor=chunk.anchor,
                ordinal=chunk.ordinal,
                text=chunk.text,
                token_count=chunk.token_count,
                content_hash=content_hash,
                embedding=embedding,
            )
        )

    if to_embed:
        vectors = embed_texts(to_embed)
        if len(vectors) != len(to_embed):
            raise ValueError("Embedder returned the wrong number of vectors for a document.")
        result.chunks_embedded += len(vectors)
        vector_iter = iter(vectors)
        for record in records:
            if record.embedding is None:
                record.embedding = next(vector_iter)

    Chunk.objects.bulk_create(records)
    result.chunks_created += len(records)