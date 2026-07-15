"""test_fntsys_formation.py — encoder validation for the formation-icon glyphs.

fntsys1 records 98-102 (and the scen001 tutorial) show the five formation icons
SQUARE / COLUMN / LINE / DIAGONAL-L / DIAGONAL-R. They are JP-font glyphs we
PRESERVE verbatim at tiles 0x014A-0x014E; the EN script carries the readable
glyph (囗 ｜ ― ＼ ／), NOT an absolute <$014A> control code.

These tests are the guard the project requires for any absolute glyph index: they
prove EACH mapping still fetches the EXPECTED glyph. When the font is refactored
and glyph slots move, _FORMATION_GLYPH_TILES must be updated here in one place and
these tests fail loudly if a mapping ends up on a blank or wrong slot.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from d00_tools import encode_text_to_entry            # noqa: E402
from font_tools import (                              # noqa: E402
    BIGRAM_TILE_MAP,
    _FORMATION_GLYPH_TILES,
    generate_english_font,
)
from fnt_sys_tools import _build_fntsys_char_map        # noqa: E402

TILE_SIZE = 32
JP_FONT = PROJ / "data" / "jp" / "font_jp.bin"


def _encode(s: str) -> bytes:
    return encode_text_to_entry(s, _build_fntsys_char_map(),
                                bigram_tile_map=BIGRAM_TILE_MAP)


def test_each_glyph_encodes_to_one_expected_tile():
    """The readable glyph encodes to exactly its mapped formation tile (no drop)."""
    for glyph, idx in _FORMATION_GLYPH_TILES.items():
        rec = _encode(glyph)
        assert rec == idx.to_bytes(2, "big"), (
            f"{glyph!r} encoded to {rec.hex()} (expected tile {idx:#06x}); "
            f"a 0-byte result means the glyph is missing from the char map "
            f"and would vanish in-game"
        )


def test_mapping_lands_on_a_preserved_nonzero_jp_glyph():
    """Each mapped tile in the GENERATED EN font carries the expected glyph.

    The expected glyph is the JP-font formation icon, which generate_english_font
    must preserve verbatim (it never repaints 0x014A-0x014E). A blank or repainted
    slot here means the mapping no longer fetches the right glyph.
    """
    jp = JP_FONT.read_bytes()
    en = generate_english_font(jp)
    for glyph, idx in _FORMATION_GLYPH_TILES.items():
        jp_tile = jp[idx * TILE_SIZE:(idx + 1) * TILE_SIZE]
        en_tile = en[idx * TILE_SIZE:(idx + 1) * TILE_SIZE]
        assert any(jp_tile), f"{glyph!r}: JP tile {idx:#06x} is blank (wrong slot)"
        assert en_tile == jp_tile, (
            f"{glyph!r}: EN tile {idx:#06x} was repainted/blanked; the encoder "
            f"would now point at the wrong glyph"
        )


def test_fntsys1_formation_records_round_trip():
    """The production fntsys1E records 98-102 encode to the five formation tiles."""
    lines = (PROJ / "scripts" / "en" / "fntsys1E.txt").read_text(
        encoding="utf-8").splitlines()
    records = [ln[:-len("<$FFFF>")] for ln in lines if ln.endswith("<$FFFF>")]
    expected = list(_FORMATION_GLYPH_TILES.values())
    # records 98-102 are 1-indexed -> slice [97:102]
    formation_records = records[97:102]
    got = [_encode(r) for r in formation_records]
    assert got == [t.to_bytes(2, "big") for t in expected], (
        f"fntsys1E formation records do not encode to {[hex(t) for t in expected]}; "
        f"got {[g.hex() for g in got]} for {formation_records!r}"
    )
