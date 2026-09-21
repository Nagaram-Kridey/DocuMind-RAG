"""Hand-written retrieval metrics: recall@k and MRR.

These are deliberately implemented from scratch rather than imported from an
evaluation framework, because the results table in the README must be
explainable line by line in an interview.

Ground truth is expressed as ``(source_path, anchor)`` pairs rather than chunk
IDs, so the metrics stay valid across re-chunking experiments. A retrieved
chunk satisfies a gold source when both the corpus-relative path and the anchor
match; a gold source with an empty anchor is a path-level label and matches any
anchor within that file.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from apps.retrieval.types import RetrievedChunk

from .golden_set import PATH_LEVEL_ANCHOR, GoldSource

DEFAULT_RECALL_K: Final = (5, 10)
DEFAULT_MRR_K: Final = 10


@dataclass(frozen=True)
class RetrievalOutcome:
    """One question's retrieved chunks paired with its ground-truth sources."""

    question_id: str
    answerable: bool
    retrieved: list[RetrievedChunk]
    gold_sources: list[GoldSource]


@dataclass(frozen=True)
class RetrievalMetrics:
    """Aggregate retrieval quality over the answerable questions in a split."""

    evaluated_questions: int
    skipped_unanswerable: int
    recall_at: dict[int, float]
    hit_at: dict[int, float]
    mrr_at: dict[int, float]

    def as_dict(self) -> dict[str, float | int]:
        """Return a JSON-serialisable metrics payload for the results files."""
        payload: dict[str, float | int] = {
            "evaluated_questions": self.evaluated_questions,
            "skipped_unanswerable": self.skipped_unanswerable,
        }
        for k, value in sorted(self.recall_at.items()):
            payload[f"recall_at_{k}"] = round(value, 6)
        for k, value in sorted(self.hit_at.items()):
            payload[f"hit_at_{k}"] = round(value, 6)
        for k, value in sorted(self.mrr_at.items()):
            payload[f"mrr_at_{k}"] = round(value, 6)
        return payload


def matches_gold_source(chunk: RetrievedChunk, gold_sources: Sequence[GoldSource]) -> bool:
    """Return whether a retrieved chunk satisfies any gold source."""
    for source in gold_sources:
        if chunk.source_path != source.path:
            continue
        if source.anchor == PATH_LEVEL_ANCHOR or chunk.anchor == source.anchor:
            return True
    return False


def first_relevant_rank(
    retrieved: Sequence[RetrievedChunk], gold_sources: Sequence[GoldSource], k: int
) -> int | None:
    """Return the 1-based rank of the first matching chunk within the top ``k``."""
    if k <= 0:
        return None
    for rank, chunk in enumerate(retrieved[:k], start=1):
        if matches_gold_source(chunk, gold_sources):
            return rank
    return None


def recall_at_k(outcomes: Sequence[RetrievalOutcome], k: int) -> float:
    """Return mean source recall@k over answerable questions.

    For each question, recall is the share of its gold sources that appear in
    the top ``k`` results. Averaging gives 1.0 when every question surfaced all
    of its ground truth.
    """
    answerable = [outcome for outcome in outcomes if outcome.answerable and outcome.gold_sources]
    if not answerable:
        return 0.0

    scores: list[float] = []
    for outcome in answerable:
        top_k = outcome.retrieved[:k] if k > 0 else []
        found = sum(
            1
            for source in outcome.gold_sources
            if any(matches_gold_source(chunk, [source]) for chunk in top_k)
        )
        scores.append(found / len(outcome.gold_sources))
    return sum(scores) / len(scores)


def hit_at_k(outcomes: Sequence[RetrievalOutcome], k: int) -> float:
    """Return the share of answerable questions with at least one gold hit."""
    answerable = [outcome for outcome in outcomes if outcome.answerable and outcome.gold_sources]
    if not answerable:
        return 0.0
    hits = sum(
        1
        for outcome in answerable
        if first_relevant_rank(outcome.retrieved, outcome.gold_sources, k) is not None
    )
    return hits / len(answerable)


def mrr_at_k(outcomes: Sequence[RetrievalOutcome], k: int) -> float:
    """Return mean reciprocal rank of the first relevant chunk within top ``k``."""
    answerable = [outcome for outcome in outcomes if outcome.answerable and outcome.gold_sources]
    if not answerable:
        return 0.0
    reciprocal_ranks = [
        1.0 / rank if (rank := first_relevant_rank(o.retrieved, o.gold_sources, k)) else 0.0
        for o in answerable
    ]
    return sum(reciprocal_ranks) / len(answerable)


def compute_retrieval_metrics(
    outcomes: Sequence[RetrievalOutcome],
    *,
    recall_k: Sequence[int] = DEFAULT_RECALL_K,
    mrr_k: int = DEFAULT_MRR_K,
) -> RetrievalMetrics:
    """Compute the full retrieval metric set for one split and one mode."""
    answerable = [outcome for outcome in outcomes if outcome.answerable and outcome.gold_sources]
    return RetrievalMetrics(
        evaluated_questions=len(answerable),
        skipped_unanswerable=len(outcomes) - len(answerable),
        recall_at={k: recall_at_k(outcomes, k) for k in recall_k},
        hit_at={k: hit_at_k(outcomes, k) for k in recall_k},
        mrr_at={mrr_k: mrr_at_k(outcomes, mrr_k)},
    )