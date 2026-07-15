"""Part 2 of the new-font rebuild: the half-glyph alphabet + composition.

The FRESH region is built by composing each necessary half-width bigram from two
half glyphs. This guard pins, deterministically:
  * the alphabet COVERS every half-width char our final scripts pair 2-by-2
    (no missing glyph -> no silent fallback in the rebuild), and
  * compose_bigram REPRODUCES the proven current font byte-for-byte (so the
    fresh composition is the same trusted output, just re-laid-out).
See archive/docs/20260625_new_font_from_scratch_plan.md (Part 2).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import font_tools as ft       # noqa: E402
import new_font as nf         # noqa: E402

JP_FONT = REPO / "data" / "jp" / "font_jp.bin"
TILE = nf.TILE


def test_alphabet_covers_necessary_chars():
    """Every half-width char in the necessary 2-by-2 pairs has a half glyph."""
    necessary = ft.script_bigram_pairs(str(REPO / "scripts" / "en"))
    half = ft._HALF_GLYPH_CHARS
    missing = sorted({
        c
        for pair in necessary
        for c in pair
        if c in half and c not in nf.HALF_GLYPHS
    })
    assert not missing, f"half-glyph alphabet missing composable chars: {missing}"


def test_compose_reproduces_current_font():
    """compose_bigram matches the proven generator's bytes for plain bigrams."""
    cur = ft.generate_english_font(JP_FONT.read_bytes())
    # plain lowercase pairs are interleaved (not tight-rendered) -> exact match
    samples = [("t", "h"), ("a", "n"), ("e", "r"), ("i", "n"),
               ("o", "u"), ("s", "t"), ("l", "l")]
    bad = []
    for a, b in samples:
        tile = ft.BIGRAM_TILE_MAP.get((a, b))
        if tile is None:
            continue
        expected = cur[tile * TILE:(tile + 1) * TILE]
        if nf.compose_bigram(a, b) != expected:
            bad.append((a, b, tile))
    assert not bad, f"compose_bigram diverges from the current font for: {bad}"
