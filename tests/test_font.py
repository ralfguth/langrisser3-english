#!/usr/bin/env python3
"""
test_font.py - Tests for bigram font system.

Verifies:
1. CHAR_TILE_MAP has correct tile indices
2. BIGRAM_TILE_MAP entries are consistent
3. All generated tiles have correct pixel content
4. Patched FONT.BIN preserves size
5. No regressions in tile mapping
"""

import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from font_tools import (
    CHAR_TILE_MAP, BIGRAM_TILE_MAP, TILE_CHAR_MAP,
    _LC_STARTS, _LC_RIGHT_FULL, _LC_UI_OFFSETS,
    _UC_GROUPS, _UC_UI_OFFSETS,
    _LETTER_GLYPHS, _DIGIT_TILES, _PUNCT_GLYPHS,
    _CWX_SPECIAL_BIGRAMS, _CWX_SPACE_DIGIT_BIGRAMS, _CWX_PREEXISTING_TILES,
    generate_all_tiles, patch_font_bin,
    I_APOSTROPHE_TILE, APOSTROPHE_TILE, ELLIPSIS_TILE,
    _compose_tile, _glyph,
)

JP_TRACK01 = Path.home() / 'Jogos/emulacao/romsets/sega saturn/Langrisser III (Japan)/Langrisser III (Japan) (3M) (Track 01).bin'


def get_jp_font():
    """Extract FONT.BIN from JP ISO."""
    from iso_tools import build_file_index, extract_file_data
    image = JP_TRACK01.read_bytes()
    idx = build_file_index(image)
    entry = idx['LANG/FONT.BIN']
    return extract_file_data(image, entry.extent, entry.size)


def extract_left_half(tile_data, tile_idx):
    tile = tile_data[tile_idx * 32:(tile_idx + 1) * 32]
    return tuple(tile[r * 2] for r in range(16))


def extract_right_half(tile_data, tile_idx):
    tile = tile_data[tile_idx * 32:(tile_idx + 1) * 32]
    return tuple(tile[r * 2 + 1] for r in range(16))


class TestCharTileMap(unittest.TestCase):

    def test_space_is_tile_0(self):
        self.assertEqual(CHAR_TILE_MAP[' '], 0)

    def test_punctuation(self):
        self.assertEqual(CHAR_TILE_MAP[','], 3)
        self.assertEqual(CHAR_TILE_MAP['.'], 4)
        self.assertEqual(CHAR_TILE_MAP['?'], 5)
        self.assertEqual(CHAR_TILE_MAP['!'], 6)
        self.assertEqual(CHAR_TILE_MAP["'"], APOSTROPHE_TILE)
        self.assertEqual(CHAR_TILE_MAP['…'], ELLIPSIS_TILE)
        self.assertNotIn('-', CHAR_TILE_MAP)
        self.assertNotIn('"', CHAR_TILE_MAP)

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

    def test_bigram_count(self):
        lc_count = sum(1 for k in BIGRAM_TILE_MAP if k[0].islower())
        uc_count = sum(1 for k in BIGRAM_TILE_MAP if k[0].isupper())
        space_count = sum(1 for k in BIGRAM_TILE_MAP if k[0] == ' ')
        apos_count = sum(1 for k in BIGRAM_TILE_MAP if k[0] == "'")
        self.assertEqual(lc_count, 801)
        self.assertEqual(uc_count, 519)        # UC groups only (no custom UC+space)
        self.assertEqual(space_count, 10)      # CWX space+digit bigrams only
        self.assertEqual(apos_count, 3)        # 's, 'v, 't from CWX

    def test_ui_tiles_not_in_bigram_map(self):
        mapped = set(BIGRAM_TILE_MAP.values())
        for ch, ui_set in _LC_UI_OFFSETS.items():
            for offset in ui_set:
                tile_idx = _LC_STARTS[ch] + offset
                self.assertNotIn(tile_idx, mapped,
                                 f"UI tile {tile_idx} ({ch}+{offset}) in bigram map")
        for ch, ui_set in _UC_UI_OFFSETS.items():
            for offset in ui_set:
                tile_idx = _UC_GROUPS[ch][0] + offset
                self.assertNotIn(tile_idx, mapped,
                                 f"UI tile {tile_idx} ({ch}+{offset}) in bigram map")

    def test_specific_known_bigrams(self):
        known = [('t','h'), ('e',' '), ('i','n'), ('m','y'), ('p','e'), ('y',',')]
        for left, right in known:
            self.assertIn((left, right), BIGRAM_TILE_MAP,
                          f"Bigram ('{left}','{right}') missing")

    def test_custom_bigrams_exist(self):
        self.assertIn(('I', "'"), BIGRAM_TILE_MAP)
        self.assertEqual(BIGRAM_TILE_MAP[('I', "'")], I_APOSTROPHE_TILE)

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


class TestTileGeneration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tiles = generate_all_tiles()

    def test_all_generated_tiles_are_32_bytes(self):
        for idx, data in self.tiles.items():
            self.assertEqual(len(data), 32,
                             f"Tile {idx} is {len(data)} bytes, expected 32")

    def test_generates_all_bigram_tiles_except_cwx(self):
        for pair, idx in BIGRAM_TILE_MAP.items():
            if idx in _CWX_PREEXISTING_TILES:
                self.assertNotIn(idx, self.tiles,
                                 f"CWX tile {idx} ({pair}) should NOT be generated")
            else:
                self.assertIn(idx, self.tiles,
                              f"Bigram {pair} tile {idx} not generated")

    def test_generates_standalone_tiles(self):
        for idx in [0, 3, 4, 5, 6]:  # space, comma, period, ?, !
            self.assertIn(idx, self.tiles)
        for i in range(10):  # digits
            self.assertIn(7 + i, self.tiles)
        for i in range(26):  # A-Z standalone
            self.assertIn(17 + i, self.tiles)

    def test_bigram_tiles_match_glyph_composition(self):
        """Every generated bigram tile should equal compose(left_glyph, right_glyph)."""
        for (left, right), idx in BIGRAM_TILE_MAP.items():
            if idx in _CWX_PREEXISTING_TILES:
                continue  # CWX tiles not generated, already correct in font
            if idx not in self.tiles:
                continue  # custom tiles tested separately
            expected = _compose_tile(_glyph(left), _glyph(right))
            actual = self.tiles[idx]
            self.assertEqual(actual, expected,
                             f"Bigram ('{left}','{right}') tile {idx} doesn't match composition")

    def test_space_tile_is_blank(self):
        self.assertEqual(self.tiles[0], b'\x00' * 32)

    def test_ellipsis_has_three_dots(self):
        ell = self.tiles[ELLIPSIS_TILE]
        # Row 12 and 13 should have pixels, others blank
        for row in range(16):
            word = (ell[row*2] << 8) | ell[row*2+1]
            if row in (12, 13):
                self.assertGreater(word, 0, f"Ellipsis row {row} is blank")
            else:
                self.assertEqual(word, 0, f"Ellipsis row {row} should be blank")

    def test_custom_apostrophe_tile(self):
        """Tile 43: standalone apostrophe (left=apostrophe, right=blank)."""
        from font_tools import _APOSTROPHE_GLYPH, _BLANK_GLYPH
        expected = _compose_tile(_APOSTROPHE_GLYPH, _BLANK_GLYPH)
        self.assertIn(APOSTROPHE_TILE, self.tiles)
        self.assertEqual(self.tiles[APOSTROPHE_TILE], expected)
        # Left half should have pixels (apostrophe), right half blank
        tile = self.tiles[APOSTROPHE_TILE]
        left_pixels = sum(bin(tile[r*2]).count('1') for r in range(16))
        right_pixels = sum(bin(tile[r*2+1]).count('1') for r in range(16))
        self.assertGreater(left_pixels, 0, "Apostrophe left half is blank")
        self.assertEqual(right_pixels, 0, "Apostrophe right half should be blank")

    def test_custom_i_apostrophe_tile(self):
        """Tile 44: I' bigram (left=I, right=apostrophe)."""
        from font_tools import _LETTER_GLYPHS, _APOSTROPHE_GLYPH
        expected = _compose_tile(_LETTER_GLYPHS['I'], _APOSTROPHE_GLYPH)
        self.assertIn(I_APOSTROPHE_TILE, self.tiles)
        self.assertEqual(self.tiles[I_APOSTROPHE_TILE], expected)
        # Both halves should have pixels
        tile = self.tiles[I_APOSTROPHE_TILE]
        left_pixels = sum(bin(tile[r*2]).count('1') for r in range(16))
        right_pixels = sum(bin(tile[r*2+1]).count('1') for r in range(16))
        self.assertGreater(left_pixels, 5, "I' left half (I) looks blank")
        self.assertGreater(right_pixels, 0, "I' right half (') looks blank")

    def test_colon_tile(self):
        """Tile 1: colon (left=colon glyph, right=blank)."""
        from font_tools import _COLON_GLYPH, _BLANK_GLYPH
        expected = _compose_tile(_COLON_GLYPH, _BLANK_GLYPH)
        self.assertIn(1, self.tiles)
        self.assertEqual(self.tiles[1], expected)

    def test_comma_tile(self):
        """Tile 3: comma (left=comma glyph, right=blank)."""
        from font_tools import _COMMA_GLYPH, _BLANK_GLYPH
        expected = _compose_tile(_COMMA_GLYPH, _BLANK_GLYPH)
        self.assertEqual(self.tiles[3], expected)

    def test_period_tile(self):
        """Tile 4: period (left=period glyph, right=blank)."""
        from font_tools import _PERIOD_GLYPH, _BLANK_GLYPH
        expected = _compose_tile(_PERIOD_GLYPH, _BLANK_GLYPH)
        self.assertEqual(self.tiles[4], expected)

    def test_digit_tiles_are_full_width(self):
        """Tiles 7-16: digits use full 32-byte tiles from _DIGIT_TILES."""
        from font_tools import _DIGIT_TILES
        for d in '0123456789':
            idx = 7 + int(d)
            self.assertEqual(self.tiles[idx], _DIGIT_TILES[d],
                             f"Digit '{d}' tile doesn't match _DIGIT_TILES")

    def test_uppercase_standalone_tiles(self):
        """Tiles 17-42: uppercase A-Z use full-width proportional tiles."""
        from font_tools import _UC_STANDALONE_TILES
        for i, ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            idx = 17 + i
            self.assertEqual(self.tiles[idx], _UC_STANDALONE_TILES[ch],
                             f"Uppercase '{ch}' at tile {idx} doesn't match")

    def test_cwx_tiles_not_overwritten(self):
        """CWX pre-existing tiles (1500-1586) must NOT be in generated tiles."""
        for tile_idx in _CWX_PREEXISTING_TILES:
            self.assertNotIn(tile_idx, self.tiles,
                             f"CWX tile {tile_idx} should not be generated")

    def test_no_tiles_in_cwx_special_range(self):
        """No generated tiles should fall in the CWX special range 1500-1620."""
        for idx in self.tiles:
            self.assertFalse(1500 <= idx <= 1620,
                             f"Tile {idx} is in CWX special range 1500-1620")

    def test_max_tile_index_within_font(self):
        max_idx = max(self.tiles.keys())
        self.assertLess(max_idx, 1691)


class TestFontPatching(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not JP_TRACK01.exists():
            raise unittest.SkipTest("JP ISO not found")
        cls.jp_font = get_jp_font()
        cls.tiles = generate_all_tiles()
        cls.patched = patch_font_bin(cls.jp_font, cls.tiles)

    def test_patched_size_matches_original(self):
        self.assertEqual(len(self.patched), len(self.jp_font))
        self.assertEqual(len(self.patched), 54112)

    def test_patched_tiles_are_applied(self):
        for idx, expected in self.tiles.items():
            actual = self.patched[idx*32:(idx+1)*32]
            self.assertEqual(actual, expected,
                             f"Tile {idx} not correctly patched")

    def test_uppercase_tiles_have_pixels(self):
        for ch in 'ABCMXYZ':
            idx = CHAR_TILE_MAP[ch]
            tile = self.patched[idx*32:(idx+1)*32]
            pixels = sum(bin(b).count('1') for b in tile)
            self.assertGreater(pixels, 10, f"'{ch}' tile looks blank")

    def test_lowercase_bigram_left_half_has_pixels(self):
        for ch in 'abcmxyz':
            idx = CHAR_TILE_MAP[ch]
            tile = self.patched[idx*32:(idx+1)*32]
            left_pixels = sum(bin(tile[r*2]).count('1') for r in range(16))
            self.assertGreater(left_pixels, 5, f"'{ch}' left half looks blank")


if __name__ == '__main__':
    unittest.main(verbosity=2)
