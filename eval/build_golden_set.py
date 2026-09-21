"""LLM-assisted drafting of the retrieval evaluation golden set.

Samples chunks across topic areas of the ingested corpus, asks the configured
LLM to draft candidate questions whose answers live in those chunks, and emits
a JSONL draft in exactly the schema ``eval/golden_set.py`` validates. The
script proposes; only a human disposes: the draft must be manually reviewed
(at least 40 questions per ``DOCUMIND_CONTEXT.md`` §9) before it becomes the
committed ``eval/golden_set.jsonl`` used for baseline measurement.

Composition (locked by the specification):
- 90 answerable questions, 9 per topic area, drawn round-robin so the draft is
  not clustered on one topic;
- 10 deliberately unanswerable questions (plausible Django questions whose
  answers are absent from the pinned docs);
- split assignment is deterministic: 27 answerable + 3 unanswerable questions
  go to ``heldout``, the rest to ``dev``, spread evenly across the order.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Protocol, cast

from eval.golden_set import (
    SPLIT_DEV,
    SPLIT_HELDOUT,
    GoldenQuestion,
    GoldSource,
    save_golden_set,
    summarise_golden_set,
    validate_golden_set,
)

ANSWERABLE_PER_AREA: Final = 9
UNANSWERABLE_COUNT: Final = 10
EXCERPT_CHARS_DEFAULT: Final = 900

# Topic areas sampled round-robin so the draft spans the corpus. Each pair is
# (label, source_path prefix inside the pinned docs tree).
TOPIC_AREAS: Final[tuple[tuple[str, str], ...]] = (
    ("models", "topics/db/"),
    ("querysets", "ref/models/querysets"),
    ("fields", "ref/models/fields"),
    ("views", "ref/class-based-views/"),
    ("forms", "topics/forms/"),
    ("auth", "topics/auth/"),
    ("settings", "ref/settings"),
    ("testing", "topics/testing/"),
    ("migrations", "topics/migrations"),
    ("http", "topics/http/"),
)

# Split assignment: 90 answerable questions spread over 10 topic-area blocks
# (9 per block) must yield exactly 27 heldout questions (30% of 90), spread
# evenly: the first seven blocks hold out relative positions 2, 4, 7
# (3 each = 21); the last three blocks hold out positions 2, 4 (2 each = 6).
# Among the 10 unanswerable questions, block indexes 1, 3, 5 go to heldout.
# Total heldout = 27 + 3 = 30; dev = 70. Nothing is random: re-running with
# the same LLM output yields the identical dataset.
_HELDOUT_ANSWERABLE_OFFSETS_EARLY: Final[frozenset[int]] = frozenset({2, 4, 7})
_HELDOUT_ANSWERABLE_OFFSETS_LATE: Final[frozenset[int]] = frozenset({2, 4})
_LATE_HELDOUT_BLOCK_START: Final = 7
_HELDOUT_UNANSWERABLE_BLOCKS: Final[frozenset[int]] = frozenset({1, 3, 5})

_JSON_ARRAY_PATTERN: Final = re.compile(r"\[.*\]", re.DOTALL)
MIN_SAMPLED_CHUNKS: Final = 3


class GoldenSetDraftError(RuntimeError):
    """Raised when the LLM drafting output cannot produce a valid draft."""


class DraftLLMResponse(Protocol):
    """Structural view of a generation result: text plus optional usage."""

    text: str


class DraftLLMClient(Protocol):
    """The narrow generation surface this script depends on."""

    def generate(self, system: str, user: str) -> DraftLLMResponse: ...


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------


def parse_draft_items(text: str, *, require_sources: bool) -> list[dict[str, str]]:
    """Extract draft question items from an LLM response.

    Accepts a bare JSON array or one fenced in a code block. Malformed entries
    are skipped rather than trusted; an entirely unparsable response raises so
    the caller can retry or abort with a clear message.
    """
    match = _JSON_ARRAY_PATTERN.search(text)
    if match is None:
        raise GoldenSetDraftError("LLM response contains no JSON array")
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as error:
        raise GoldenSetDraftError(f"LLM response is not valid JSON: {error}") from error
    if not isinstance(payload, list):
        raise GoldenSetDraftError("LLM response JSON is not an array")

    items: list[dict[str, str]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        question = entry.get("question")
        if not isinstance(question, str) or not question.strip():
            continue
        item = {"question": question.strip()}
        if require_sources:
            index = entry.get("index")
            item["index"] = str(index) if isinstance(index, int) else ""
        items.append(item)
    return items


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_answerable_prompt(area_label: str, chunks: Sequence[dict[str, str]]) -> tuple[str, str]:
    """Return the system/user prompt asking for answerable draft questions."""
    system = (
        "You draft evaluation questions for a documentation retrieval system. "
        "For each numbered excerpt from the Django documentation, write exactly "
        "one question that a Django developer could ask, and whose answer is "
        "contained in that excerpt. Questions must be self-contained (no 'this "
        "function' references), specific, and answerable purely from the excerpt. "
        'Respond with ONLY a JSON array of objects, one per excerpt, shaped as '
        '{"index": <excerpt number>, "question": "..."} using the exact number '
        "shown for that excerpt. No prose outside the JSON."
    )
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[{index}] path={chunk['path']} anchor={chunk['anchor']}\n"
            f"heading: {chunk['heading_path']}\n"
            f"{chunk['text']}"
        )
    user = (
        f"Topic area: {area_label}\n\n"
        + "\n\n".join(blocks)
        + f"\n\nWrite one question per excerpt ({len(chunks)} total) as a JSON array."
    )
    return system, user


def build_unanswerable_prompt(count: int) -> tuple[str, str]:
    """Return the system/user prompt asking for unanswerable draft questions."""
    system = (
        "You draft evaluation questions for a documentation retrieval system. "
        "Write questions a Django developer might plausibly ask, but whose "
        "answers are ABSENT from the official Django 5.2 documentation — for "
        "example third-party packages, pricing, other web frameworks, "
        "non-Django tooling, features introduced in Django versions after 5.2, "
        "or general knowledge unrelated to Django. Questions must look "
        "on-topic and answerable at a glance. "
        'Respond with ONLY a JSON array of objects shaped as {"question": "..."} '
        "with no other fields. No prose outside the JSON."
    )
    user = f"Write {count} such questions as a JSON array."
    return system, user


# ---------------------------------------------------------------------------
# Corpus sampling
# ---------------------------------------------------------------------------


def sample_chunks_for_area(
    path_prefix: str, *, per_area: int, excerpt_chars: int
) -> list[dict[str, str]]:
    """Pick evenly spaced ingested chunks under one topic-area path prefix.

    Even spacing spreads the draft across whole documents instead of clustering
    on the first file alphabetically. Provenance (path/anchor/heading) always
    comes from the database, never from the LLM.
    """
    from apps.documents.models import Chunk

    queryset = (
        Chunk.objects.filter(document__source_path__startswith=path_prefix)
        .select_related("document")
        .order_by("document__source_path", "ordinal")
    )
    total = queryset.count()
    if total < per_area:
        raise GoldenSetDraftError(
            f"topic area {path_prefix!r} has only {total} ingested chunks; need {per_area}"
        )
    step = total / per_area
    wanted = sorted({min(int(i * step), total - 1) for i in range(per_area)})
    chunks: list[dict[str, str]] = []
    for position, chunk in enumerate(queryset.iterator()):
        if position in wanted:
            chunks.append(
                {
                    "path": chunk.document.source_path,
                    "anchor": chunk.anchor,
                    "heading_path": chunk.heading_path,
                    "text": chunk.text[:excerpt_chars],
                }
            )
            if len(chunks) == per_area:
                break
    return chunks


def draft_area_questions(
    client: DraftLLMClient,
    area_label: str,
    path_prefix: str,
    *,
    per_area: int,
    excerpt_chars: int,
) -> list[dict[str, str]]:
    """Draft answerable questions for one topic area with DB-verified provenance.

    The LLM may only choose an excerpt by index; the path/anchor pair is taken
    from the sampled chunk, so a hallucinated source cannot enter the golden
    set. Items without a usable index are dropped.
    """
    chunks = sample_chunks_for_area(path_prefix, per_area=per_area, excerpt_chars=excerpt_chars)
    system, user = build_answerable_prompt(area_label, chunks)
    response = client.generate(system, user)
    items = parse_draft_items(response.text, require_sources=True)
    drafted: list[dict[str, str]] = []
    seen_questions: set[str] = set()
    for item in items:
        try:
            chunk = chunks[int(item["index"]) - 1]
        except (KeyError, ValueError, IndexError):
            continue
        question = item["question"]
        if question in seen_questions:
            continue
        seen_questions.add(question)
        drafted.append({"question": question, "path": chunk["path"], "anchor": chunk["anchor"]})
    if len(drafted) < per_area:
        raise GoldenSetDraftError(
            f"topic area {area_label!r}: LLM drafted {len(drafted)} usable questions, "
            f"need {per_area}"
        )
    return drafted[:per_area]


def draft_unanswerable_questions(client: DraftLLMClient, count: int) -> list[str]:
    """Draft deliberately unanswerable questions (no gold sources by design)."""
    system, user = build_unanswerable_prompt(count)
    response = client.generate(system, user)
    items = parse_draft_items(response.text, require_sources=False)
    questions = list(dict.fromkeys(item["question"] for item in items))
    if len(questions) < count:
        raise GoldenSetDraftError(
            f"LLM drafted {len(questions)} unique unanswerable questions, need {count}"
        )
    return questions[:count]


def build_draft(
    client: DraftLLMClient,
    *,
    per_area: int,
    excerpt_chars: int,
    unanswerable_count: int,
    llm_model: str = "",
) -> list[GoldenQuestion]:
    """Run the full drafting flow and assemble the deterministic split.

    Ordering: one block per topic area containing ``per_area`` answerable
    questions followed by one unanswerable question. Splits come from the fixed
    offset sets, never from randomness, so re-running with the same LLM output
    yields the identical dataset.
    """
    areas = [
        draft_area_questions(client, label, prefix, per_area=per_area, excerpt_chars=excerpt_chars)
        for label, prefix in TOPIC_AREAS
    ]
    unanswerable = draft_unanswerable_questions(client, unanswerable_count)
    if len(unanswerable) < len(areas):
        raise GoldenSetDraftError(
            "not enough unanswerable questions for one per topic-area block"
        )

    questions: list[GoldenQuestion] = []
    for block_index, items in enumerate(areas):
        heldout_offsets = (
            _HELDOUT_ANSWERABLE_OFFSETS_LATE
            if block_index >= _LATE_HELDOUT_BLOCK_START
            else _HELDOUT_ANSWERABLE_OFFSETS_EARLY
        )
        for relative_position, item in enumerate(items):
            questions.append(
                GoldenQuestion(
                    id=f"q{len(questions) + 1:03d}",
                    question=item["question"],
                    gold_sources=[GoldSource(path=item["path"], anchor=item["anchor"])],
                    answerable=True,
                    split=SPLIT_HELDOUT if relative_position in heldout_offsets else SPLIT_DEV,
                    notes=f"model={llm_model}" if llm_model else "",
                )
            )
        questions.append(
            GoldenQuestion(
                id=f"q{len(questions) + 1:03d}",
                question=unanswerable[block_index],
                gold_sources=[],
                answerable=False,
                split=SPLIT_HELDOUT
                if block_index in _HELDOUT_UNANSWERABLE_BLOCKS
                else SPLIT_DEV,
                notes=f"model={llm_model}" if llm_model else "",
            )
        )
    return questions


def main(argv: Sequence[str] | None = None) -> int:
    """Draft the golden set and write the review-ready JSONL file."""
    parser = argparse.ArgumentParser(description="Draft the retrieval golden set with an LLM.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("eval/drafts/golden_set_draft.jsonl"),
        help="Output JSONL path (draft; not the committed golden set).",
    )
    parser.add_argument("--per-area", type=int, default=ANSWERABLE_PER_AREA)
    parser.add_argument("--excerpt-chars", type=int, default=EXCERPT_CHARS_DEFAULT)
    args = parser.parse_args(argv)

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()

    from apps.qa.llm_client import get_llm_client
    from config.corpus import DJANGO_DOCS_RELATIVE_PATH

    client = get_llm_client()
    questions = build_draft(
        cast(DraftLLMClient, client),
        per_area=args.per_area,
        excerpt_chars=args.excerpt_chars,
        unanswerable_count=UNANSWERABLE_COUNT,
        llm_model=getattr(client, "model", ""),
    )
    validate_golden_set(questions, corpus_root=Path(DJANGO_DOCS_RELATIVE_PATH))
    save_golden_set(args.output, questions)
    summary = summarise_golden_set(questions)
    print(f"draft written to {args.output}")
    print(
        f"total={summary.total} answerable={summary.answerable} "
        f"unanswerable={summary.unanswerable} dev={summary.dev} heldout={summary.heldout}"
    )
    print("REMINDER: manually review at least 40 questions before promoting this draft.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

