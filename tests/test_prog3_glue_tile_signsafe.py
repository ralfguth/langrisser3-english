"""Glue-tile immediates must be SIGN-SAFE (<= 0x7F) — the guard that was missing.

The PROG_3 message builder writes glue/special tiles with `mov #imm8, rX;
mov.w rX, @buf`. SH-2 `mov #imm8` SIGN-EXTENDS the 8-bit immediate, so an
immediate with bit 7 set (>= 0x80) becomes 0xFFFFFFxx and `mov.w` writes the
tile code 0xFFxx — outside the 1691-tile range → renders BLANK.

Proven 2026-06-13: repointing the item-use possequive の to tile 0xD4 vanished
in-game; the log showed `val=0000FFD4` (not 0x00D4). Two earlier tests passed
(patch byte == 0xD4; FONT.BIN tile 0xD4 had the glyph) but neither modeled the
EFFECTIVE tile the hardware writes — see memory feedback_tdd_effective_behavior.

This guard models the sign-extension and asserts every glue-tile patch resolves
to a RENDERABLE tile (and, for non-blank glue, a non-empty glyph).
"""
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

NUM_TILES = 1691


def effective_tile(imm8):
    """The 16-bit tile code an SH-2 `mov #imm8; mov.w` actually writes."""
    v = imm8 if imm8 < 0x80 else (imm8 | 0xFFFFFF00)
    return v & 0xFFFF


def _all_glue_patches():
    from prog3_item_use_glue import PROG3_ITEM_USE_GLUE
    from prog3_statup_template import PROG3_STATUP_TEMPLATE
    out = []
    for name, mod in (("item_use", PROG3_ITEM_USE_GLUE),
                      ("statup", PROG3_STATUP_TEMPLATE)):
        for off, repl in mod["LANG/PROG_3.BIN"]:
            # Each replacement is a single immediate byte for a mov #imm site.
            assert len(repl) == 1, f"{name} 0x{off:X}: expected 1 byte, got {repl!r}"
            out.append((name, off, repl[0]))
    return out


def test_signext_model_flags_the_0xD4_regression():
    """Lock the model: 0x2C is safe, 0xD4 (the shipped regression) is not."""
    assert effective_tile(0x2C) == 0x2C
    assert effective_tile(0x00) == 0x00
    assert effective_tile(0x7F) == 0x7F
    assert effective_tile(0xD4) == 0xFFD4           # the bug
    assert effective_tile(0xD4) >= NUM_TILES        # -> out of range -> blank


def test_every_glue_tile_is_renderable():
    """No glue immediate may sign-extend out of the tile range."""
    bad = []
    for name, off, imm in _all_glue_patches():
        eff = effective_tile(imm)
        if eff >= NUM_TILES:
            bad.append(f"{name} 0x{off:X}: mov #0x{imm:02X} -> tile 0x{eff:04X} (blank)")
    assert not bad, "sign-extended (>=0x80) glue tiles render blank:\n  " + "\n  ".join(bad)


def test_nonblank_glue_tiles_have_a_glyph():
    """Each non-zero glue tile must actually have ink in the generated font at
    its EFFECTIVE index (0 = intentional blank/space, skipped)."""
    jp = PROJ / "data" / "jp" / "font_jp.bin"
    if not jp.exists():
        pytest.skip("data/jp/font_jp.bin not present")
    from font_tools import generate_english_font
    font = generate_english_font(jp.read_bytes())
    bad = []
    for name, off, imm in _all_glue_patches():
        eff = effective_tile(imm)
        if eff == 0 or eff >= NUM_TILES:
            continue
        ink = sum(bin(b).count("1") for b in font[eff * 32:(eff + 1) * 32])
        if ink == 0:
            bad.append(f"{name} 0x{off:X}: tile 0x{eff:02X} is blank in the font")
    assert not bad, "glue tiles pointing at blank glyphs:\n  " + "\n  ".join(bad)
