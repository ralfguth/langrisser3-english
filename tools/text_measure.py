"""text_measure.py — pure tile-count for visible-text segments.

Mirrors the greedy left-to-right tile-emission loop of
`d00_tools.encode_text_to_entry` (file `d00_tools.py`, lines 245-285)
WITHOUT writing any bytes. The point is to know how many tiles a
rendered text segment will consume on screen, so the layout simulator
can detect overflow before the encoder runs.

Single responsibility per the SOLID directive: this module does ONE
thing — count tiles. It does not segment control codes, does not run
state machines, does not classify, does not render. Callers strip
control codes BEFORE calling `measure_tiles`; the only "control" this
module knows is the `next_is_inline` flag, which tells it whether the
trailing-space-skip rule (d00_tools.py:262-267) should reach across
the segment boundary.

Why mirror instead of import: `encode_text_to_entry` is tightly
coupled to byte emission (`result.extend(struct.pack('>H', ...))`).
Reusing it would require either threading a "count-only mode" flag
through that hot loop, or wrapping the output and dividing by 2 —
both of which entangle two concerns. A focused replica is simpler,
covered by a parity test that asserts equivalence on real corpus data.

The protagonist token `<$F600><$0000>` is a special case: its
RENDERED width is up to 8 zenkaku full-width chars (per F1 decision).
Callers should consult `SPECIAL_TOKEN_WIDTHS["<$F600><$0000>"]` when
the parser hands them this token, rather than ever passing the
literal substring to `measure_tiles` (which would yield 0 because
control-code bytes aren't in CHAR_TILE_MAP).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator, Tuple

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP  # noqa: E402
from d00_tools import (  # noqa: E402
    RIGHT_BLANK_STANDALONE_CHARS,
    LEFT_BLANK_STANDALONE_CHARS,
)

# The data-driven layout is now production (font_tools Part 6 swap, 2026-06-26):
# measure the balloon budget against the packed BIGRAM_TILE_MAP + the rigorous
# trailing-(c,space) rule — the same encoding the build ships.
_ACTIVE_BIGRAM = BIGRAM_TILE_MAP
_ACTIVE_TRAILING = True

# The map/char set actually used for measurement (consumed by layout_qa's
# encoding-risk check so its coverage matches the active font).
ACTIVE_BIGRAM_MAP = _ACTIVE_BIGRAM
ACTIVE_CHAR_MAP = CHAR_TILE_MAP


# Protagonist's name expands at runtime to up to 8 zenkaku (full-width)
# chars — locked per the F1 decision. The literal F600 0000 control pair
# isn't measurable via the tile maps, so callers look this constant up.
SPECIAL_TOKEN_WIDTHS = {
    "<$F600><$0000>": 8,
}


def measure_tiles(
    text: str,
    *,
    next_is_inline: bool = False,
    bigram_map: dict | None = None,
    trailing: bool | None = None,
) -> int:
    """Tile cost of a visible-text segment.

    Args:
        text: plain text — no control codes, no `<$XXXX>` escapes.
        next_is_inline: True iff the next parser segment is an
            inline-text control code (currently only `<$F600><$0000>`,
            which expands to the player name in the same word-stream).
            Affects the trailing-space-skip rule at the segment tail.
        bigram_map / trailing: override the active font (see iter_tiles).

    Returns:
        Number of tiles the rendered text will occupy on a single
        line, ignoring any line-wrap behavior (callers handle wrap).
    """
    return sum(
        count
        for _, count in iter_tiles(
            text, next_is_inline=next_is_inline,
            bigram_map=bigram_map, trailing=trailing,
        )
    )


def iter_tiles(
    text: str,
    *,
    next_is_inline: bool = False,
    bigram_map: dict | None = None,
    trailing: bool | None = None,
) -> Iterator[Tuple[str, int]]:
    """Yield (substring, tile_count) per emitted tile, in order.

    `tile_count` is 1 for a real tile (1 or 2 source chars). The one
    exception is a redundant ASCII space baked into the previous tile's
    right-half blank: it is yielded as `(' ', 0)` — zero width (the
    encoder writes no separate tile for it) but still REPRESENTED, so
    the joined substrings reproduce the real rendered text and word
    boundaries are not lost. Summing tile_count stays byte-exact with
    `encode_text_to_entry`.

    `substring` is the source text consumed (1 or 2 chars for bigram).
    The simulator uses this to know, per tile, whether the boundary
    character is whitespace (for `broken_word_wrap` detection).

    Yields nothing for chars that would be silently dropped by the
    encoder (unmapped chars not in CHAR_TILE_MAP or any bigram). The
    simulator/caller is responsible for flagging `encoding_risk`.
    """
    big = _ACTIVE_BIGRAM if bigram_map is None else bigram_map
    trail = _ACTIVE_TRAILING if trailing is None else trailing
    s = text.replace('...', '…')
    j = 0
    last_was_right_blank = False
    n = len(s)
    while j < n:
        # Skip a redundant ASCII space when the previous tile carried
        # a built-in right-half blank AND either there's more text in
        # this segment OR the next parser segment is inline text
        # (e.g. <$F600><$0000>). See d00_tools.py:255-267.
        if last_was_right_blank and s[j] == ' ':
            not_last = (j + 1 < n)
            if not_last or next_is_inline:
                # The encoder writes NO separate tile for this space — the
                # previous tile's built-in right-half blank already renders
                # the gap, so it adds zero width. But the space IS occupied
                # in the balloon (it is that tile's right half); do NOT
                # disregard it. Emit it as a zero-cost tile so the joined
                # substrings reproduce the real rendered text and word
                # boundaries survive. Width is unchanged (cost 0), staying
                # byte-exact with encode_text_to_entry.
                yield (' ', 0)
                j += 1
                last_was_right_blank = False
                continue

        # Try bigram first (greedy, left-to-right, no lookahead).
        if j + 1 < n:
            pair = (s[j], s[j + 1])
            if pair in big:
                yield (s[j:j + 2], 1)
                last_was_right_blank = (pair[1] == ' ')
                j += 2
                continue

        # Opening punctuation hugging the next glyph: blank-LEFT (' ', c) tile —
        # one tile, NOT right-blank. Mirrors d00_tools LEFT_BLANK_STANDALONE_CHARS
        # and must precede the generic (c, space) trailing rule below.
        if trail and s[j] in LEFT_BLANK_STANDALONE_CHARS and (' ', s[j]) in big:
            yield (s[j], 1)
            last_was_right_blank = False
            j += 1
            continue

        # Rigorous trailing rule (new font only): a composable char that cannot
        # pair mid-word renders as its (c, space) half-width tile — one tile,
        # right-blank — exactly as d00_tools does under trailing_bigram=True.
        if trail and (s[j], ' ') in big:
            yield (s[j], 1)
            last_was_right_blank = True
            j += 1
            continue

        # Single-char fallback.
        if s[j] in CHAR_TILE_MAP:
            yield (s[j], 1)
            last_was_right_blank = s[j] in RIGHT_BLANK_STANDALONE_CHARS
        # else: unmapped — silently drop, do NOT update last_was_right_blank.
        j += 1
