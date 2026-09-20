"""Schema-level tests for DocuMind persistence models."""

from django.contrib.postgres.indexes import GinIndex
from django.db.models import UniqueConstraint
from pgvector.django import HnswIndex

from apps.documents.models import (
    EMBEDDING_DIMENSIONS,
    HNSW_EF_CONSTRUCTION,
    HNSW_M,
    Chunk,
    Document,
)
from apps.qa.models import QueryLog


def test_chunk_model_uses_locked_vector_and_index_configuration() -> None:
    """The vector field and HNSW configuration match the project specification."""
    assert Chunk._meta.get_field("embedding").dimensions == EMBEDDING_DIMENSIONS == 384
    hnsw_index = next(index for index in Chunk._meta.indexes if isinstance(index, HnswIndex))

    assert hnsw_index.opclasses == ("vector_cosine_ops",)
    assert hnsw_index.m == HNSW_M == 16
    assert hnsw_index.ef_construction == HNSW_EF_CONSTRUCTION == 64
    assert any(isinstance(index, GinIndex) for index in Chunk._meta.indexes)


def test_model_constraints_preserve_idempotency_and_auditability() -> None:
    """Documents, chunks, and query logs expose the required persistence contract."""
    document_constraint = next(
        constraint
        for constraint in Document._meta.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    chunk_constraint = next(
        constraint
        for constraint in Chunk._meta.constraints
        if isinstance(constraint, UniqueConstraint)
    )

    assert document_constraint.fields == ("source_path", "doc_version")
    assert chunk_constraint.fields == ("document", "ordinal")
    assert QueryLog._meta.get_field("retrieved").get_default() == []
    assert QueryLog._meta.get_field("latency_ms").get_default() == {}
