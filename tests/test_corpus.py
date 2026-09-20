"""Tests for the pinned documentation corpus metadata."""

from config.corpus import (
    DJANGO_DOCS_COMMIT,
    DJANGO_DOCS_RELATIVE_PATH,
    DJANGO_DOCS_TAG,
    DJANGO_DOCS_VERSION,
)


def test_django_docs_pin_is_complete() -> None:
    """The corpus pin identifies a version, tag, immutable commit, and path."""
    assert DJANGO_DOCS_VERSION == "5.2"
    assert DJANGO_DOCS_TAG == "5.2.9"
    assert len(DJANGO_DOCS_COMMIT) == 40
    assert DJANGO_DOCS_RELATIVE_PATH == "data/django-5.2/docs"
