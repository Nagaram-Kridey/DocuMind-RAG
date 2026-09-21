"""Golden-set schema and load/save helpers.

The golden set is a JSONL file where each line is one evaluation question with
ground-truth sources expressed as corpus-relative ``path`` plus a stable
``anchor``. Anchors (not chunk IDs) are used so the labels survive re-chunking.
"""

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final, Literal

SPLIT_DEV: Final = "dev"
SPLIT_HELDOUT: Final = "heldout"
Split = Literal["dev", "heldout"]

# Question identifiers are stable, sortable, and human-readable: q001, q002, ...
QUESTION_ID_PATTERN: Final = re.compile(r"^q\d{3}$")

# A label may name a source path only (any anchor in that file) or a specific
# section anchor. An empty anchor means "path-level label".
PATH_LEVEL_ANCHOR: Final = ""


class GoldenSetError(ValueError):
    """Base class for golden-set problems."""


class GoldenSetValidationError(GoldenSetError):
    """Raised when a golden-set record or dataset violates the schema."""


@dataclass(frozen=True)
class GoldSource:
    """A single ground-truth source for a question."""

    path: str
    anchor: str


@dataclass(frozen=True)
class GoldenQuestion:
    """One evaluation question and its expected retrieval outcome."""

    id: str
    question: str
    gold_sources: list[GoldSource] = field(default_factory=list)
    answerable: bool = True
    split: Split = SPLIT_DEV
    notes: str = ""

    def to_json_line(self) -> str:
        """Serialise this question as one JSONL record."""
        payload: dict[str, object] = {
            "id": self.id,
            "question": self.question,
            "gold_sources": [asdict(source) for source in self.gold_sources],
            "answerable": self.answerable,
            "split": self.split,
        }
        if self.notes:
            payload["notes"] = self.notes
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def load_golden_set(path: Path) -> list[GoldenQuestion]:
    """Read a JSONL golden set into validated questions."""
    questions: list[GoldenQuestion] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise GoldenSetValidationError(
                f"{path}:{line_number}: invalid JSON: {error}"
            ) from error
        if not isinstance(record, dict):
            raise GoldenSetValidationError(f"{path}:{line_number}: record must be a JSON object")
        questions.append(_question_from_record(record))
    return questions


def save_golden_set(path: Path, questions: list[GoldenQuestion]) -> None:
    """Write questions to a JSONL file, one record per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [question.to_json_line() for question in questions]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _question_from_record(record: dict[str, object]) -> GoldenQuestion:
    """Build a ``GoldenQuestion`` from one decoded JSON object.

    Every field is checked explicitly so a malformed line fails with a precise
    message instead of being coerced into a plausible-looking question.
    """
    question_id = _require_str(record, "id")
    return GoldenQuestion(
        id=question_id,
        question=_require_str(record, "question"),
        gold_sources=_sources_from_record(record, question_id),
        answerable=_optional_bool(record, "answerable", question_id=question_id),
        split=_split_from_record(record, question_id),
        notes=_optional_str(record, "notes"),
    )


def _require_str(record: dict[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GoldenSetValidationError(f"record field '{key}' must be a non-empty string")
    return value.strip()


def _optional_str(record: dict[str, object], key: str) -> str:
    """Return an optional string field, rejecting wrong types."""
    value = record.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise GoldenSetValidationError(f"record field '{key}' must be a string when present")
    return value


def _optional_bool(record: dict[str, object], key: str, *, question_id: str) -> bool:
    """Return an optional boolean field, rejecting truthy non-booleans."""
    value = record.get(key, True)
    if not isinstance(value, bool):
        raise GoldenSetValidationError(f"{question_id}: record field '{key}' must be a boolean")
    return value


def _split_from_record(record: dict[str, object], question_id: str) -> Split:
    """Return the validated dev/heldout split for a record."""
    value = record.get("split", SPLIT_DEV)
    if value == SPLIT_DEV:
        return SPLIT_DEV
    if value == SPLIT_HELDOUT:
        return SPLIT_HELDOUT
    raise GoldenSetValidationError(
        f"{question_id}: split must be '{SPLIT_DEV}' or '{SPLIT_HELDOUT}'"
    )


def _sources_from_record(record: dict[str, object], question_id: str) -> list[GoldSource]:
    """Return the validated gold sources for a record."""
    raw_sources = record.get("gold_sources", [])
    if not isinstance(raw_sources, list):
        raise GoldenSetValidationError(f"{question_id}: 'gold_sources' must be a list")
    sources: list[GoldSource] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            raise GoldenSetValidationError(f"{question_id}: each gold source must be an object")
        sources.append(
            GoldSource(
                path=_require_str(raw_source, "path"),
                anchor=_optional_str(raw_source, "anchor"),
            )
        )
    return sources


def validate_golden_set(
    questions: list[GoldenQuestion],
    *,
    corpus_root: Path | None = None,
    require_both_splits: bool = True,
) -> None:
    """Assert dataset-level invariants before any metric is computed.

    Checks identifiers, split values, answerable/unanswerable shape, and
    (optionally) that every labelled source path exists in the pinned corpus.
    Raising here is deliberate: a baseline measured against a malformed golden
    set is worse than no baseline, because the number still looks credible.
    """
    if not questions:
        raise GoldenSetValidationError("golden set is empty")

    seen: set[str] = set()
    for question in questions:
        if not QUESTION_ID_PATTERN.match(question.id):
            raise GoldenSetValidationError(
                f"{question.id}: question id must match {QUESTION_ID_PATTERN.pattern}"
            )
        if question.id in seen:
            raise GoldenSetValidationError(f"{question.id}: duplicate question id")
        seen.add(question.id)

        if question.answerable and not question.gold_sources:
            raise GoldenSetValidationError(
                f"{question.id}: an answerable question needs at least one gold source"
            )
        if not question.answerable and question.gold_sources:
            raise GoldenSetValidationError(
                f"{question.id}: an unanswerable question must not declare gold sources"
            )

        for source in question.gold_sources:
            if not source.path.endswith(".txt"):
                raise GoldenSetValidationError(
                    f"{question.id}: gold source path must be an RST file: {source.path}"
                )
            if corpus_root is not None and not (corpus_root / source.path).is_file():
                raise GoldenSetValidationError(
                    f"{question.id}: gold source path is not in the corpus: {source.path}"
                )

    splits = {question.split for question in questions}
    if require_both_splits and splits != {SPLIT_DEV, SPLIT_HELDOUT}:
        raise GoldenSetValidationError("golden set must contain both a dev and a heldout split")


@dataclass(frozen=True)
class GoldenSetSummary:
    """Counts used to verify the golden set before trusting its metrics."""

    total: int
    answerable: int
    unanswerable: int
    dev: int
    heldout: int

    @property
    def answerable_ratio(self) -> float:
        """Return the share of questions that have ground truth."""
        return self.answerable / self.total if self.total else 0.0


def summarise_golden_set(questions: list[GoldenQuestion]) -> GoldenSetSummary:
    """Return split and answerability counts for reporting."""
    splits = Counter(question.split for question in questions)
    answerable = sum(1 for question in questions if question.answerable)
    return GoldenSetSummary(
        total=len(questions),
        answerable=answerable,
        unanswerable=len(questions) - answerable,
        dev=splits[SPLIT_DEV],
        heldout=splits[SPLIT_HELDOUT],
    )