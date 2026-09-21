"""Local, cached embedding generation for documentation chunks and queries.

Embeddings are produced by a sentence-transformers model (default
``BAAI/bge-small-en-v1.5``) running on CPU. The encoder is loaded lazily and
cached so ingestion and query time share one in-process model instance. Vectors
are normalised so cosine similarity and inner product are equivalent, matching
the ``vector_cosine_ops`` HNSW index created in the persistence task.
"""

from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol, cast

import numpy as np
from django.conf import settings

from .models import EMBEDDING_DIMENSIONS

# BGE v1.5 recommends this instruction prefix for queries only, never documents.
QUERY_INSTRUCTION_PREFIX = "Represent this sentence for searching relevant passages: "
EMBEDDING_BATCH_SIZE = 32


class Encoder(Protocol):
    """The narrow slice of ``SentenceTransformer`` that DocuMind relies on."""

    def encode(
        self,
        sentences: Sequence[str],
        batch_size: int = ...,
        normalize_embeddings: bool = ...,
        convert_to_numpy: bool = ...,
    ) -> np.ndarray: ...


@lru_cache(maxsize=1)
def get_encoder() -> Encoder:
    """Load and cache the configured embedding model exactly once per process."""
    from sentence_transformers import SentenceTransformer

    return cast(Encoder, SentenceTransformer(settings.EMBEDDING_MODEL))


def embed_documents(texts: Sequence[str]) -> list[list[float]]:
    """Embed chunk texts into L2-normalised vectors in a single batched call."""
    if not texts:
        return []
    vectors = get_encoder().encode(
        list(texts),
        batch_size=EMBEDDING_BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return _validate_vectors(vectors, expected_rows=len(texts))


def embed_query(text: str) -> list[float]:
    """Embed one query with the BGE retrieval instruction prefix."""
    return embed_documents([f"{QUERY_INSTRUCTION_PREFIX}{text}"])[0]


def _validate_vectors(vectors: np.ndarray, expected_rows: int) -> list[list[float]]:
    """Fail loudly if the encoder returns an unexpected matrix shape."""
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape != (expected_rows, EMBEDDING_DIMENSIONS):
        raise ValueError(
            "Encoder must return shape "
            f"({expected_rows}, {EMBEDDING_DIMENSIONS}) but returned {matrix.shape}."
        )
    return [row.tolist() for row in matrix]