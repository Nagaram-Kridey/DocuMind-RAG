"""Heading-aware chunking for parsed documentation sections."""

from dataclasses import dataclass

from .parser import ParsedDocument, ParsedSection

DEFAULT_TARGET_TOKENS = 400
DEFAULT_OVERLAP_TOKENS = 50


@dataclass(frozen=True)
class DocumentChunk:
    """A retrieval-ready chunk with stable source provenance."""

    source_path: str
    heading_path: str
    anchor: str
    ordinal: int
    text: str
    token_count: int


def chunk_document(
    document: ParsedDocument,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[DocumentChunk]:
    """Chunk sections by paragraph while preserving every indented code block."""
    if target_tokens <= overlap_tokens or overlap_tokens < 0:
        raise ValueError("target_tokens must be greater than a non-negative overlap_tokens")

    chunks: list[DocumentChunk] = []
    for section in document.sections:
        chunks.extend(_chunk_section(section, len(chunks), target_tokens, overlap_tokens))
    return chunks


def _chunk_section(
    section: ParsedSection,
    ordinal_start: int,
    target_tokens: int,
    overlap_tokens: int,
) -> list[DocumentChunk]:
    """Build chunks within one heading section so provenance remains precise."""
    blocks = _content_blocks(section.content)
    completed: list[DocumentChunk] = []
    current: list[str] = []

    for block in blocks:
        candidate = "\n\n".join([*current, block])
        if current and _word_count(candidate) > target_tokens:
            current_text = "\n\n".join(current)
            completed.append(_make_chunk(section, ordinal_start + len(completed), current_text))
            overlap = _tail_words(current_text, overlap_tokens)
            current = [overlap, block] if overlap else [block]
        else:
            current.append(block)

    if current:
        completed.append(_make_chunk(section, ordinal_start + len(completed), "\n\n".join(current)))
    return completed


def _content_blocks(content: str) -> list[str]:
    """Split only on blank-line boundaries, keeping indented code together."""
    blocks: list[str] = []
    current: list[str] = []
    for line in content.splitlines():
        if not line.strip():
            if current:
                current.append("")
            continue
        if current and not current[-1] and not line.startswith((" ", "\t")):
            blocks.append("\n".join(current).strip())
            current = []
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return blocks


def _make_chunk(section: ParsedSection, ordinal: int, content: str) -> DocumentChunk:
    """Prefix the chunk body with heading context for downstream embedding."""
    heading_path = " > ".join(section.heading_path)
    text = f"{heading_path}\n\n{content}"
    return DocumentChunk(
        source_path=section.source_path,
        heading_path=heading_path,
        anchor=section.anchor,
        ordinal=ordinal,
        text=text,
        token_count=_word_count(text),
    )


def _tail_words(text: str, count: int) -> str:
    """Return a lightweight token overlap for the following chunk."""
    return " ".join(text.split()[-count:]) if count else ""


def _word_count(text: str) -> int:
    """Estimate tokens consistently until a model tokenizer is introduced."""
    return len(text.split())
