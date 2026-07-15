"""parser.py — split scen*E.txt into Entry + Segment dataclasses.

Each non-blank line of a scen file is exactly one entry. The entry's
last control code (`<$FFFF>` or `<$FFFE>`) is its terminator. Inside
the entry, the parser tokenizes the raw string into a flat list of
Segments of three kinds:

    text   — visible characters (no `<$...>` escapes inside)
    ctrl   — a control code `<$XXXX>` or multi-word like `<$XXXX...>`
    token  — `<$F600><$0000>` protagonist-name placeholder
             OR the legacy authoring marker `[diehardt's name]`
             (which the encoder rewrites to F600/0000 — see
             d00_tools.py:178-184). Both are normalized to the
             string `<$F600><$0000>` so the simulator looks them up
             in `text_measure.SPECIAL_TOKEN_WIDTHS` uniformly.

The parser does NOT classify layout, does NOT measure tiles, does
NOT validate budgets. Those are downstream concerns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal


SegmentKind = Literal['text', 'ctrl', 'token']

# Pattern for an escape sequence: `<$XXXX>` where XXXX is one or more
# hex words. Engine codes are single 4-hex (e.g. `<$FFFE>`) but the
# encoder accepts longer concatenations — we capture the full bracketed
# token as a single ctrl segment.
ESCAPE_RE = re.compile(r'<\$([0-9A-Fa-f]+)>')

# The protagonist name marker the encoder treats as F600/0000.
DIEHARDT_MARKER_RE = re.compile(r"\[diehardt's name\]", re.IGNORECASE)

# The normalized token form we emit for any protagonist-name placeholder.
PROTAGONIST_TOKEN = '<$F600><$0000>'


@dataclass
class Segment:
    """A piece of an Entry's raw text after control-code tokenization."""
    kind: SegmentKind
    value: str

    def __repr__(self) -> str:
        return f'Segment({self.kind!r}, {self.value!r})'


@dataclass
class Entry:
    """One non-blank line of a scen script, tokenized.

    Attributes:
        scen_id: 'scen019' (no E suffix, no extension).
        index: zero-based position within the file (0 = first entry).
        raw: the line exactly as it appears in the source file
            (no normalization, no trailing newline).
        terminator: 'FFFE' or 'FFFF' (uppercase, no `<$...>` wrapper).
            For lines that lack a recognized terminator (extremely
            rare per investigation), the value is the empty string.
        segments: ordered list of Segments covering the full raw line,
            terminator inclusive.
    """
    scen_id: str
    index: int
    raw: str
    terminator: str
    segments: List[Segment] = field(default_factory=list)


def _tokenize(line: str) -> List[Segment]:
    """Walk a single line and produce the flat Segment list.

    Order of resolution at each position:
        1. `[diehardt's name]` marker  → token PROTAGONIST_TOKEN
        2. `<$F600><$0000>` literal    → token PROTAGONIST_TOKEN
        3. `<$XXXX>` escape            → ctrl (entire bracketed span)
        4. otherwise                   → accumulate into text segment
    """
    segments: List[Segment] = []
    text_buf: List[str] = []

    def flush_text() -> None:
        if text_buf:
            segments.append(Segment('text', ''.join(text_buf)))
            text_buf.clear()

    i = 0
    n = len(line)
    while i < n:
        # 1. [diehardt's name]
        m_marker = DIEHARDT_MARKER_RE.match(line, i)
        if m_marker:
            flush_text()
            segments.append(Segment('token', PROTAGONIST_TOKEN))
            i = m_marker.end()
            continue

        # 2 + 3. <$XXXX> family — check for the special protagonist pair first
        if line.startswith(PROTAGONIST_TOKEN, i):
            flush_text()
            segments.append(Segment('token', PROTAGONIST_TOKEN))
            i += len(PROTAGONIST_TOKEN)
            continue

        m_esc = ESCAPE_RE.match(line, i)
        if m_esc:
            flush_text()
            segments.append(Segment('ctrl', m_esc.group(0)))
            i = m_esc.end()
            continue

        # 4. plain text char
        text_buf.append(line[i])
        i += 1

    flush_text()
    return segments


def _terminator_of(segments: List[Segment]) -> str:
    """Identify the entry's SEMANTIC terminator.

    FFFE = end-of-dialogue-message; FFFF = string terminator. A dialogue entry
    ends in FFFE and may carry a trailing FFFF as the string terminator (the JP
    pattern `<$FFFE><$FFFF>`, restored to the last entry of 61 sections
    2026-06-14). A pure LABEL (nameplate / location title) ends in FFFF with NO
    preceding FFFE. So: if FFFE is the last terminator, OR the last is FFFF and
    the one immediately before it is FFFE, the entry is FFFE-terminated
    (dialogue). Only a trailing FFFF with no FFFE before it is FFFF (label).

    Some lines have trailing whitespace AFTER the terminator (e.g.
    `'Urggh!<$FFFE> '`); we scan backwards through ctrl segments to find the
    structural terminators regardless of trailing text.

    Returns 'FFFE', 'FFFF', or '' if no FFFE/FFFF ctrl appears in the entry.
    """
    trailing: List[str] = []   # terminator codes, last-first
    for seg in reversed(segments):
        if seg.kind != 'ctrl':
            continue
        m = ESCAPE_RE.fullmatch(seg.value)
        if not m:
            continue
        hex_payload = m.group(1).upper()
        tail = hex_payload[-4:] if len(hex_payload) >= 4 else hex_payload
        if tail in ('FFFE', 'FFFF'):
            trailing.append(tail)
            if len(trailing) == 2:
                break
    if not trailing:
        return ''
    if trailing[0] == 'FFFE':
        return 'FFFE'
    # trailing[0] == 'FFFF': dialogue iff an FFFE sits immediately before it.
    if len(trailing) >= 2 and trailing[1] == 'FFFE':
        return 'FFFE'
    return 'FFFF'


def parse_scenario(path: Path) -> List[Entry]:
    """Read a `scenNNNE.txt` file and return its tokenized entries.

    Blank lines are skipped (no Entry produced). Trailing newlines are
    stripped from `raw`. Entries are indexed by their order of
    appearance among the non-blank lines.
    """
    scen_id = path.stem.lower()
    if scen_id.endswith('e'):
        scen_id = scen_id[:-1]  # 'scen019E' → 'scen019'
    entries: List[Entry] = []
    idx = 0
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        if not raw_line.strip():
            continue
        segments = _tokenize(raw_line)
        terminator = _terminator_of(segments)
        entries.append(
            Entry(
                scen_id=scen_id,
                index=idx,
                raw=raw_line,
                terminator=terminator,
                segments=segments,
            )
        )
        idx += 1
    return entries


def parse_all(scripts_dir: Path) -> List[Entry]:
    """Convenience: parse every `scen*E.txt` in a directory in sorted order."""
    out: List[Entry] = []
    for path in sorted(scripts_dir.glob('scen*E.txt')):
        out.extend(parse_scenario(path))
    return out
