"""Tests guaranteeing that umlaut bigram tiles are actually painted
into the EN FONT.BIN (not leaving the JP kanji underneath).

Bug history: when (m,ü)/(g,ü)/(h,ä)/(ä,r)/(B,ö)/(ö,s) were registered
in BIGRAM_TILE_MAP but the corresponding `write_tile()` call was
missing, the encoder produced D00.DAT entries referencing the new
slots while FONT.BIN still held the JP kanji at those positions —
producing "Ri詩ler" in-game.

These tests close that gap by asserting, for every umlaut bigram in
`_CUSTOM_UMLAUT_BIGRAMS`, that the slot in the generated EN font:
1. differs from the JP source at that slot (we DID overwrite it)
2. matches `_interleave(left_glyph, right_glyph)` (correct content)
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "tools"))

import pytest
from tools.font_tools import (
    _CUSTOM_UMLAUT_BIGRAMS,
    _LETTER_GLYPHS,
    _UMLAUT_HALF_GLYPHS,
    _interleave,
    BIGRAM_TILE_MAP,
    generate_english_font,
)

TILE_SIZE = 32
JP_TRACK01 = (
    Path.home()
    / "Jogos/emulacao/romsets/sega-saturn/cue-bin"
    / "Langrisser III (Japan)/Langrisser III (Japan) (3M) (Track 01).bin"
)


@pytest.fixture(scope="module")
def jp_font_bytes() -> bytes:
    """Load JP FONT.BIN once for all tests in this module."""
    if not JP_TRACK01.exists():
        pytest.skip(f"JP track01 not present at {JP_TRACK01}")
    import build as b
    image = JP_TRACK01.read_bytes()
    idx = b.build_file_index(bytearray(image))
    fe = idx["LANG/FONT.BIN"]
    return b.extract_file_data(bytearray(image), fe.extent, fe.size)


@pytest.fixture(scope="module")
def en_font_bytes(jp_font_bytes: bytes) -> bytes:
    return generate_english_font(jp_font_bytes)


def _expected_bigram_tile(left: str, right: str) -> bytes:
    """Compose the expected interleaved tile bytes for (left, right)."""
    left_glyph = _UMLAUT_HALF_GLYPHS.get(left, _LETTER_GLYPHS.get(left))
    right_glyph = _UMLAUT_HALF_GLYPHS.get(right, _LETTER_GLYPHS.get(right))
    assert left_glyph is not None, f"no glyph for {left!r}"
    assert right_glyph is not None, f"no glyph for {right!r}"
    return _interleave(left_glyph, right_glyph)


def _get_tile(font: bytes, idx: int) -> bytes:
    return font[idx * TILE_SIZE : (idx + 1) * TILE_SIZE]


class TestCustomUmlautBigramsPainted:
    """Every (X, ü)/(ä, X)/(B, ö)/(ö, s) etc. bigram must be:
    1. Registered in BIGRAM_TILE_MAP (encoder will reference it)
    2. Actually written to the EN font (tile bytes differ from JP)
    3. Match the expected interleave of letter + umlaut glyphs
    """

    @pytest.mark.parametrize("pair,slot", sorted(_CUSTOM_UMLAUT_BIGRAMS.items()))
    def test_registered_in_encoder_map(self, pair, slot):
        assert pair in BIGRAM_TILE_MAP, (
            f"bigram {pair!r} not in BIGRAM_TILE_MAP — encoder won't pick it"
        )
        assert BIGRAM_TILE_MAP[pair] == slot, (
            f"bigram {pair!r} maps to {BIGRAM_TILE_MAP[pair]} in encoder, "
            f"but _CUSTOM_UMLAUT_BIGRAMS says {slot}"
        )

    @pytest.mark.parametrize("pair,slot", sorted(_CUSTOM_UMLAUT_BIGRAMS.items()))
    def test_overwrites_jp_original(self, pair, slot, en_font_bytes, jp_font_bytes):
        en_tile = _get_tile(en_font_bytes, slot)
        jp_tile = _get_tile(jp_font_bytes, slot)
        assert en_tile != jp_tile, (
            f"tile {slot} (bigram {pair!r}) was NOT overwritten — still holds "
            f"the JP original (which renders as kanji in dialogue text). "
            f"Add a write_tile() call for _CUSTOM_UMLAUT_BIGRAMS in "
            f"generate_english_font()."
        )

    @pytest.mark.parametrize("pair,slot", sorted(_CUSTOM_UMLAUT_BIGRAMS.items()))
    def test_matches_expected_interleave(self, pair, slot, en_font_bytes):
        left, right = pair
        expected = _expected_bigram_tile(left, right)
        actual = _get_tile(en_font_bytes, slot)
        assert actual == expected, (
            f"tile {slot} (bigram {pair!r}) does not match expected "
            f"interleave(_glyph[{left!r}], _glyph[{right!r}]).\n"
            f"  expected: {expected.hex()}\n"
            f"  actual:   {actual.hex()}"
        )

    def test_no_umlaut_slot_collisions(self):
        slots = list(_CUSTOM_UMLAUT_BIGRAMS.values())
        assert len(slots) == len(set(slots)), (
            f"duplicate slots in _CUSTOM_UMLAUT_BIGRAMS: {slots}"
        )

    def test_all_slots_outside_cwx_range(self):
        """User-defined contract: umlaut bigrams must live OUTSIDE the CWX
        range (1500-1620), because the engine renders CWX tiles with
        name-input-grid spacing that produces visible inter-tile gaps in
        dialogue text."""
        for pair, slot in _CUSTOM_UMLAUT_BIGRAMS.items():
            assert not (1500 <= slot <= 1620), (
                f"bigram {pair!r} at slot {slot} is inside CWX range — "
                f"this causes name-input spacing in dialogue ('Altemü ller')"
            )
