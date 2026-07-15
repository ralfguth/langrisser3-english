"""Part 3 of the new-font rebuild: the data-driven FRESH bigram layout.

Pins, deterministically, that the FRESH region is allocated ONLY for necessary
bigrams (100% utilization — no wasted tile), every necessary composable pair has
a slot (coverage), the layout is collision-free and inside 46..1499, and each
allocated tile is composed to the SAME proven glyph as the current font (just
re-laid-out). See archive/docs/20260625_new_font_from_scratch_plan.md (Part 3).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import font_tools as ft       # noqa: E402
import new_font as nf         # noqa: E402

JP_FONT = REPO / "data" / "jp" / "font_jp.bin"
TILE = nf.TILE


def test_layout_is_only_necessary_bigrams():
    """No waste: every laid-out pair is a necessary composable bigram."""
    assert set(nf.BIGRAM_LAYOUT) == set(nf.necessary_bigrams())


def test_layout_covers_every_necessary_pair():
    """Coverage: every necessary composable pair has a tile (no fallback)."""
    missing = [p for p in nf.necessary_bigrams() if p not in nf.BIGRAM_LAYOUT]
    assert not missing, f"necessary pairs without a FRESH tile: {missing[:20]}"


def test_layout_in_fresh_range_and_collision_free():
    # FRESH-allocated pairs: distinct tiles, inside 46..1499, off the preserved set.
    fresh = {p: t for p, t in nf.BIGRAM_LAYOUT.items() if t not in nf.PRESERVED_TILES}
    tiles = list(fresh.values())
    assert len(tiles) == len(set(tiles)), "two pairs share a FRESH tile"
    for pair, t in fresh.items():
        assert nf.FRESH_START <= t <= nf.FRESH_END, f"{pair} -> {t} out of FRESH range"
    # Preserved-reuse pairs (e.g. (x, space)) point AT a preserved single tile.
    for pair, t in nf.BIGRAM_LAYOUT.items():
        if t in nf.PRESERVED_TILES:
            assert pair[1] == " " or pair in __import__("font_tools").BIGRAM_TILE_MAP


def test_font_within_render_buffer():
    assert nf.NEW_FONT_TILES <= 1691


def test_allocated_bigrams_are_composed_in_font():
    """Each FRESH (non-preserved) bigram tile is composed from its half glyphs.
    Preserved-reuse pairs come from the preserved source (covered separately)."""
    new = nf.generate_new_font(JP_FONT.read_bytes())
    bad = []
    for (a, b), t in nf.BIGRAM_LAYOUT.items():
        if t in nf.PRESERVED_TILES:
            continue
        if new[t * TILE:(t + 1) * TILE] != nf.compose_bigram(a, b):
            bad.append((a, b, t))
    assert not bad, f"FRESH tiles not composed correctly: {bad[:20]}"


def test_every_relocated_pair_keeps_its_glyph():
    """Glyph-preservation invariant: for EVERY pair the rebuild lays out that the
    current font also has, the new-font glyph is byte-identical to the current
    one — the rebuild RE-POSITIONS, it never alters a glyph. (This is the guard
    that catches conflating a half-width (X, space) with the wide zenkaku single,
    the 'I ' regression the user caught 2026-06-25.)"""
    cur = ft.generate_english_font(JP_FONT.read_bytes())
    new = nf.generate_new_font(JP_FONT.read_bytes())
    n_cur = len(cur) // TILE
    bad = []
    for pair, new_t in nf.BIGRAM_LAYOUT.items():
        old_t = ft.BIGRAM_TILE_MAP.get(pair)
        if old_t is None or old_t >= n_cur:
            continue
        if new[new_t * TILE:(new_t + 1) * TILE] != cur[old_t * TILE:(old_t + 1) * TILE]:
            bad.append((pair, old_t, new_t))
    assert not bad, (
        f"{len(bad)} relocated pairs changed glyph (re-positioning must preserve "
        f"the glyph):\n" + "\n".join(f"  {p}: old {o} -> new {n}" for p, o, n in bad[:15])
    )
