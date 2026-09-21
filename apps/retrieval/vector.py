"""Dense vector retrieval using pgvector cosine distance.

The baseline retrieval mode: embed the query, then order chunks by cosine
distance to that vector. Because chunk embeddings are L2-normalised and the
``Chunk.embedding`` column is indexed with ``vector_cosine_ops`` HNSW, the
database returns results in increasing ``CosineDistance`` (1 - cosine
similarity), so the closest chunks come first.
"""

from collections.abc import Sequence

from django.db.models import QuerySet
from pgvector.django import CosineDistance

from apps.documents.embedder import embed_query
from apps.documents.models import Chunk

from .types import RetrievedChunk


def search_by_vector(
    query: str,
    top_k: int,
    query_vector: Sequence[float] | None = None,
) -> list[RetrievedChunk]:
    """Return the ``top_k`` chunks most similar to ``query`` by cosine distance.

    ``query_vector`` lets callers pass an already-computed embedding; when it is
    omitted the query is embedded with the shared BGE encoder.
    """
    if top_k <= 0:
        return []

    vector = list(query_vector) if query_vector is not None else embed_query(query)
    queryset: QuerySet[Chunk] = (
        Chunk.objects.exclude(embedding=None)
        .select_related("document")
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance")[:top_k]
    )
    return [_to_retrieved_chunk(chunk, float(getattr(chunk, "distance"))) for chunk in queryset]


def _to_retrieved_chunk(chunk: Chunk, distance: float) -> RetrievedChunk:
    """Convert a database row plus its distance into a similarity-scored result."""
    document = chunk.document
    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=document.id,
        title=document.title,
        source_path=document.source_path,
        heading_path=chunk.heading_path,
        anchor=chunk.anchor,
        url=document.url,
        text=chunk.text,
        score=1.0 - distance,
    )