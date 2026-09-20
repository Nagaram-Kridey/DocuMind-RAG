"""Minimal RST parsing for the pinned Django documentation corpus."""

import re
from dataclasses import dataclass
from pathlib import Path

_ADORNMENT_CHARACTERS = frozenset("=-~^\"'+*#:")
_ANCHOR_PATTERN = re.compile(r"^\.\. _([a-zA-Z0-9_.:-]+):\s*$")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class ParsedSection:
    """A heading-bounded source section ready for chunking."""

    source_path: str
    heading_path: tuple[str, ...]
    anchor: str
    content: str


@dataclass(frozen=True)
class ParsedDocument:
    """The extracted title and sections of a single RST document."""

    source_path: str
    title: str
    sections: tuple[ParsedSection, ...]


def parse_rst(source_path: str, text: str) -> ParsedDocument:
    """Parse RST headings and explicit anchors without rendering the document."""
    lines = text.splitlines()
    headings = _find_headings(lines)
    title = headings[0][1] if headings else Path(source_path).stem.replace("_", " ").title()
    section_headings = headings[1:] if headings else []
    sections: list[ParsedSection] = []
    marker_levels: dict[str, int] = {}
    heading_stack: list[str] = [title]

    first_content_line = headings[0][3] if headings else 0
    if section_headings:
        _append_section(
            sections,
            source_path,
            heading_stack,
            _anchor_before(lines, headings[0][0]) if headings else None,
            lines[first_content_line : section_headings[0][0]],
        )

    for index, (line_number, heading, marker, content_start) in enumerate(section_headings):
        level = marker_levels.setdefault(marker, len(marker_levels) + 1)
        heading_stack = heading_stack[:level]
        heading_stack.append(heading)
        next_line = (
            section_headings[index + 1][0] if index + 1 < len(section_headings) else len(lines)
        )
        _append_section(
            sections,
            source_path,
            heading_stack,
            _anchor_before(lines, line_number),
            lines[content_start:next_line],
        )

    if not headings:
        _append_section(sections, source_path, heading_stack, None, lines)
    return ParsedDocument(source_path=source_path, title=title, sections=tuple(sections))


def parse_rst_file(path: Path, corpus_root: Path) -> ParsedDocument:
    """Read and parse an RST file using a corpus-relative source path."""
    return parse_rst(path.relative_to(corpus_root).as_posix(), path.read_text(encoding="utf-8"))


def _find_headings(lines: list[str]) -> list[tuple[int, str, str, int]]:
    """Find simple two-line RST headings outside indented code blocks."""
    headings: list[tuple[int, str, str, int]] = []
    for index in range(len(lines) - 1):
        heading = lines[index]
        underline = lines[index + 1].strip()
        if heading.startswith((" ", "\t")) or not heading.strip() or len(underline) < 3:
            continue
        if len(set(underline)) == 1 and underline[0] in _ADORNMENT_CHARACTERS:
            headings.append((index, heading.strip(), underline[0], index + 2))
    return headings


def _anchor_before(lines: list[str], heading_line: int) -> str | None:
    """Return an explicit target immediately associated with a heading."""
    for line in reversed(lines[max(0, heading_line - 3) : heading_line]):
        match = _ANCHOR_PATTERN.match(line)
        if match:
            return match.group(1)
        if line.strip():
            break
    return None


def _append_section(
    sections: list[ParsedSection],
    source_path: str,
    heading_path: list[str],
    explicit_anchor: str | None,
    content_lines: list[str],
) -> None:
    """Add a nonempty section with a stable explicit or heading-derived anchor."""
    content = "\n".join(content_lines).strip()
    if not content:
        return
    anchor = explicit_anchor or _slugify("-".join(heading_path[1:] or heading_path))
    sections.append(
        ParsedSection(
            source_path=source_path,
            heading_path=tuple(heading_path),
            anchor=anchor,
            content=content,
        )
    )


def _slugify(value: str) -> str:
    """Create a predictable anchor when an RST target is not available."""
    return _NON_ALPHANUMERIC.sub("-", value.lower()).strip("-")
