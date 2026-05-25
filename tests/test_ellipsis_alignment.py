"""Assert the '…' ellipsis tile sits at the same vertical position as
the '.' period glyph — both should occupy rows 11-12 of their tile.

Bug: ellipsis was painted at rows 12-13, one row LOWER than period,
so '...' written via the ellipsis tile rendered below the text
baseline next to a regular period.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "tools"))

import pytest
from font_tools import _ELLIPSIS_TILE_DATA, _PUNCT_GLYPHS


def _nonblank_rows(tile_bytes: bytes, row_byte_count: int) -> list[int]:
    """Return row indices that have any pixel set."""
    rows = []
    n_rows = len(tile_bytes) // row_byte_count
    for r in range(n_rows):
        row_bytes = tile_bytes[r * row_byte_count : (r + 1) * row_byte_count]
        if any(b != 0 for b in row_bytes):
            rows.append(r)
    return rows


def test_ellipsis_row_alignment_matches_period():
    period_rows = _nonblank_rows(_PUNCT_GLYPHS['.'], row_byte_count=1)   # 8x16 = 1 byte/row
    ellipsis_rows = _nonblank_rows(_ELLIPSIS_TILE_DATA, row_byte_count=2)  # 16x16 = 2 bytes/row
    assert period_rows, "period glyph should have non-blank rows"
    assert ellipsis_rows, "ellipsis glyph should have non-blank rows"
    assert ellipsis_rows == period_rows, (
        f"ellipsis non-blank rows {ellipsis_rows} must match period "
        f"non-blank rows {period_rows} so '…' and '.' align on the same "
        f"text baseline."
    )
