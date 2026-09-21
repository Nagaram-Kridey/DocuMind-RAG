"""Tests for the LLM-assisted golden-set drafting flow."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from eval import build_golden_set as bgs
from eval.golden_set import (
    SPLIT_DEV,
    SPLIT_HELDOUT,
    summarise_golden_set,
    validate_golden_set,
)


@dataclass
class FakeResponse:
    text: str


class FakeLLMClient:
    """Returns scripted responses in call order."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses

    def generate(self, system: str, user: str) -> FakeResponse:
        return FakeResponse(self._responses.pop(0))


def _make_answerable_response() -> str:
    entries = [{"index": i + 1, "question": f"Question about excerpt {i + 1}?"} for i in range(9)]
    return str(entries).replace("'", '"')


def _sampled_chunks() -> list[dict[str, str]]:
    return [
        {
            "path": f"topics/db/models{i}.txt",
            "anchor": f"anchor-{i}",
            "heading_path": f"Models > Section {i}",
            "text": f"Excerpt text {i}.",
        }
        for i in range(9)
    ]


def _full_client() -> FakeLLMClient:
    responses = [_make_answerable_response() for _ in bgs.TOPIC_AREAS]
    responses.append(str([{"question": f"Off-topic {i}?"} for i in range(10)]).replace("'", '"'))
    return FakeLLMClient(responses)


def test_parse_accepts_fenced_array_and_skips_malformed() -> None:
    text = (
        '```json\n[{"index": 1, "question": "Q1?"}, "junk", {"question": ""},'
        ' {"index": 2, "question": "Q2?"}]\n```'
    )
    items = bgs.parse_draft_items(text, require_sources=True)
    assert [(i["index"], i["question"]) for i in items] == [("1", "Q1?"), ("2", "Q2?")]


def test_parse_raises_without_array() -> None:
    with pytest.raises(bgs.GoldenSetDraftError):
        bgs.parse_draft_items("No JSON here at all.", require_sources=True)


def test_parse_unanswerable_ignores_sources() -> None:
    items = bgs.parse_draft_items('[{"question": "Q?"}, {"question": "R?"}]', require_sources=False)
    assert [i["question"] for i in items] == ["Q?", "R?"]


def test_draft_area_uses_db_provenance_not_llm_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """A hallucinated LLM index/path never invents provenance."""
    monkeypatch.setattr(bgs, "sample_chunks_for_area", lambda *a, **k: _sampled_chunks())
    client = FakeLLMClient(
        [
            '[{"index": 999, "question": "Valid?"}, '
            '{"index": 3, "question": "Also valid?"}, '
            '{"index": 1, "question": "First?"}]'
        ]
    )
    drafted = bgs.draft_area_questions(
        client, "models", "topics/db/", per_area=2, excerpt_chars=900
    )
    # Index 999 is dropped; index 3 (1-based) maps to the third sampled chunk.
    assert drafted == [
        {"question": "Also valid?", "path": "topics/db/models2.txt", "anchor": "anchor-2"},
        {"question": "First?", "path": "topics/db/models0.txt", "anchor": "anchor-0"},
    ]


def test_draft_area_deduplicates_and_raises_when_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bgs, "sample_chunks_for_area", lambda *a, **k: _sampled_chunks())
    client = FakeLLMClient(
        ['[{"index": 1, "question": "Same?"}, {"index": 2, "question": "Same?"}]']
    )
    with pytest.raises(bgs.GoldenSetDraftError, match="usable questions"):
        bgs.draft_area_questions(client, "models", "topics/db/", per_area=3, excerpt_chars=900)


def test_build_draft_composition_and_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bgs, "sample_chunks_for_area", lambda *a, **k: _sampled_chunks())
    questions = bgs.build_draft(
        _full_client(), per_area=9, excerpt_chars=900, unanswerable_count=10
    )
    summary = summarise_golden_set(questions)

    assert summary.total == 100
    assert summary.answerable == 90
    assert summary.unanswerable == 10
    assert summary.dev == 70
    assert summary.heldout == 30
    assert [q.id for q in questions] == [f"q{i:03d}" for i in range(1, 101)]
    validate_golden_set(questions)


def test_split_assignment_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bgs, "sample_chunks_for_area", lambda *a, **k: _sampled_chunks())
    questions = bgs.build_draft(
        _full_client(), per_area=9, excerpt_chars=900, unanswerable_count=10
    )

    # Block layout: 10 questions per block; answerable first, unanswerable last.
    first_block = questions[:10]
    assert [q.split for q in first_block] == [
        SPLIT_DEV, SPLIT_DEV, SPLIT_HELDOUT, SPLIT_DEV, SPLIT_HELDOUT,
        SPLIT_DEV, SPLIT_DEV, SPLIT_HELDOUT, SPLIT_DEV, SPLIT_DEV,
    ]
    # Unanswerable blocks 1, 4, 7 (0-based) go to heldout.
    unanswerable_splits = [q.split for q in questions if not q.answerable]
    assert unanswerable_splits == [
        SPLIT_DEV, SPLIT_HELDOUT, SPLIT_DEV, SPLIT_HELDOUT,
        SPLIT_DEV, SPLIT_HELDOUT, SPLIT_DEV, SPLIT_DEV, SPLIT_DEV, SPLIT_DEV,
    ]


def test_build_draft_raises_on_empty_answerable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bgs, "sample_chunks_for_area", lambda *a, **k: _sampled_chunks())
    client = FakeLLMClient(["[]"] * (len(bgs.TOPIC_AREAS) + 1))
    with pytest.raises(bgs.GoldenSetDraftError):
        bgs.build_draft(client, per_area=9, excerpt_chars=900, unanswerable_count=10)


def test_unanswerable_deduplicates_and_requires_count() -> None:
    client = FakeLLMClient(['[{"question": "A?"}, {"question": "A?"}, {"question": "B?"}]'])
    assert bgs.draft_unanswerable_questions(client, 2) == ["A?", "B?"]
    with pytest.raises(bgs.GoldenSetDraftError, match="unanswerable"):
        bgs.draft_unanswerable_questions(FakeLLMClient(["[]"]), 2)


def test_prompts_ask_for_index_and_json_only() -> None:
    chunks: list[dict[str, str]] = [
        {"path": "p.txt", "anchor": "a", "heading_path": "H", "text": "T"}
    ]
    system, user = bgs.build_answerable_prompt("models", chunks)
    assert '"index"' in system and "No prose outside the JSON" in system
    assert "[1] path=p.txt" in user
    usys, uuser = bgs.build_unanswerable_prompt(10)
    assert "ABSENT" in usys and "10" in uuser
