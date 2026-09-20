"""Tests for the hand-written RST parser and heading-aware chunker."""

from apps.documents.chunker import chunk_document
from apps.documents.parser import parse_rst


def test_parser_preserves_headings_and_explicit_anchor() -> None:
    """RST headings form a path and explicit targets win over generated anchors."""
    document = parse_rst(
        "topics/example.txt",
        """Example
=======

Intro text.

.. _quick-start:

Quick start
===========

Use this feature.

Details
-------

More detail.
""",
    )

    assert document.title == "Example"
    assert document.sections[1].heading_path == ("Example", "Quick start")
    assert document.sections[1].anchor == "quick-start"
    assert document.sections[2].heading_path == ("Example", "Quick start", "Details")


def test_chunker_prefixes_heading_and_keeps_code_block_intact() -> None:
    """Code remains in one chunk even when paragraph boundaries form chunks."""
    document = parse_rst(
        "topics/example.txt",
        """Example
=======

Quick start
===========

One two three four five six seven eight.

Example::

    def greet():
        return "hello"

Nine ten eleven twelve thirteen fourteen fifteen sixteen.
""",
    )

    chunks = chunk_document(document, target_tokens=12, overlap_tokens=3)
    code_chunk = next(chunk for chunk in chunks if "def greet" in chunk.text)

    assert "return \"hello\"" in code_chunk.text
    assert all(chunk.text.startswith("Example > Quick start\n\n") for chunk in chunks)
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))


def test_chunker_rejects_invalid_overlap() -> None:
    """Overlap cannot consume the complete target size."""
    document = parse_rst("example.txt", "Example\n=======\n\nText.\n")

    try:
        chunk_document(document, target_tokens=10, overlap_tokens=10)
    except ValueError as error:
        assert "target_tokens" in str(error)
    else:
        raise AssertionError("Expected invalid chunk configuration to fail")
