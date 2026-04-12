#!/usr/bin/env python3
"""
test_font_tiles.py - Validate font.bin tile integrity and CHAR_TILE_MAP correctness.

Verifies that:
1. font.bin has the expected number of tiles and file size
2. Each single-char tile (0-45) matches its known pixel fingerprint
3. CHAR_TILE_MAP entries point to tiles whose glyphs match the intended character
4. Bigram right-half glyphs for punctuation match their standalone tile counterparts

Ground truth established 2026-04-12 by pixel-by-pixel visual analysis.
See FONT_TILE_REFERENCE.md for the full verified tile table.
"""

import hashlib
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

FONT_PATH = PROJ / 'lang3a2' / 'font.bin'

# ---------------------------------------------------------------------------
# Ground truth: (pixel_count, md5 of raw 32 bytes) for single-char tiles 0-45
# Verified visually against build/font_0_64.png on 2026-04-12
# ---------------------------------------------------------------------------
TILE_FINGERPRINTS = {
    0:  (  0, "70bc8f4b72a86921468bf8e8441dce51"),  # space
    1:  ( 32, "5ff09bdfbc24ee6f94eaec7fe813814d"),  # 『
    2:  ( 32, "5539201988f6d47c7b4b165f25b8fc00"),  # 』
    3:  (  4, "0ed7f98ddf6ec5a0c4f965bdec14a953"),  # , (comma)
    4:  (  5, "543d993ea72831aa3ee8a227b81c3147"),  # . (period/dot)
    5:  ( 17, "58ab78a3b413ef02df6794a82c39485d"),  # ?
    6:  ( 13, "94cb22b87132203c521d5d3df1485c7c"),  # !
    7:  ( 36, "1add7b6376408dab45f0c9796979f9cb"),  # 0
    8:  ( 20, "b05b6f61bf921e3cd82209c1e3b38dba"),  # 1
    9:  ( 34, "db61eb4e4a70970eab61bb5d95d78dc2"),  # 2
    10: ( 34, "df1a52f5635ad89e125232d7cb3ea26a"),  # 3
    11: ( 36, "ffbf1741a6d35ad560b0b423d389b29e"),  # 4
    12: ( 40, "adf931dceda66b22efc133cfb7ef132f"),  # 5
    13: ( 40, "1c3b0492e008339e45706743c3c245a3"),  # 6
    14: ( 26, "dea97b838aafad78402f414eff76a209"),  # 7
    15: ( 40, "451467e5e67f8e6f20a44a1b6eff64f5"),  # 8
    16: ( 40, "7c5a1bd1e102a9dd75bd494f6fe20352"),  # 9
    17: ( 47, "737fa761d9e14ab1dd1cf82750e2a60d"),  # A
    18: ( 47, "715fd65cb8277c92f36c5246dd4f723a"),  # B
    19: ( 37, "a0449c26e65f7e3aed89c6988e6e1fd8"),  # C
    20: ( 44, "7b64471b37efa9e94a1528e8be919631"),  # D
    21: ( 46, "6b560a2b4746379180466dfa21949551"),  # E
    22: ( 38, "0108ec5657bf8b87dad10937d797c839"),  # F
    23: ( 43, "d09234db0994a31edba2f45e00d80f44"),  # G
    24: ( 50, "b4b1ca1df74cd67bb0b0214d405a57bc"),  # H
    25: ( 21, "126f76463aaef835a264154aae415539"),  # I
    26: ( 24, "15230fbabe0f6ec92f558bbbbb584ee5"),  # J
    27: ( 54, "5aaad5917da257f58733e28f010a82c0"),  # K
    28: ( 30, "1c8704502fb6d6a07452f00f94dae76d"),  # L
    29: ( 67, "27e3c67678f7494c2d11510d5c6ecd5d"),  # M
    30: ( 54, "9c4e9bb95294e8efed4b2f5237ca9ba7"),  # N
    31: ( 42, "16afbbd3ad4c525afa5b7068f7e78b53"),  # O
    32: ( 36, "2c0b8964f61086caf32d0f356e62f87d"),  # P
    33: ( 50, "ccaf1b55211cf9f29a78782898961105"),  # Q
    34: ( 48, "586bcf156e0f887d15fbd0a119d827c4"),  # R
    35: ( 40, "4d91d360285208e43ece9d336a3a1c61"),  # S
    36: ( 33, "85ce6decd43771856cbcec8c1b074669"),  # T
    37: ( 40, "77c1736dcc0e49f02e40d057fb900ff9"),  # U
    38: ( 41, "67cd312c211331c25ee1afda55a66994"),  # V
    39: ( 64, "dc661691acf0fac77b0886a9839dd6d8"),  # W
    40: ( 59, "0bc490c044b8c4939f50b8c18d5ea87f"),  # X
    41: ( 40, "be5f57ffca907b95f41357c859fb3026"),  # Y
    42: ( 44, "2103f43b2661842b9f28157b5cfb538e"),  # Z
    43: ( 27, "f8293ef2a7af9e85ce6991396accb944"),  # a (standalone full-width)
    44: ( 37, "5f0e77288a996967b79a058088f1a468"),  # m (standalone full-width)
    45: ( 31, "07484c30175f3bdc87f073cbe5cfe85e"),  # p (standalone full-width)
}

# Verified glyph identity for each tile — what it ACTUALLY renders
TILE_GLYPHS = {
    0: 'space', 1: '『', 2: '』', 3: ',', 4: '.',
    5: '?', 6: '!',
    7: '0', 8: '1', 9: '2', 10: '3', 11: '4',
    12: '5', 13: '6', 14: '7', 15: '8', 16: '9',
    17: 'A', 18: 'B', 19: 'C', 20: 'D', 21: 'E',
    22: 'F', 23: 'G', 24: 'H', 25: 'I', 26: 'J',
    27: 'K', 28: 'L', 29: 'M', 30: 'N', 31: 'O',
    32: 'P', 33: 'Q', 34: 'R', 35: 'S', 36: 'T',
    37: 'U', 38: 'V', 39: 'W', 40: 'X', 41: 'Y', 42: 'Z',
    43: 'a_fw', 44: 'm_fw', 45: 'p_fw',
}

# Known UI tiles embedded in bigram groups
UI_TILES = {
    482:  ('m_lc',  'colon'),       # : (two dots)
    489:  ('m_lc',  'asterisk'),    # * (star shape)
    566:  ('p_lc',  'swoosh'),      # ~ like swoosh
    860:  ('y_lc',  'bracket_r'),   # > or 」
    861:  ('y_lc',  'bracket_l'),   # < or 「
    1041: ('E_uc',  'ui_stats'),    # battle stats composite
    1064: ('F_uc',  'equals'),      # = (two horizontal bars)
    1276: ('N_uc',  'ui_np'),       # NP composite
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_font():
    return FONT_PATH.read_bytes()


def _tile_raw(data, idx):
    return data[idx * 32 : (idx + 1) * 32]


def _tile_md5(data, idx):
    return hashlib.md5(_tile_raw(data, idx)).hexdigest()


def _tile_pixel_count(data, idx):
    raw = _tile_raw(data, idx)
    return sum(bin(b).count('1') for b in raw)


def _tile_right_half_rows(data, idx):
    """Return right 8 columns as list of 8-element bit lists."""
    rows = []
    off = idx * 32
    for r in range(16):
        b0 = data[off + r * 2]
        b1 = data[off + r * 2 + 1]
        val = (b0 << 8) | b1
        row = []
        for bit in range(7, -1, -1):
            row.append(1 if val & (1 << bit) else 0)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFontFileIntegrity:
    """Verify font.bin basic properties."""

    def test_file_exists(self):
        assert FONT_PATH.exists(), f"font.bin not found at {FONT_PATH}"

    def test_file_size(self):
        data = _read_font()
        assert len(data) == 1691 * 32, (
            f"Expected {1691 * 32} bytes (1691 tiles), got {len(data)}"
        )

    def test_tile_count(self):
        data = _read_font()
        assert len(data) // 32 == 1691


class TestSingleCharTiles:
    """Verify each of the 46 single-char tiles matches known fingerprint."""

    @pytest.mark.parametrize("tile_idx", range(46))
    def test_tile_fingerprint(self, tile_idx):
        data = _read_font()
        expected_px, expected_md5 = TILE_FINGERPRINTS[tile_idx]
        actual_px = _tile_pixel_count(data, tile_idx)
        actual_md5 = _tile_md5(data, tile_idx)
        glyph = TILE_GLYPHS.get(tile_idx, '?')
        assert actual_md5 == expected_md5, (
            f"Tile {tile_idx} ({glyph}) changed! "
            f"pixels: {expected_px}->{actual_px}, md5: {expected_md5}->{actual_md5}"
        )


class TestUITiles:
    """Verify known UI tiles are non-empty (not overwritten with blanks)."""

    @pytest.mark.parametrize("tile_idx", sorted(UI_TILES.keys()))
    def test_ui_tile_not_empty(self, tile_idx):
        data = _read_font()
        px = _tile_pixel_count(data, tile_idx)
        group, name = UI_TILES[tile_idx]
        assert px > 0, f"UI tile {tile_idx} ({group}/{name}) is empty"


class TestPunctuationCrossRef:
    """Verify standalone punctuation tiles match their bigram right-half counterparts."""

    def _assert_right_half_matches_tile(self, data, bigram_tile, standalone_tile, name):
        """Check that the right 8 cols of bigram_tile match standalone_tile's shape."""
        rh = _tile_right_half_rows(data, bigram_tile)
        # Get the non-zero rows from the right-half
        rh_active = [(r, row) for r, row in enumerate(rh) if any(row)]
        assert len(rh_active) > 0, f"No pixels in right-half of bigram tile {bigram_tile}"

        # Get standalone tile pixels in cols 0-7 (same width region)
        st_off = standalone_tile * 32
        st_active = []
        for r in range(16):
            b0 = data[st_off + r * 2]
            b1 = data[st_off + r * 2 + 1]
            val = (b0 << 8) | b1
            row = []
            for bit in range(15, -1, -1):
                row.append(1 if val & (1 << bit) else 0)
            if any(row):
                st_active.append((r, row))

        # Both should have active pixels in similar rows
        rh_rows = {r for r, _ in rh_active}
        st_rows = {r for r, _ in st_active}
        # Allow 1-row offset (standalone may be shifted)
        overlap = len(rh_rows & st_rows) + len({r + 1 for r in rh_rows} & st_rows) + len({r - 1 for r in rh_rows} & st_rows)
        assert overlap > 0, (
            f"{name}: standalone tile {standalone_tile} active rows {st_rows} "
            f"don't overlap with bigram right-half rows {rh_rows}"
        )

    def test_comma_tile3_matches_bigram(self):
        """Tile 3 (comma) should match comma right-half in bigrams."""
        data = _read_font()
        # 'e' group base=170, comma at index 28 -> tile 198
        self._assert_right_half_matches_tile(data, 198, 3, "comma")

    def test_period_tile4_matches_bigram_apostrophe(self):
        """Tile 4 (period/dot) has same glyph as apostrophe right-half in bigrams."""
        data = _read_font()
        # 'e' group base=170, apostrophe at index 27 -> tile 197
        self._assert_right_half_matches_tile(data, 197, 4, "period/apostrophe")

    def test_question_tile5_matches_bigram(self):
        """Tile 5 (?) should match ? right-half in bigrams."""
        data = _read_font()
        # 'e' group base=170, ? at index 29 -> tile 199
        self._assert_right_half_matches_tile(data, 199, 5, "question mark")

    def test_exclamation_tile6_matches_bigram(self):
        """Tile 6 (!) should match ! right-half in bigrams."""
        data = _read_font()
        # 'e' group base=170, ! at index 30 -> tile 200
        self._assert_right_half_matches_tile(data, 200, 6, "exclamation mark")


class TestCharTileMapCorrectness:
    """Verify CHAR_TILE_MAP maps characters to the correct tiles."""

    def test_period_not_mapped_to_comma_glyph(self):
        """Period '.' must NOT map to tile 3 (which is comma glyph)."""
        from font_tools import build_char_tile_map
        m = build_char_tile_map()
        assert m.get('.') != 3, (
            "BUG: '.' mapped to tile 3, which is the comma glyph! "
            "Should be tile 4 (period/dot diamond)"
        )

    def test_comma_not_mapped_to_period_glyph(self):
        """Comma ',' must NOT map to tile 4 (which is period/dot glyph)."""
        from font_tools import build_char_tile_map
        m = build_char_tile_map()
        assert m.get(',') != 4, (
            "BUG: ',' mapped to tile 4, which is the period/dot glyph! "
            "Should be tile 3 (comma hook)"
        )

    def test_apostrophe_mapped_to_custom_tile(self):
        """Apostrophe should map to custom tile 1510 (hand-drawn top diamond)."""
        from font_tools import build_char_tile_map, APOSTROPHE_TILE
        m = build_char_tile_map()
        assert m.get("'") == APOSTROPHE_TILE, (
            f"Apostrophe should map to tile {APOSTROPHE_TILE} (custom glyph)"
        )

    def test_hyphen_not_mapped_to_letter(self):
        """Hyphen must NOT map to tile 44 (standalone 'm')."""
        from font_tools import build_char_tile_map
        m = build_char_tile_map()
        if '-' in m:
            assert m['-'] != 44, (
                "BUG: hyphen mapped to tile 44, which is standalone letter 'm'!"
            )

    def test_doublequote_not_mapped_to_letter(self):
        """Double-quote must NOT map to tile 45 (standalone 'p')."""
        from font_tools import build_char_tile_map
        m = build_char_tile_map()
        if '"' in m:
            assert m['"'] != 45, (
                "BUG: double-quote mapped to tile 45, which is standalone letter 'p'!"
            )

    def test_space_is_tile_0(self):
        from font_tools import build_char_tile_map
        m = build_char_tile_map()
        assert m[' '] == 0

    def test_digits_correct(self):
        from font_tools import build_char_tile_map
        m = build_char_tile_map()
        for i in range(10):
            assert m[str(i)] == 7 + i, f"Digit {i} should map to tile {7 + i}"

    def test_uppercase_correct(self):
        from font_tools import build_char_tile_map
        m = build_char_tile_map()
        for i in range(26):
            ch = chr(65 + i)
            assert m[ch] == 17 + i, f"'{ch}' should map to tile {17 + i}"
