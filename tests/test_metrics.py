"""Tests for the hand-written retrieval metrics.

Every expected value here is computed by hand in the comment above the
assertion, so the metrics can be defended line by line.
"""

import pytest

from apps.retrieval.types import RetrievedChunk
from eval.golden_set import GoldSource
from eval.metrics import (
    RetrievalOutcome,
    compute_retrieval_metrics,
    first_relevant_rank,
    hit_at_k,
    matches_gold_source,
    mrr_at_k,
    recall_at_k,
)


def _chunk(chunk_id: int, source_path: str, anchor: str) -> RetrievedChunk:
    """Build a minimal retrieved chunk for metric tests."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=1,
        title="Title",
        source_path=source_path,
        heading_path="Title > Section",
        anchor=anchor,
        url=f"https://docs.djangoproject.com/en/5.2/{source_path.removesuffix('.txt')}/",
        text="Body text.",
        score=1.0 - (chunk_id / 100),
    )


def _outcome(
    question_id: str,
    retrieved: list[RetrievedChunk],
    gold: list[GoldSource],
    *,
    answerable: bool = True,
) -> RetrievalOutcome:
    """Pair an ordered retrieval result with its ground truth."""
    return RetrievalOutcome(
        question_id=question_id,
        answerable=answerable,
        retrieved=retrieved,
        gold_sources=gold,
    )


GOLD_MODELS = GoldSource(path="topics/db/models.txt", anchor="field-options")
GOLD_QUERIES = GoldSource(path="topics/db/queries.txt", anchor="making-queries")


def test_matches_gold_source_requires_path_and_anchor() -> None:
    """A chunk matches only when both path and anchor agree."""
    wrong_anchor = _chunk(2, "topics/db/models.txt", "other")
    wrong_path = _chunk(3, "topics/db/queries.txt", "field-options")

    assert matches_gold_source(_chunk(1, "topics/db/models.txt", "field-options"), [GOLD_MODELS])
    assert not matches_gold_source(wrong_anchor, [GOLD_MODELS])
    assert not matches_gold_source(wrong_path, [GOLD_MODELS])


def test_matches_gold_source_supports_path_level_labels() -> None:
    """An empty gold anchor accepts any anchor within the labelled file."""
    path_level = GoldSource(path="topics/db/models.txt", anchor="")

    assert matches_gold_source(_chunk(1, "topics/db/models.txt", "anything"), [path_level])
    assert not matches_gold_source(_chunk(2, "topics/db/queries.txt", "anything"), [path_level])


def test_first_relevant_rank_is_one_based_and_respects_cutoff() -> None:
    """The first match is reported as a 1-based rank, or None past the cutoff."""
    retrieved = [
        _chunk(1, "topics/db/queries.txt", "x"),
        _chunk(2, "topics/db/models.txt", "y"),
        _chunk(3, "topics/db/models.txt", "field-options"),
    ]

    # Rank 1 misses; rank 2 matches the path but not the anchor; rank 3 matches.
    assert first_relevant_rank(retrieved, [GOLD_MODELS], k=10) == 3
    assert first_relevant_rank(retrieved, [GOLD_MODELS], k=2) is None
    assert first_relevant_rank(retrieved, [GOLD_MODELS], k=3) == 3
    assert first_relevant_rank(retrieved, [GOLD_MODELS], k=0) is None


def test_recall_at_k_averages_over_questions() -> None:
    """Recall@2 = (1.0 + 0.5) / 2 = 0.75 for hand-built outcomes."""
    perfect = _outcome("q001", [_chunk(1, "topics/db/models.txt", "field-options")], [GOLD_MODELS])
    partial = _outcome(
        "q002",
        [
            _chunk(1, "topics/db/models.txt", "field-options"),
            _chunk(2, "topics/db/queries.txt", "unrelated"),
        ],
        [GOLD_MODELS, GOLD_QUERIES],
    )

    assert recall_at_k([perfect], 2) == 1.0
    assert recall_at_k([partial], 2) == 0.5
    assert recall_at_k([perfect, partial], 2) == 0.75


def test_recall_at_k_cutoff_drops_late_hits() -> None:
    """A gold source found only at rank 3 does not count towards recall@2."""
    outcome = _outcome(
        "q001",
        [
            _chunk(1, "topics/db/queries.txt", "x"),
            _chunk(2, "topics/db/queries.txt", "y"),
            _chunk(3, "topics/db/models.txt", "field-options"),
        ],
        [GOLD_MODELS],
    )

    assert recall_at_k([outcome], 2) == 0.0
    assert recall_at_k([outcome], 3) == 1.0


def test_hit_and_mrr_use_the_first_relevant_rank() -> None:
    """First hit at rank 2 gives MRR = 1/2 = 0.5 and hit@10 = 1.0."""
    outcome = _outcome(
        "q001",
        [
            _chunk(1, "topics/db/queries.txt", "x"),
            _chunk(2, "topics/db/models.txt", "field-options"),
        ],
        [GOLD_MODELS],
    )

    assert hit_at_k([outcome], 10) == 1.0
    assert mrr_at_k([outcome], 10) == 0.5


def test_mrr_at_k_averages_reciprocal_ranks() -> None:
    """Ranks 1 and 4 give MRR = (1/1 + 1/4) / 2 = 0.625."""
    first = _outcome("q001", [_chunk(1, "topics/db/models.txt", "field-options")], [GOLD_MODELS])
    fourth = _outcome(
        "q002",
        [
            _chunk(1, "topics/db/queries.txt", "a"),
            _chunk(2, "topics/db/queries.txt", "b"),
            _chunk(3, "topics/db/queries.txt", "c"),
            _chunk(4, "topics/db/models.txt", "field-options"),
        ],
        [GOLD_MODELS],
    )

    assert mrr_at_k([first, fourth], 10) == pytest.approx(0.625)


def test_unanswerable_questions_are_excluded_from_retrieval_metrics() -> None:
    """Questions without ground truth cannot contribute to retrieval quality."""
    unanswerable = _outcome("q099", [], [], answerable=False)

    assert recall_at_k([unanswerable], 5) == 0.0
    assert hit_at_k([unanswerable], 5) == 0.0
    assert mrr_at_k([unanswerable], 10) == 0.0


def test_compute_retrieval_metrics_reports_counts_and_rounded_values() -> None:
    """The aggregate payload carries the counts the results files need."""
    outcome = _outcome("q001", [_chunk(1, "topics/db/models.txt", "field-options")], [GOLD_MODELS])
    unanswerable = _outcome("q099", [], [], answerable=False)

    metrics = compute_retrieval_metrics([outcome, unanswerable])
    payload = metrics.as_dict()

    assert metrics.evaluated_questions == 1
    assert metrics.skipped_unanswerable == 1
    assert payload["recall_at_5"] == 1.0
    assert payload["recall_at_10"] == 1.0
    assert payload["mrr_at_10"] == 1.0
    assert payload["hit_at_5"] == 1.0


def test_compute_retrieval_metrics_is_zero_without_answerable_questions() -> None:
    """A split with no ground truth reports zeros rather than dividing by zero."""
    metrics = compute_retrieval_metrics([])

    assert metrics.evaluated_questions == 0
    assert metrics.as_dict()["recall_at_5"] == 0.0
    assert metrics.as_dict()["mrr_at_10"] == 0.0