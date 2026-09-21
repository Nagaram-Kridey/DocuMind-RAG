"""Value objects shared across retrieval modes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    """A scored chunk returned by a retrieval mode, with citation metadata."""

    chunk_id: int
    document_id: int
    title: str
    source_path: str
    heading_path: str
    anchor: str
    url: str
    text: str
    score: float

    def as_citation(self) -> dict[str, object]:
        """Return the public citation payload for this chunk."""
        return {
            "chunk_id": self.chunk_id,
            "title": self.title,
            "heading_path": self.heading_path,
            "url": self.url,
            "score": round(self.score, 4),
        }

    def as_retrieved(self) -> dict[str, object]:
        """Return the audit payload recorded on a query log."""
        return {
            "chunk_id": self.chunk_id,
            "source_path": self.source_path,
            "anchor": self.anchor,
            "score": round(self.score, 4),
        }