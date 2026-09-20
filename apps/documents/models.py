"""Persistence models for the pinned documentation corpus and its chunks."""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from pgvector.django import HnswIndex, VectorField

EMBEDDING_DIMENSIONS = 384
HNSW_M = 16
HNSW_EF_CONSTRUCTION = 64


class Document(models.Model):
    """A source document from the single pinned documentation corpus."""

    source_path = models.CharField(max_length=500)
    title = models.CharField(max_length=500)
    doc_version = models.CharField(max_length=20)
    url = models.URLField(max_length=1000)
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Database constraints for idempotent document ingestion."""

        constraints = [
            models.UniqueConstraint(
                fields=("source_path", "doc_version"),
                name="documents_unique_source_version",
            )
        ]
        indexes = [models.Index(fields=("content_hash",), name="documents_content_hash_idx")]

    def __str__(self) -> str:
        """Return a concise administrative representation."""
        return f"{self.doc_version}:{self.source_path}"


class Chunk(models.Model):
    """A provenance-preserving retrieval unit derived from one document."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    heading_path = models.TextField()
    anchor = models.CharField(max_length=500)
    ordinal = models.PositiveIntegerField()
    text = models.TextField()
    token_count = models.PositiveIntegerField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)
    search_vector = SearchVectorField(null=True)
    content_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Indexes for vector and Postgres full-text retrieval."""

        constraints = [
            models.UniqueConstraint(
                fields=("document", "ordinal"),
                name="chunks_unique_document_ordinal",
            )
        ]
        indexes = [
            HnswIndex(
                name="chunks_embedding_hnsw_idx",
                fields=("embedding",),
                opclasses=("vector_cosine_ops",),
                m=HNSW_M,
                ef_construction=HNSW_EF_CONSTRUCTION,
            ),
            GinIndex(fields=("search_vector",), name="chunks_search_vector_gin_idx"),
            models.Index(fields=("content_hash",), name="chunks_content_hash_idx"),
        ]

    def __str__(self) -> str:
        """Return a concise administrative representation."""
        return f"{self.document.source_path}#{self.anchor}:{self.ordinal}"


class IngestionJob(models.Model):
    """Record the lifecycle and outcome of a documentation ingestion run."""

    class Status(models.TextChoices):
        """Allowed ingestion lifecycle states."""

        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    doc_count = models.PositiveIntegerField(default=0)
    chunk_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        """Return an administrative representation of this run."""
        return f"IngestionJob {self.pk}: {self.status}"
