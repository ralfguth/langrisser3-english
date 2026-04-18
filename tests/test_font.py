#!/usr/bin/env python3
"""
test_font.py - Tests for bigram font system (VD font alignment).

Verifies:
1. CHAR_TILE_MAP has correct tile indices
2. BIGRAM_TILE_MAP entries are consistent and aligned with VD font
3. Glyph reference data is well-formed
4. VD font file has correct size and key tiles have pixels
5. Tile maps only reference tiles that exist in VD's font
"""

import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from font_tools import (
    CHAR_TILE_MAP, BIGRAM_TILE_MAP, TILE_CHAR_MAP,
    _LC_STARTS, _LC_RIGHT_FULL, _LC_UI_OFFSETS, _LC_MISSING_CHARS,
    _UC_GROUPS, _UC_UI_OFFSETS,
    _LETTER_GLYPHS, _DIGIT_TILES, _PUNCT_GLYPHS,
    _CWX_SPECIAL_BIGRAMS, _CWX_SPACE_DIGIT_BIGRAMS,
    _VD_APOSTROPHE_BIGRAMS, _VD_SPACE_LETTER_BIGRAMS, _VD_PUNCT_BIGRAMS,
    ELLIPSIS_TILE, DQUOTE_TILE,
)

VD_FONT_PATH = PROJECT_DIR / 'patches' / 'vd_font.bin'


class TestCharTileMap(unittest.TestCase):

    def test_space_is_tile_0(self):
        self.assertEqual(CHAR_TILE_MAP[' '], 0)

    def test_punctuation(self):
        self.assertEqual(CHAR_TILE_MAP[','], 3)
        self.assertEqual(CHAR_TILE_MAP['.'], 4)
        self.assertEqual(CHAR_TILE_MAP['?'], 5)
        self.assertEqual(CHAR_TILE_MAP['!'], 6)
        self.assertNotIn("'", CHAR_TILE_MAP)  # apostrophe is bigram-only in VD
        self.assertEqual(CHAR_TILE_MAP['…'], ELLIPSIS_TILE)
        self.assertEqual(CHAR_TILE_MAP['"'], DQUOTE_TILE)

    def test_no_custom_tiles_that_conflict_with_vd(self):
        """Characters that VD's font doesn't have should not be in CHAR_TILE_MAP."""
        for ch in ['-', '~', '*', '⅓', '+', '[', ']', '(', ')', '%', 'ñ']:
            self.assertNotIn(ch, CHAR_TILE_MAP,
                             f"'{ch}' should not be in CHAR_TILE_MAP (no VD font tile)")

    def test_dquote_at_tile_1470(self):
        """VD's double-quote is at tile 1470, not 1439."""
        self.assertEqual(DQUOTE_TILE, 1470)
        self.assertEqual(CHAR_TILE_MAP['"'], 1470)

    def test_digits_are_tiles_7_to_16(self):
        for i in range(10):
            self.assertEqual(CHAR_TILE_MAP[str(i)], 7 + i)

    def test_uppercase_are_tiles_17_to_42(self):
        for i in range(26):
            self.assertEqual(CHAR_TILE_MAP[chr(65 + i)], 17 + i)

    def test_lowercase_map_to_bigram_group_starts(self):
        for ch, start in _LC_STARTS.items():
            self.assertEqual(CHAR_TILE_MAP[ch], start)

    def test_all_tiles_within_font_range(self):
        max_tile = 54112 // 32  # 1691
        for ch, idx in CHAR_TILE_MAP.items():
            self.assertLess(idx, max_tile, f"'{ch}' tile {idx} out of range")


class TestBigramTileMap(unittest.TestCase):

    def test_ui_tiles_not_in_bigram_map(self):
        mapped = set(BIGRAM_TILE_MAP.values())
        for ch, ui_set in _LC_UI_OFFSETS.items():
            for offset in ui_set:
                tile_idx = _LC_STARTS[ch] + offset
                self.assertNotIn(tile_idx, mapped,
                                 f"UI tile {tile_idx} ({ch}+{offset}) in bigram map")

    def test_specific_known_bigrams(self):
        known = [('t','h'), ('e',' '), ('i','n'), ('m','y'), ('p','e'), ('y',',')]
        for left, right in known:
            self.assertIn((left, right), BIGRAM_TILE_MAP,
                          f"Bigram ('{left}','{right}') missing")

    def test_lc_period_at_position_27(self):
        """VD has period at LC position 27, not apostrophe."""
        self.assertEqual(_LC_RIGHT_FULL[27], '.')
        # Verify 'a.' bigram exists (a-group, position 27)
        self.assertIn(('a', '.'), BIGRAM_TILE_MAP)
        # Apostrophe should NOT be in LC right chars
        self.assertNotIn("'", _LC_RIGHT_FULL)

    def test_lc_groups_fully_mapped(self):
        """Each LC group should have all available right chars mapped."""
        for left in _LC_STARTS:
            missing = _LC_MISSING_CHARS.get(left, set())
            expected_rights = [c for c in _LC_RIGHT_FULL if c not in missing]
            actual = len([1 for (l, r) in BIGRAM_TILE_MAP
                         if l == left and r in expected_rights])
            self.assertEqual(actual, len(expected_rights),
                             f"LC group '{left}': expected {len(expected_rights)} right chars, got {actual}")

    def test_vd_apostrophe_bigrams_exist(self):
        """VD's 10 apostrophe bigrams should all be in the map."""
        for pair, tile_idx in _VD_APOSTROPHE_BIGRAMS.items():
            self.assertIn(pair, BIGRAM_TILE_MAP, f"VD apostrophe bigram {pair} missing")
            self.assertEqual(BIGRAM_TILE_MAP[pair], tile_idx)
        # 'v at 1500
        self.assertIn(("'", 'v'), BIGRAM_TILE_MAP)
        self.assertEqual(BIGRAM_TILE_MAP[("'", 'v')], 1500)

    def test_vd_space_letter_bigrams_exist(self):
        """VD's space+letter bigrams should all be in the map."""
        for pair, tile_idx in _VD_SPACE_LETTER_BIGRAMS.items():
            self.assertIn(pair, BIGRAM_TILE_MAP, f"VD space+letter {pair} missing")
            self.assertEqual(BIGRAM_TILE_MAP[pair], tile_idx)

    def test_vd_punct_bigrams_exist(self):
        """VD's punctuation double-bigrams should be in the map."""
        for pair, tile_idx in _VD_PUNCT_BIGRAMS.items():
            self.assertIn(pair, BIGRAM_TILE_MAP, f"VD punct bigram {pair} missing")
            self.assertEqual(BIGRAM_TILE_MAP[pair], tile_idx)

    def test_no_conflicting_custom_bigrams(self):
        """Custom bigrams that conflict with VD tiles should not exist."""
        # Tiles 43-45 should not be mapped (VD has a/m/p there)
        mapped_tiles = set(BIGRAM_TILE_MAP.values())
        for tile in [43, 44, 45]:
            self.assertNotIn(tile, mapped_tiles,
                             f"Tile {tile} should not be in bigram map (VD uses it for a/m/p)")
        # No hyphen, colon, semicolon, enye bigrams
        for pair in BIGRAM_TILE_MAP:
            self.assertNotIn('-', pair, f"Hyphen bigram {pair} found (VD has no hyphen tiles)")
            self.assertNotIn('ñ', pair, f"Enye bigram {pair} found (VD has no enye tiles)")

    def test_cwx_special_bigrams_exist(self):
        for pair, tile_idx in _CWX_SPECIAL_BIGRAMS.items():
            self.assertIn(pair, BIGRAM_TILE_MAP, f"CWX bigram {pair} missing")
            self.assertEqual(BIGRAM_TILE_MAP[pair], tile_idx)

    def test_cwx_space_digit_bigrams_exist(self):
        for pair, tile_idx in _CWX_SPACE_DIGIT_BIGRAMS.items():
            self.assertIn(pair, BIGRAM_TILE_MAP, f"CWX space+digit {pair} missing")
            self.assertEqual(BIGRAM_TILE_MAP[pair], tile_idx)

    def test_all_tiles_within_font_range(self):
        max_tile = 1691
        for pair, idx in BIGRAM_TILE_MAP.items():
            self.assertLess(idx, max_tile,
                            f"Bigram {pair} tile {idx} out of range")


class TestGlyphData(unittest.TestCase):
    """Reference glyph data integrity checks."""

    def test_all_letter_glyphs_are_16_bytes(self):
        for ch, data in _LETTER_GLYPHS.items():
            self.assertEqual(len(data), 16, f"Glyph '{ch}' is {len(data)} bytes")

    def test_all_digit_tiles_are_32_bytes(self):
        for d, data in _DIGIT_TILES.items():
            self.assertEqual(len(data), 32, f"Digit '{d}' is {len(data)} bytes")

    def test_all_punct_glyphs_are_16_bytes(self):
        for ch, data in _PUNCT_GLYPHS.items():
            self.assertEqual(len(data), 16, f"Punct '{ch}' is {len(data)} bytes")

    def test_letter_glyphs_have_pixels(self):
        for ch, data in _LETTER_GLYPHS.items():
            pixels = sum(bin(b).count('1') for b in data)
            self.assertGreater(pixels, 5, f"Glyph '{ch}' looks blank ({pixels} pixels)")

    def test_digit_tiles_have_pixels(self):
        for d, data in _DIGIT_TILES.items():
            pixels = sum(bin(b).count('1') for b in data)
            self.assertGreater(pixels, 5, f"Digit '{d}' looks blank")

    def test_all_52_letters_present(self):
        for ch in 'abcdefghijklmnopqrstuvwxyz':
            self.assertIn(ch, _LETTER_GLYPHS)
        for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            self.assertIn(ch, _LETTER_GLYPHS)

    def test_all_10_digits_present(self):
        for d in '0123456789':
            self.assertIn(d, _DIGIT_TILES)


class TestVDFont(unittest.TestCase):
    """Tests for VermillionDesserts' English font file."""

    @classmethod
    def setUpClass(cls):
        if not VD_FONT_PATH.exists():
            raise unittest.SkipTest("VD font not found")
        cls.font_data = VD_FONT_PATH.read_bytes()

    def _tile_pixels(self, idx):
        tile = self.font_data[idx*32:(idx+1)*32]
        return sum(bin(b).count('1') for b in tile)

    def test_font_size(self):
        self.assertEqual(len(self.font_data), 54112)

    def test_font_tile_count(self):
        self.assertEqual(len(self.font_data) // 32, 1691)

    def test_uppercase_tiles_have_pixels(self):
        """Tiles 17-42 (A-Z) should have visible glyph data."""
        for i, ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            idx = 17 + i
            self.assertGreater(self._tile_pixels(idx), 10,
                               f"'{ch}' tile {idx} looks blank")

    def test_key_bigram_tiles_have_pixels(self):
        """Common bigram tiles should have visible glyph data."""
        key_bigrams = [('t','h'), ('h','e'), ('i','n'), ('e','r')]
        for left, right in key_bigrams:
            idx = BIGRAM_TILE_MAP[(left, right)]
            self.assertGreater(self._tile_pixels(idx), 10,
                               f"Bigram '{left}{right}' tile {idx} looks blank")

    def test_space_tile_is_blank(self):
        tile = self.font_data[0:32]
        self.assertEqual(tile, b'\x00' * 32)

    def test_digit_tiles_have_pixels(self):
        for d in range(10):
            idx = 7 + d
            self.assertGreater(self._tile_pixels(idx), 5,
                               f"Digit {d} tile {idx} looks blank")

    def test_vd_apostrophe_tiles_have_pixels(self):
        """VD's apostrophe bigram tiles should have visible glyph data."""
        for pair, idx in _VD_APOSTROPHE_BIGRAMS.items():
            self.assertGreater(self._tile_pixels(idx), 5,
                               f"Apostrophe bigram {pair} tile {idx} looks blank")

    def test_vd_space_letter_sample_tiles_have_pixels(self):
        """Sample VD space+letter tiles should have visible glyph data."""
        samples = [(' ','a'), (' ','e'), (' ','t'), (' ','A'), (' ','T')]
        for pair in samples:
            idx = BIGRAM_TILE_MAP[pair]
            self.assertGreater(self._tile_pixels(idx), 3,
                               f"Space+letter {pair} tile {idx} looks blank")

    def test_ellipsis_tile_has_pixels(self):
        self.assertGreater(self._tile_pixels(ELLIPSIS_TILE), 2,
                           "Ellipsis tile looks blank")

    def test_dquote_tile_has_pixels(self):
        self.assertGreater(self._tile_pixels(DQUOTE_TILE), 2,
                           "Double-quote tile looks blank")

    def test_bigram_map_tiles_match_vd_font(self):
        """Every tile in BIGRAM_TILE_MAP should have pixels in VD's font.

        This catches misalignments where font_tools maps a bigram to a tile
        index that has a blank or wrong glyph in VD's font.
        """
        blank_tiles = []
        for pair, idx in BIGRAM_TILE_MAP.items():
            left, right = pair
            # Space bigrams (X + ' ') have left-half content only
            if right == ' ' and left != ' ':
                continue
            if self._tile_pixels(idx) == 0:
                blank_tiles.append((pair, idx))
        if blank_tiles:
            examples = blank_tiles[:10]
            msg = (f"{len(blank_tiles)} bigram tiles are blank in VD font:\n"
                   + '\n'.join(f"  {p} -> tile {i}" for p, i in examples))
            self.fail(msg)


if __name__ == '__main__':
    unittest.main(verbosity=2)
