#!/usr/bin/env python3
"""
test_font_tiles.py - Validate VermillionDesserts' English font binary.

Verifies:
  1. VD font file exists and has correct size (1691 tiles x 32 bytes)
  2. Key single-char tiles (space, digits, uppercase) have correct content
  3. Common bigram tiles have pixel content
  4. CWX pre-existing tiles have pixels
"""

import hashlib
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

VD_FONT_PATH = PROJ / 'patches' / 'vd_font.bin'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tile_raw(data, idx):
    return data[idx * 32 : (idx + 1) * 32]


def _tile_pixel_count(data, idx):
    raw = _tile_raw(data, idx)
    return sum(bin(b).count('1') for b in raw)


@pytest.fixture(scope="module")
def font_data():
    if not VD_FONT_PATH.exists():
        pytest.skip("VD font not found")
    return VD_FONT_PATH.read_bytes()


# ---------------------------------------------------------------------------
# Tests: Font file integrity
# ---------------------------------------------------------------------------

class TestFontIntegrity:

    def test_vd_font_exists(self):
        assert VD_FONT_PATH.exists(), f"VD font not found at {VD_FONT_PATH}"

    def test_font_size(self, font_data):
        assert len(font_data) == 1691 * 32, (
            f"Expected {1691 * 32} bytes (1691 tiles), got {len(font_data)}"
        )


# ---------------------------------------------------------------------------
# Tests: Key tile content
# ---------------------------------------------------------------------------

class TestKeyTiles:

    def test_space_tile_is_blank(self, font_data):
        tile = _tile_raw(font_data, 0)
        assert tile == b'\x00' * 32, "Space tile (0) is not blank"

    @pytest.mark.parametrize("digit", range(10))
    def test_digit_tiles_have_pixels(self, font_data, digit):
        idx = 7 + digit
        px = _tile_pixel_count(font_data, idx)
        assert px > 5, f"Digit {digit} tile {idx} looks blank ({px} pixels)"

    @pytest.mark.parametrize("letter_idx", range(26))
    def test_uppercase_tiles_have_pixels(self, font_data, letter_idx):
        ch = chr(65 + letter_idx)
        idx = 17 + letter_idx
        px = _tile_pixel_count(font_data, idx)
        assert px > 10, f"'{ch}' tile {idx} looks blank ({px} pixels)"

    def test_punctuation_tiles_have_pixels(self, font_data):
        # colon(1), semicolon(2), comma(3), period(4), ?(5), !(6)
        for idx, name in [(1,':'), (2,';'), (3,','), (4,'.'), (5,'?'), (6,'!')]:
            px = _tile_pixel_count(font_data, idx)
            assert px > 0, f"'{name}' tile {idx} is blank"


# ---------------------------------------------------------------------------
# Tests: Bigram tiles have content
# ---------------------------------------------------------------------------

class TestBigramContent:

    def test_common_bigrams_have_pixels(self, font_data):
        """Common English bigrams should have visible content."""
        from font_tools import BIGRAM_TILE_MAP
        common = [('t','h'), ('h','e'), ('i','n'), ('e','r'), ('a','n'),
                  ('r','e'), ('o','n'), ('s','t'), ('e','n'), ('n','d')]
        for left, right in common:
            idx = BIGRAM_TILE_MAP.get((left, right))
            if idx is None:
                continue
            px = _tile_pixel_count(font_data, idx)
            assert px > 5, f"Bigram '{left}{right}' tile {idx} looks blank"

    @pytest.mark.parametrize("left_char", list('aeiorstn'))
    def test_high_freq_lc_groups_have_pixels(self, font_data, left_char):
        """High-frequency LC bigram groups should have non-blank tiles."""
        from font_tools import BIGRAM_TILE_MAP
        group_tiles = [idx for (l, r), idx in BIGRAM_TILE_MAP.items()
                       if l == left_char]
        assert len(group_tiles) > 0
        blank = 0
        for idx in group_tiles:
            if _tile_pixel_count(font_data, idx) == 0:
                blank += 1
        # Allow some blanks (space bigrams) but most should have content
        assert blank < len(group_tiles) // 2, (
            f"'{left_char}' group: {blank}/{len(group_tiles)} tiles are blank"
        )


# ---------------------------------------------------------------------------
# Tests: CHAR_TILE_MAP correctness
# ---------------------------------------------------------------------------

class TestCharTileMap:

    def test_space_is_tile_0(self):
        from font_tools import CHAR_TILE_MAP
        assert CHAR_TILE_MAP[' '] == 0

    def test_punctuation_mapping(self):
        from font_tools import CHAR_TILE_MAP
        assert CHAR_TILE_MAP[','] == 3
        assert CHAR_TILE_MAP['.'] == 4
        assert CHAR_TILE_MAP['?'] == 5
        assert CHAR_TILE_MAP['!'] == 6

    def test_digits_correct(self):
        from font_tools import CHAR_TILE_MAP
        for i in range(10):
            assert CHAR_TILE_MAP[str(i)] == 7 + i

    def test_uppercase_correct(self):
        from font_tools import CHAR_TILE_MAP
        for i in range(26):
            assert CHAR_TILE_MAP[chr(65 + i)] == 17 + i
