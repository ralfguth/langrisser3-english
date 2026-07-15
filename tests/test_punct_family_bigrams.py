"""Apostrophe + hyphen completion — letters pair TIGHT with ' and -.

RED state (the user-reported gaps): when the letter before a ' or - lands at
odd greedy parity it falls to a STANDALONE half-width tile (blank right half),
so the mark renders spread out:
  - "Freya's"  -> (F,r)(e,y)[a]('s)        = "Freya 's"   (lone 'a' gap)
  - "Class-Up" -> (C,l)(a,s)[s][-](U,p)    = "Class - Up" (lone 's' + '-' gap)
  - "N-no"     -> [N][-](n,o) ...           = "N - no"     (stutters, very common)

GREEN: every (letter,') (',letter) (letter,-) (-,letter) is a single bigram
tile, so the letter pairs with the mark and there is no standalone/blank gap.
Composed from the half-width glyphs (_APOSTROPHE_GLYPH / _EXTRA_PUNCT_GLYPHS['-']),
appended past the number region (the font grows).
"""
import string
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import font_tools as ft  # noqa: E402
from d00_tools import encode_text_to_entry  # noqa: E402


def _tiles(s):
    enc = encode_text_to_entry(s, ft.CHAR_TILE_MAP, ft.BIGRAM_TILE_MAP)
    return [struct.unpack_from(">H", enc, i)[0] for i in range(0, len(enc) - 1, 2)]


def test_apostrophe_and_hyphen_pairs_used_by_scripts_are_mapped():
    """Every apostrophe/hyphen pair the FINAL scripts actually produce (2-by-2)
    has a bigram tile, so the mark always pairs tight with its letter — no
    standalone/blank gap. The data-driven font deliberately does NOT carry the
    full letter×mark cartesian (slot-conscious: the unused combinations never
    occur); coverage of the pairs that DO occur is the invariant that matters
    (the per-word cases below + test_no_bigram_fallback enforce it too)."""
    used = ft.script_bigram_pairs(str(REPO / "scripts" / "en"))
    missing = sorted(
        p for p in used
        if ("'" in p or "-" in p)
        and p[0] in ft.HALF_GLYPHS and p[1] in ft.HALF_GLYPHS
        and p not in ft.BIGRAM_TILE_MAP)
    assert not missing, f"apostrophe/hyphen pairs used by scripts but unmapped: {missing}"


def test_freya_possessive_is_tight():
    """'Freya's' must pair the 'a' with the apostrophe, not leave a lone 'a'."""
    tiles = _tiles("Freya's")
    assert ft.CHAR_TILE_MAP["a"] not in tiles, "lone 'a' (blank gap) before apostrophe"
    assert ft.BIGRAM_TILE_MAP[("a", "'")] in tiles


def test_hyphen_names_and_stutters_are_tight():
    """No standalone hyphen tile (the gap) for odd-parity hyphenations."""
    for s in ("Class-Up", "Sky-Fortress", "N-no", "Wh-what", "I-I", "Y-you"):
        tiles = _tiles(s)
        assert ft.CHAR_TILE_MAP["-"] not in tiles, f"standalone hyphen gap in {s!r}"
