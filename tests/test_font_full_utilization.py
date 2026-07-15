"""North-star guard for the data-driven font re-allocation (100% utilization).

The user's directive (2026-06-25): place the NECESSARY bigrams with 100% tile
utilization — no wasted tiles, no unused space — and stay within the render
buffer (<=1691 tiles, the in-game glyph-buffer cap that garbles above it). The
engine-fixed tiles stay fixed (only their glyph art is standardized); the
re-allocation only packs the MOVABLE dialogue-grid bigrams.

These tests pin the END state and are RED until the re-allocation is done:
  * test_within_render_buffer  — ENGLISH_FONT_TILES <= 1691 (no garble)
  * test_no_wasted_bigram_tiles — every MOVABLE bigram tile is necessary
    (its (a,b) pair is produced 2-by-2 by some final script). Engine-fixed /
    reserved tiles are exempt (they hold required engine glyphs, not waste).

Necessity oracle = font_tools.script_bigram_pairs over scripts/en (the same
2-chars-at-a-time walk the encoder uses; covers D00 + PLOT + FNT_SYS).
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import font_tools as ft  # noqa: E402

SCRIPTS = REPO / "scripts" / "en"

RENDER_BUFFER_TILES = 1691  # the in-game glyph staging buffer cap (see handoff)

# Engine-fixed / reserved tile indices — NOT re-allocatable, exempt from the
# no-waste check (they hold required engine glyphs by index, see the engine-fixed
# map in archive/docs/20260625_font_refactor_handoff.md).
RESERVED_TILES = (
    set(range(0, 46))            # low band: blank, punct, digits 7-16, UC 17-42, 's@44
    | set(range(201, 212))       # digit+space pairs (fntsys-indexed)
    | {330, 331, 332, 333, 334}  # formation glyphs 0x014A-E
    | {369, 373}                 # full-width parens (scen107)
    | {489}                      # star *
    | {906}                      # ellipsis
    | set(range(1488, 1491))     # ADV/BAK/END keyboard buttons
    | set(range(1500, 1691))     # 0.2-patch menu/UI band + keyboard zenkaku lc + dead-kanji tail
)


def _necessary_pairs():
    """Necessity oracle = the (a,b) pairs the scripts produce 2-chars-at-a-time
    (the user's spec: pair strictly 2-by-2, not greedy). With COMPLETE coverage
    greedy emission converges to this set, so it is also the target the runtime
    encoder must match. Covers D00 + PLOT + FNT_SYS text. fntsys-encoder
    specials (digit→(d,' ') tiles, fragment reuse) live in RESERVED ranges."""
    return ft.script_bigram_pairs(str(SCRIPTS))


def test_within_render_buffer():
    """GREEN since the Part 6 swap (2026-06-26): the data-driven layout packs the
    necessary bigrams in-place <=1691 instead of appending past the render buffer
    (the old layout reached 2167 tiles, which garbles in-game)."""
    assert ft.ENGLISH_FONT_TILES <= RENDER_BUFFER_TILES, (
        f"font is {ft.ENGLISH_FONT_TILES} tiles (> {RENDER_BUFFER_TILES}); "
        f"tiles above the render buffer garble in-game. Pack the data-driven "
        f"bigrams in-place into reclaimed dead slots instead of appending."
    )


def test_no_wasted_bigram_tiles():
    """GREEN since the Part 6 swap: the layout is data-driven (only necessary
    bigrams). The old combinatorial LC/UC groups + cartesian punct family + full
    00-99 left hundreds of movable bigram tiles unused; now every movable bigram
    tile is necessary (its pair occurs 2-by-2 in the final scripts)."""
    necessary = _necessary_pairs()
    wasted = sorted(
        (tile, pair)
        for pair, tile in ft.BIGRAM_TILE_MAP.items()
        if tile not in RESERVED_TILES
        and pair[1] != " "          # trailing-space pairs render as standalone
        and pair not in necessary
    )
    if wasted:
        sample = ", ".join(f"{a!r}+{b!r}@{t}" for t, (a, b) in wasted[:12])
        raise AssertionError(
            f"{len(wasted)} movable bigram tiles are wasted (mapped but no surface "
            f"emits them) — the re-alloc must be data-driven (necessary only).\n"
            f"sample: {sample}"
        )
