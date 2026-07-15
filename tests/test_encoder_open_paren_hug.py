#!/usr/bin/env python3
"""test_encoder_open_paren_hug.py — a standalone opening '(' must HUG the glyph
that follows it.

RED state (before the LEFT_BLANK_STANDALONE_CHARS rule): a '(' that cannot pair
with its right neighbour (no ('(',X) bigram, e.g. '(' before the full-width
formation square 囗) fell to the generic trailing tile ('(',' ') = 152 — '(' on
the LEFT half, blank RIGHT — leaving a visible gap before the next glyph
(scen001's "(囗)" formation tutorial).

GREEN: such a '(' uses the blank-LEFT tile (' ','(') = 49 instead — '(' on the
RIGHT half of its cell, adjacent to the following glyph. The tile already exists
in the font, so this is encoder-only. A '(' that DOES have a content bigram
(e.g. ('(','A')) is unaffected, and a '(' already preceded by a space keeps
rendering via that same tile 49.

The width is unchanged (one tile either way); text_measure.iter_tiles mirrors
the rule so layout-QA stays byte-exact with the encoder.
"""

import struct
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

import font_tools as ft                                   # noqa: E402
from d00_tools import encode_text_to_entry                # noqa: E402
from text_measure import iter_tiles                       # noqa: E402

C = ft.CHAR_TILE_MAP
B = ft.BIGRAM_TILE_MAP
LEFT_BLANK_PAREN = B[(' ', '(')]    # 49 — blank left, '(' right (hugs next)
RIGHT_BLANK_PAREN = B[('(', ' ')]   # 152 — '(' left, blank right (gap after)


def tiles(s):
    raw = encode_text_to_entry(s, C, B, trailing_bigram=True)
    return [struct.unpack('>H', raw[i:i + 2])[0] for i in range(0, len(raw), 2)]


class TestOpenParenHug(unittest.TestCase):
    def test_paren_before_fullwidth_square_hugs_right(self):
        """'(' before 囗 (no ('(',囗) bigram) -> blank-LEFT tile 49, then 囗."""
        self.assertNotIn(('(', '囗'), B)            # the missing pair that triggered this
        t = tiles('(囗')
        self.assertEqual(t[0], LEFT_BLANK_PAREN, "'(' should hug right (tile 49)")
        self.assertNotEqual(t[0], RIGHT_BLANK_PAREN, "'(' must not use the gap tile 152")
        self.assertEqual(t[1], C['囗'])             # 330, JP square glyph

    def test_paren_before_nonbigram_letter_hugs(self):
        """'(' + a letter with NO ('(',X) bigram (e.g. 'C') also hugs."""
        self.assertNotIn(('(', 'C'), B)
        self.assertEqual(tiles('(C')[0], LEFT_BLANK_PAREN)

    def test_paren_with_letter_bigram_is_unaffected(self):
        """'(' + 'A' HAS a ('(','A') content bigram -> keep it, do NOT hug."""
        self.assertIn(('(', 'A'), B)
        self.assertEqual(tiles('(A')[0], B[('(', 'A')])

    def test_space_before_paren_still_left_blank(self):
        """A '(' already preceded by a space keeps using tile 49 (unchanged)."""
        self.assertEqual(tiles(' (C')[0], LEFT_BLANK_PAREN)

    def test_after_control_code_hugs(self):
        """The real case: '(' right after a structural code (<$FFFD>) hugs 囗."""
        raw = encode_text_to_entry('<$FFFD>(囗', C, B, trailing_bigram=True)
        # ctrl FFFD (2 bytes) then the '(' tile
        first_tile = struct.unpack('>H', raw[2:4])[0]
        self.assertEqual(first_tile, LEFT_BLANK_PAREN)

    def test_text_measure_mirrors_encoder_width(self):
        """iter_tiles must stay in sync: same tile count as the encoder for '(囗'."""
        measured = [t for t in iter_tiles('(囗', next_is_inline=False,
                                          bigram_map=B, trailing=True)]
        self.assertEqual(len(measured), len(tiles('(囗')))


if __name__ == '__main__':
    unittest.main()
