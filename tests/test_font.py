#!/usr/bin/env python3
"""
test_font.py - Tests for the bigram font system.

Verifies:
1. CHAR_TILE_MAP has correct tile indices
2. BIGRAM_TILE_MAP entries are consistent
3. Glyph reference data is well-formed
4. The GENERATED English FONT.BIN (generate_english_font over the JP
   source from LANG3_JP_DIR) has correct size and key tiles have pixels
"""

import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from font_tools import (
    CHAR_TILE_MAP, BIGRAM_TILE_MAP, TILE_CHAR_MAP, ENGLISH_FONT_TILES,
    _LC_STARTS, _LC_RIGHT_FULL, _LC_UI_OFFSETS, _LC_MISSING_CHARS,
    _UC_GROUPS, _UC_UI_OFFSETS,
    _LETTER_GLYPHS, _DIGIT_TILES, _PUNCT_GLYPHS,
    _SPECIAL_BIGRAMS,
    _APOSTROPHE_BIGRAMS, _SPACE_LETTER_BIGRAMS, _PUNCT_BIGRAMS,
    ELLIPSIS_TILE, DQUOTE_TILE,
)

class TestCharTileMap(unittest.TestCase):

    def test_space_is_tile_0(self):
        self.assertEqual(CHAR_TILE_MAP[' '], 0)

    def test_punctuation(self):
        self.assertEqual(CHAR_TILE_MAP[','], 3)
        self.assertEqual(CHAR_TILE_MAP['.'], 4)
        self.assertEqual(CHAR_TILE_MAP['?'], 5)
        self.assertEqual(CHAR_TILE_MAP['!'], 6)
        self.assertEqual(CHAR_TILE_MAP['…'], ELLIPSIS_TILE)
        self.assertEqual(CHAR_TILE_MAP['"'], DQUOTE_TILE)

    def test_extended_punctuation_in_kanji_area(self):
        """Extended punctuation (-, +, (, ), /, %, [, ], ', &) installed in
        the kanji area (tiles 1627-1638) after coverage audit found these chars
        appeared in scripts but lacked tiles."""
        expected = {
            '-': 1627, '+': 1628, '(': 1629, ')': 1631,
            '/': 1632, '%': 1634, '[': 1635,
            ']': 1636, "'": 1637, '&': 1638,
        }
        for ch, tile in expected.items():
            self.assertEqual(CHAR_TILE_MAP[ch], tile,
                             f"Extended punct {ch!r} should be at tile {tile}")

    def test_asterisk_maps_to_jp_star(self):
        """'*' renders as the JP full-width star ＊ (tile 489 in FONT.BIN, the
        objectives-header star), not the hand-drawn asterisk. Tile 489 is
        preserved verbatim from the JP font (it sits on an 'm'-group UI offset
        the bigram generator skips), so no glyph is drawn over the star."""
        self.assertEqual(CHAR_TILE_MAP['*'], 489)

    def test_zenkaku_aliases_reuse_halfwidth_tiles(self):
        """Full-width (zenkaku) chars used by the SCENARIO title line map to
        the same tiles as their half-width counterparts (for now)."""
        self.assertEqual(CHAR_TILE_MAP['　'], 0)            # U+3000 ideographic space
        self.assertEqual(CHAR_TILE_MAP['？'], 5)            # U+FF1F
        for d in range(10):                                 # ０-９ → 7-16
            self.assertEqual(CHAR_TILE_MAP[chr(0xFF10 + d)], 7 + d)
        for i in range(26):                                 # Ａ-Ｚ → 17-42
            self.assertEqual(CHAR_TILE_MAP[chr(0xFF21 + i)], 17 + i)
        self.assertEqual(CHAR_TILE_MAP['‐'], 372)           # U+2010 JP hyphen

    def test_zenkaku_scenario_header_matches_jp_tiles(self):
        """'　　　ＳＣＥＮＡＲＩＯ‐０１' encodes to the exact JP tile sequence:
        3 blank tiles + SCENARIO + JP hyphen (372) + '01'."""
        from d00_tools import encode_text_to_entry
        import struct
        raw = encode_text_to_entry('　　　ＳＣＥＮＡＲＩＯ‐０１',
                                   CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        tiles = [struct.unpack('>H', raw[i:i+2])[0] for i in range(0, len(raw), 2)]
        self.assertEqual(tiles, [0, 0, 0, 35, 19, 21, 30, 17, 34, 25, 31, 372, 7, 8])

    def test_chars_absent_from_map(self):
        """Characters not supported by the font should still be absent."""
        for ch in ['~', '⅓', 'ñ', '@', '#', '^', '`']:
            self.assertNotIn(ch, CHAR_TILE_MAP,
                             f"'{ch}' should not be in CHAR_TILE_MAP")

    def test_dquote_at_tile_1470(self):
        """0.2 patch's double-quote is at tile 1470, not 1439."""
        self.assertEqual(DQUOTE_TILE, 1470)
        self.assertEqual(CHAR_TILE_MAP['"'], 1470)

    def test_digit_fallback_rule(self):
        """Centered digit tiles 7-16 are explicit-zenkaku-only (full-width
        '０'-'９'); ASCII digit singles render HALF-WIDTH on BOTH surfaces now
        (the dialogue zenkaku-only rule was reversed by the complete 00-99
        number-bigram coverage; 2026-06-25)."""
        from font_tools import FNTSYS_CHAR_TILE_MAP, _DIGIT_PAIR_TILES
        for i in range(10):
            self.assertEqual(CHAR_TILE_MAP[str(i)],
                             _DIGIT_PAIR_TILES[(str(i), ' ')])  # dialogue, half-width
            self.assertEqual(FNTSYS_CHAR_TILE_MAP[str(i)],
                             _DIGIT_PAIR_TILES[(str(i), ' ')])  # fntsys, half-width
            self.assertEqual(CHAR_TILE_MAP[chr(0xFF10 + i)], 7 + i)  # full-width stays zenkaku

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
    # test_ui_tiles_not_in_bigram_map removed by the Part 6 data-driven swap
    # (2026-06-27): it enforced 0.2-patch-era UI gaps in the LC bigram grid. We
    # own the patch, and the data-driven packing only uses non-PRESERVED slots
    # (real engine tiles stay in FIXED|KEPT_SPECIAL), validated by the playtest —
    # so those LC-UI gaps are now productively reclaimed.

    def test_specific_known_bigrams(self):
        known = [('t','h'), ('e',' '), ('i','n'), ('m','y'), ('p','e'), ('y',',')]
        for left, right in known:
            self.assertIn((left, right), BIGRAM_TILE_MAP,
                          f"Bigram ('{left}','{right}') missing")

    def test_lc_period_at_position_27(self):
        """0.2 patch has period at LC position 27, not apostrophe."""
        self.assertEqual(_LC_RIGHT_FULL[27], '.')
        # Verify 'a.' bigram exists (a-group, position 27)
        self.assertIn(('a', '.'), BIGRAM_TILE_MAP)
        # Apostrophe should NOT be in LC right chars
        self.assertNotIn("'", _LC_RIGHT_FULL)

    # The old combinatorial-layout structure tests (test_lc_groups_fully_mapped,
    # test_apostrophe_bigrams_exist, test_space_letter_bigrams_exist,
    # test_punct_bigrams_exist, test_no_conflicting_custom_bigrams) were removed
    # by the Part 6 data-driven swap (2026-06-27): they pinned the hand-built
    # _LC_STARTS / _APOSTROPHE_BIGRAMS / _SPACE_LETTER_BIGRAMS positions that no
    # longer exist. Coverage migrated to test_new_font_bigram_layout (distinct
    # tiles, off the preserved set), test_no_bigram_fallback (every script pair
    # mapped) and the north-stars (no waste / within the render buffer).

    def test_special_bigrams_exist(self):
        for pair, tile_idx in _SPECIAL_BIGRAMS.items():
            self.assertIn(pair, BIGRAM_TILE_MAP, f"0.2 patch bigram {pair} missing")
            self.assertEqual(BIGRAM_TILE_MAP[pair], tile_idx)

    def test_all_tiles_within_font_range(self):
        max_tile = ENGLISH_FONT_TILES  # JP base + appended bigrams (numbers, ...)
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


class TestGeneratedFont(unittest.TestCase):
    """Pixel checks against the GENERATED English FONT.BIN — the artifact
    the build actually ships (generate_english_font over the JP source).

    Ported 2026-06-10 (roadmap T02) from the old TestVDFont, which read the
    deleted 0.2-patch font blob and skipped forever. The JP source is
    extracted live from the user's ISO (LANG3_JP_DIR, same contract as
    test_byte_overlays)."""

    @classmethod
    def setUpClass(cls):
        import os
        jp_dir = os.environ.get('LANG3_JP_DIR')
        if not jp_dir:
            raise unittest.SkipTest("LANG3_JP_DIR env var not set")
        candidates = (list(Path(jp_dir).glob('*rack*01*.bin'))
                      or list(Path(jp_dir).glob('*rack*1*.bin'))
                      or list(Path(jp_dir).glob('*.bin')))
        if not candidates:
            raise unittest.SkipTest(f"no Track 01 .bin in {jp_dir}")
        from iso_tools import build_file_index, extract_file_data
        from font_tools import generate_english_font
        image = candidates[0].read_bytes()
        entry = build_file_index(image).get('LANG/FONT.BIN')
        if entry is None:
            raise unittest.SkipTest("LANG/FONT.BIN not in JP ISO")
        jp_font = extract_file_data(image, entry.extent, entry.size)
        cls.font_data = generate_english_font(jp_font)

    def _tile_pixels(self, idx):
        tile = self.font_data[idx*32:(idx+1)*32]
        return sum(bin(b).count('1') for b in tile)

    def test_font_size(self):
        self.assertEqual(len(self.font_data), ENGLISH_FONT_TILES * 32)

    def test_font_tile_count(self):
        self.assertEqual(len(self.font_data) // 32, ENGLISH_FONT_TILES)

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

    def test_space_letter_sample_tiles_have_pixels(self):
        """Sample 0.2 patch space+letter tiles should have visible glyph data."""
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

    def test_bigram_map_tiles_match_generated_font(self):
        """Every tile in BIGRAM_TILE_MAP should have pixels in the
        generated font.

        This catches misalignments where font_tools maps a bigram to a
        tile index that generate_english_font left blank.
        """
        blank_tiles = []
        for pair, idx in BIGRAM_TILE_MAP.items():
            left, right = pair
            # Space bigrams (X + ' ') have left-half content only; (' ',' ') is the
            # all-blank double-space tile (correctly blank).
            if right == ' ' and left != ' ':
                continue
            if pair == (' ', ' '):
                continue
            if self._tile_pixels(idx) == 0:
                blank_tiles.append((pair, idx))
        if blank_tiles:
            examples = blank_tiles[:10]
            msg = (f"{len(blank_tiles)} bigram tiles are blank in the "
                   f"generated font:\n"
                   + '\n'.join(f"  {p} -> tile {i}" for p, i in examples))
            self.fail(msg)


if __name__ == '__main__':
    unittest.main(verbosity=2)
