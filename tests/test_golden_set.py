"""Tests for the golden-set schema, round-trip, and dataset validation."""

import json
from pathlib import Path

import pytest

from eval.golden_set import (
    SPLIT_DEV,
    SPLIT_HELDOUT,
    GoldenQuestion,
    GoldenSetValidationError,
    GoldSource,
    load_golden_set,
    save_golden_set,
    summarise_golden_set,
    validate_golden_set,
)


def _question(
    question_id: str = "q001",
    *,
    split: str = SPLIT_DEV,
    answerable: bool = True,
    sources: list[GoldSource] | None = None,
) -> GoldenQuestion:
    """Build a golden question with sensible defaults for a test."""
    if sources is None:
        sources = [GoldSource(path="topics/db/models.txt", anchor="field-options")]
        if not answerable:
            sources = []
    return GoldenQuestion(
        id=question_id,
        question="How do you define a model field?",
        gold_sources=sources,
        answerable=answerable,
        split=split,  # type: ignore[arg-type]
    )


def _write_lines(path: Path, records: list[dict[str, object]]) -> Path:
    """Write raw JSONL records so malformed input can be exercised."""
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    return path


def test_round_trip_preserves_every_field(tmp_path: Path) -> None:
    """Saving and reloading a golden set yields the same questions."""
    original = [
        GoldenQuestion(
            id="q001",
            question="How do you define a model field?",
            gold_sources=[GoldSource(path="topics/db/models.txt", anchor="field-options")],
            answerable=True,
            split=SPLIT_DEV,
            notes="drafted then reviewed",
        ),
        _question("q002", split=SPLIT_HELDOUT, answerable=False),
    ]
    target = tmp_path / "golden_set.jsonl"

    save_golden_set(target, original)
    reloaded = load_golden_set(target)

    assert reloaded == original
    assert reloaded[0].notes == "drafted then reviewed"


def test_load_skips_blank_lines(tmp_path: Path) -> None:
    """Blank lines in the JSONL file are ignored rather than treated as records."""
    target = tmp_path / "golden_set.jsonl"
    target.write_text('{"id": "q001", "question": "Q?"}\n\n\n', encoding="utf-8")

    questions = load_golden_set(target)

    assert len(questions) == 1
    assert questions[0].split == SPLIT_DEV
    assert questions[0].answerable is True


def test_load_rejects_invalid_json(tmp_path: Path) -> None:
    """A malformed line reports the file and line number."""
    target = tmp_path / "golden_set.jsonl"
    target.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(GoldenSetValidationError, match="invalid JSON"):
        load_golden_set(target)


def test_load_rejects_non_object_record(tmp_path: Path) -> None:
    """A JSON array is not a valid golden-set record."""
    target = _write_lines(tmp_path / "golden_set.jsonl", [["q001"]])  # type: ignore[list-item]

    with pytest.raises(GoldenSetValidationError, match="must be a JSON object"):
        load_golden_set(target)


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"question": "Missing id?"}, "field 'id'"),
        ({"id": "q001"}, "field 'question'"),
        ({"id": "q001", "question": "Q?", "answerable": "yes"}, "must be a boolean"),
        ({"id": "q001", "question": "Q?", "split": "test"}, "split must be"),
        ({"id": "q001", "question": "Q?", "gold_sources": {}}, "'gold_sources' must be a list"),
        (
            {"id": "q001", "question": "Q?", "gold_sources": ["topics/db/models.txt"]},
            "must be an object",
        ),
        (
            {"id": "q001", "question": "Q?", "gold_sources": [{"anchor": "x"}]},
            "field 'path'",
        ),
    ],
)
def test_load_rejects_malformed_fields(
    tmp_path: Path, record: dict[str, object], expected: str
) -> None:
    """Each schema violation fails with a precise message."""
    target = _write_lines(tmp_path / "golden_set.jsonl", [record])

    with pytest.raises(GoldenSetValidationError, match=expected):
        load_golden_set(target)


def test_validate_accepts_a_well_formed_dataset(tmp_path: Path) -> None:
    """A dataset with both splits and consistent answerability passes."""
    corpus = tmp_path / "docs"
    (corpus / "topics" / "db").mkdir(parents=True)
    (corpus / "topics" / "db" / "models.txt").write_text("Models\n======\n", encoding="utf-8")
    questions = [_question("q001"), _question("q002", split=SPLIT_HELDOUT, answerable=False)]

    validate_golden_set(questions, corpus_root=corpus)


def test_validate_rejects_empty_dataset() -> None:
    """An empty golden set is rejected: there is nothing to measure."""
    with pytest.raises(GoldenSetValidationError, match="empty"):
        validate_golden_set([])


@pytest.mark.parametrize(
    ("questions", "expected"),
    [
        ([_question("q1"), _question("q002")], "must match"),
        ([_question("q001"), _question("q001")], "duplicate question id"),
        (
            [_question("q001", sources=[]), _question("q002", split=SPLIT_HELDOUT)],
            "needs at least one gold source",
        ),
        (
            [
                _question(
                    "q001",
                    answerable=False,
                    sources=[GoldSource(path="topics/db/models.txt", anchor="x")],
                ),
                _question("q002", split=SPLIT_HELDOUT),
            ],
            "must not declare gold sources",
        ),
        (
            [
                _question("q001", sources=[GoldSource(path="topics/db/models.rst", anchor="x")]),
                _question("q002", split=SPLIT_HELDOUT),
            ],
            "must be an RST file",
        ),
    ],
)
def test_validate_rejects_broken_questions(
    questions: list[GoldenQuestion], expected: str
) -> None:
    """Identifier, answerability, and path-shape violations are all caught."""
    with pytest.raises(GoldenSetValidationError, match=expected):
        validate_golden_set(questions)


def test_validate_requires_both_splits() -> None:
    """A single-split dataset is rejected because heldout reporting needs both."""
    with pytest.raises(GoldenSetValidationError, match="both a dev and a heldout split"):
        validate_golden_set([_question("q001")])

    validate_golden_set([_question("q001")], require_both_splits=False)


def test_validate_checks_gold_paths_against_the_corpus(tmp_path: Path) -> None:
    """A labelled path that is absent from the pinned corpus is rejected."""
    corpus = tmp_path / "docs"
    corpus.mkdir()
    questions = [
        _question("q001", sources=[GoldSource(path="topics/db/missing.txt", anchor="x")]),
        _question("q002", split=SPLIT_HELDOUT),
    ]

    with pytest.raises(GoldenSetValidationError, match="is not in the corpus"):
        validate_golden_set(questions, corpus_root=corpus)


def test_summarise_reports_split_and_answerability_counts() -> None:
    """The summary exposes the counts the README must quote."""
    questions = [
        _question("q001"),
        _question("q002"),
        _question("q003", split=SPLIT_HELDOUT),
        _question("q004", split=SPLIT_HELDOUT, answerable=False),
    ]

    summary = summarise_golden_set(questions)

    assert summary.total == 4
    assert summary.answerable == 3
    assert summary.unanswerable == 1
    assert summary.dev == 2
    assert summary.heldout == 2
    assert summary.answerable_ratio == pytest.approx(0.75)


def test_summary_ratio_is_zero_for_an_empty_set() -> None:
    """An empty set reports a zero ratio instead of dividing by zero."""
    assert summarise_golden_set([]).answerable_ratio == 0.0