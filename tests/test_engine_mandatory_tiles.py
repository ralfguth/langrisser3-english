"""Part 0 of the new-font rebuild: LOCK the engine-mandatory tile skeleton.

The engine writes/reads these tile indices from compiled SH-2 code — `mov #imm`
glue (blank 0x00, ": " 0x01, 's 0x2C) and the number formatter (digits 7-16 =
value+7). The new from-scratch FONT.BIN MUST keep them at these EXACT positions,
so this guard byte-locks them against the generated font: any accidental move or
corruption during the data-driven rebuild turns it RED.

See archive/docs/20260625_new_font_from_scratch_plan.md (Part 0) and the
engine-fixed map in 20260625_font_refactor_handoff.md.

Glyph note: tiles 0,1,7-16 are immutable. Tile 44 ('s possessive) keeps its
POSITION fixed forever; its GLYPH is slated to be standardized (condensed ->
normal 's) in Part 3 — when that lands, update GOLDEN[44] in the SAME commit.
The RED here is then the intended-change signal (TDD canon), not a regression.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import font_tools as ft  # noqa: E402
import new_font as nf     # noqa: E402

JP_FONT = REPO / "data" / "jp" / "font_jp.bin"
TILE = 32  # bytes per 16x16 1bpp tile

# Byte-exact golden for the engine-mandatory tiles in the NEW (shipping) font.
# 0,1,7-16 are preserved from the JP base; tile 44 is the standardized 's = [',s]
# (apostrophe left + s right) that new_font draws at the の position. Deterministic.
GOLDEN = {
    0:  '0000000000000000000000000000000000000000000000000000000000000000',  # full-width blank
    1:  '0000000000000000000000001800180000000000000018001800000000000000',  # ": "
    7:  '000000000000038006c00c600ce00de00f600e600c6006c00380000000000000',  # 0
    8:  '00000000000001800380078001800180018001800180018003c0000000000000',  # 1
    9:  '00000000000007c00c60006000c00180030006000c600c600fe0000000000000',  # 2
    10: '00000000000007e0046000c0018003c0006000600060066003c0000000000000',  # 3
    11: '00000000000001c001c003c003c006c006c00cc00fe000c001e0000000000000',  # 4
    12: '0000000000000fc00c000c000f800cc00060006008600cc00780000000000000',  # 5
    13: '00000000000003c006000c000f800ec00c600c600c6006c00380000000000000',  # 6
    14: '0000000000000fe00c60006000c000c001800180030003000300000000000000',  # 7
    15: '00000000000007c00c600c600c6007c00c600c600c600c6007c0000000000000',  # 8
    16: '000000000000038006c00c600c600c6006e003e0006000c00780000000000000',  # 9
    44: '000000000000180018003000007c00c600c0007c000600c6007c000000000000',  # 's = [',s] (の): apostrophe left + s right
}


def _font():
    return nf.generate_new_font(JP_FONT.read_bytes())


def test_engine_mandatory_tiles_byte_locked():
    """The engine-mandatory tiles stay byte-identical at their fixed positions."""
    font = _font()
    bad = []
    for tile, expected in GOLDEN.items():
        got = font[tile * TILE:(tile + 1) * TILE].hex()
        if got != expected:
            bad.append((tile, expected, got))
    if bad:
        lines = [f"  tile {t}: expected {e[:20]}… got {g[:20]}…" for t, e, g in bad]
        raise AssertionError(
            "engine-mandatory tiles moved/corrupted (they are written by SH-2 "
            "`mov #imm` / the number formatter and MUST stay put):\n"
            + "\n".join(lines)
        )


def test_engine_mandatory_semantic_anchors():
    """The encoder maps the mandatory glyphs to their fixed indices."""
    assert ft.CHAR_TILE_MAP.get('　') == 0, "full-width blank must be tile 0"
    assert ft.CHAR_TILE_MAP.get(':') == 1, "': ' colon must be tile 1"
