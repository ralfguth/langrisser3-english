"""Part 1 of the new-font rebuild: the from-scratch generator SKELETON.

`new_font.generate_new_font` must emit a valid 1691-tile font whose FIXED +
KEPT-SPECIAL tiles sit byte-identical at their positions (preserved) while the
FRESH region (the data-driven 46-1499 area) and the DROPPED parked bigrams are
blank. This pins the rebuild's starting point deterministically. See
archive/docs/20260625_new_font_from_scratch_plan.md (Part 1).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import font_tools as ft       # noqa: E402
import new_font as nf         # noqa: E402

JP_FONT = REPO / "data" / "jp" / "font_jp.bin"
TILE = nf.TILE


def _new():
    return nf.generate_new_font(JP_FONT.read_bytes())


def _src():
    return ft.generate_english_font(JP_FONT.read_bytes())


def test_size_is_within_render_buffer():
    font = _new()
    assert len(font) == nf.NEW_FONT_TILES * TILE
    assert nf.NEW_FONT_TILES <= 1691  # no garble


# Preserved tiles whose GLYPH is intentionally REDRAWN in the new font (position
# kept, art changed). The standalone bullet • uses the small EagleIII dot instead
# of the wide centered circle (user 2026-06-26).
REDRAWN_TILES = {ft.CHAR_TILE_MAP['•'], 0x2C}  # bullet + 's possessive (の) = [',s]


def test_preserved_tiles_byte_identical():
    """Every FIXED + KEPT-SPECIAL tile equals the proven source at its position,
    except the deliberately-redrawn ones (REDRAWN_TILES)."""
    new, src = _new(), _src()
    bad = []
    for t in sorted(nf.PRESERVED_TILES):
        if t >= nf.NEW_FONT_TILES or t in REDRAWN_TILES:
            continue
        if new[t * TILE:(t + 1) * TILE] != src[t * TILE:(t + 1) * TILE]:
            bad.append(t)
    assert not bad, f"preserved tiles not byte-identical at: {bad[:20]}"


def test_fixed_skeleton_matches_golden():
    """The engine-mandatory tiles match the Part-0 golden (cross-check)."""
    new = _new()
    # tile 0 blank, tiles 7-16 are the full-width digits, 44 the 's
    assert new[0:TILE] == bytes(TILE), "tile 0 must be the full-width blank"
    assert new[44 * TILE:45 * TILE] != bytes(TILE), "tile 44 ('s) must be drawn"
    for d in range(10):
        t = 7 + d
        assert new[t * TILE:(t + 1) * TILE] != bytes(TILE), f"digit tile {t} drawn"


def test_dropped_parked_bigrams_are_blank():
    """43 (Tu) and 45 (V ) are parked bigrams the rebuild drops -> blank."""
    new = _new()
    for t in sorted(nf.DROPPED_TILES):
        assert new[t * TILE:(t + 1) * TILE] == bytes(TILE), f"tile {t} must be blank (dropped)"


def test_fresh_slack_is_blank():
    """After the data-driven bigrams (Part 3), the UNALLOCATED FRESH tail is
    blank (the only acceptable blank region — filled with extras in a later
    100%-utilization slice)."""
    new = _new()
    last = max(nf.BIGRAM_LAYOUT.values())
    for t in range(last + 1, nf.FRESH_END + 1):
        if t in nf.PRESERVED_TILES:
            continue
        assert new[t * TILE:(t + 1) * TILE] == bytes(TILE), f"slack tile {t} should be blank"
