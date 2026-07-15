"""Lock "NP" as a COMMON Eagle III bigram (not a 0.2 patch special glyph).

"NP" (used by fntsys1 "NPC" / "NPC Unit") is a plain half-width uppercase
bigram, handled by the normal bigram machinery like AT/DF — ('N','P') lives in
BIGRAM_TILE_MAP and its tile is a standard Eagle III interleave of N + P. The
fntsys1 entries are plain text "NPC", so the encoder emits ('N','P')('C',' ').
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import font_tools as ft                                      # noqa: E402
from d00_tools import encode_text_to_entry                  # noqa: E402
from iso_tools import build_file_index, extract_file_data    # noqa: E402

JP_ISO = Path("/home/ralf/Jogos/emulacao/romsets/sega-saturn/cue-bin/"
              "Langrisser III (Japan)/Langrisser III (Japan) (3M) (Track 01).bin")


def test_np_is_a_common_bigram():
    """('N','P') is in BIGRAM_TILE_MAP (a normal bigram), NOT a 0.2 patch override."""
    assert ('N', 'P') in ft.BIGRAM_TILE_MAP
    tile = ft.BIGRAM_TILE_MAP[('N', 'P')]
    assert tile not in ft._MENU_GLYPHS, "NP must not be a 0.2 patch-override tile"


def test_npc_encodes_to_np_plus_c_space():
    """Plain "NPC " encodes as ('N','P') then ('C',' ') — the user's spec."""
    import struct
    rec = encode_text_to_entry("NPC ", dict(ft.CHAR_TILE_MAP),
                               bigram_tile_map=ft.BIGRAM_TILE_MAP)
    ids = [struct.unpack_from(">H", rec, i)[0]
           for i in range(0, len(rec) - 1, 2)]
    ids = [w for w in ids if w != 0xFFFF]
    assert ids[0] == ft.BIGRAM_TILE_MAP[('N', 'P')]
    assert ids[1] == ft.BIGRAM_TILE_MAP[('C', ' ')]


@pytest.mark.skipif(not JP_ISO.exists(), reason="JP ISO absent")
def test_np_tile_is_eagle_interleave():
    img = bytearray(JP_ISO.read_bytes())
    e = build_file_index(img)["LANG/FONT.BIN"]
    font = ft.generate_english_font(extract_file_data(img, e.extent, e.size))
    tile = ft.BIGRAM_TILE_MAP[('N', 'P')]
    got = font[tile * 32:(tile + 1) * 32]
    want = ft._interleave(ft._LETTER_GLYPHS['N'], ft._LETTER_GLYPHS['P'])
    assert got == want, "NP tile must be the Eagle III N+P interleave"


# test_legacy_04fc_position_repainted_with_our_np was removed by the Part 6
# data-driven swap (2026-06-27): it pinned a repaint of the legacy <$04FC> tile
# 1276, which the data-driven packing now reclaims for a different bigram. NP's
# own coverage is locked by the three tests above (it pairs, encodes, and the
# tile is the Eagle N+P interleave at its packed position).
