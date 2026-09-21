"""Mode-aware retrieval entry point.

Only the ``vector`` baseline exists in Phase 1. ``hybrid`` and
``hybrid_rerank`` are declared so the API contract is stable, but they raise a
clear error until their phases implement them. This keeps the endpoint honest
rather than silently returning baseline results for an unimplemented mode.
"""

from collections.abc import Sequence

from .types import RetrievedChunk
from .vector import search_by_vector

VECTOR_MODE = "vector"
HYBRID_MODE = "hybrid"
HYBRID_RERANK_MODE = "hybrid_rerank"
SUPPORTED_MODES = (VECTOR_MODE, HYBRID_MODE, HYBRID_RERANK_MODE)
IMPLEMENTED_MODES = (VECTOR_MODE,)


class UnsupportedModeError(ValueError):
    """Raised when a mode is valid but not yet implemented."""


def retrieve(
    query: str,
    mode: str = VECTOR_MODE,
    top_k: int = 5,
    *,
    query_vector: Sequence[float] | None = None,
) -> list[RetrievedChunk]:
    """Dispatch retrieval for ``mode`` (Phase 1 supports ``vector`` only)."""
    if mode == VECTOR_MODE:
        return search_by_vector(query, top_k, query_vector=query_vector)
    if mode in SUPPORTED_MODES:
        raise UnsupportedModeError(f"Retrieval mode '{mode}' is not implemented yet.")
    raise ValueError(f"Unknown retrieval mode: {mode}")


def build_context(chunks: Sequence[RetrievedChunk]) -> str:
    """Format retrieved chunks as numbered, citable context blocks."""
    blocks = [
        f"[{chunk.chunk_id}] {chunk.heading_path}\n{chunk.text}" for chunk in chunks
    ]
    return "\n\n".join(blocks)


def chunk_by_id(chunks: Sequence[RetrievedChunk]) -> dict[int, RetrievedChunk]:
    """Index retrieved chunks by ID for citation validation."""
    return {chunk.chunk_id: chunk for chunk in chunks}


__all__ = [
    "HYBRID_MODE",
    "HYBRID_RERANK_MODE",
    "IMPLEMENTED_MODES",
    "SUPPORTED_MODES",
    "VECTOR_MODE",
    "UnsupportedModeError",
    "build_context",
    "chunk_by_id",
    "retrieve",
]
