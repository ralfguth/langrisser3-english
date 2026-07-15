"""test_prog3_item_use_glue.py — item-use message の-glue -> 's (TDD guard).

Bug (user playtest 2026-06-13): "TiarisboNectar was used!" — the item-use
message "[Name]の[Item]をつかった！" rendered the JP possessive particle の
(tile 0x5C) which our repainted font draws as the "bo" bigram.

RE (Ghidra, FUN_0607c430 = PROG_3 system-message builder, opcodes 0x10/0x13):
  - 0x0607C8C2 (file 0x2A0C3): mov #0x5c,r6 ; mov.w r6,@r8  — の glue, written
    after the name function (PTR_FUN_0607c98c) and before the item-name table
    (DAT_0607c988): "[Name]の[Item]".
  - 0x0607C91B (file 0x2A11B): same pattern, the opcode's second name path.

Fix: 0x5C -> 0x2C (tile 44 = our 's). Composes "[Name]'s[Item] was used!".
Tile 44 is an 8-bit-loadable LOW slot ON PURPOSE: SH-2 `mov #imm8` SIGN-EXTENDS,
so a glue tile index >= 0x80 becomes 0xFFxx and renders blank. (A 0xD4 attempt
at adding a trailing space did exactly that — proven in-game; see
tests/test_prog3_glue_tile_signsafe.py and memory
feedback_tdd_effective_behavior.) The item name is appended with no leading
space, so the line reads "Tiaris'sMagic Herb" (glued). Giving it a separating
space needs a SECOND sign-safe (<= 0x7F) packed-'s slot, deferred to the
FONT.BIN refactor (reference_engine_immediate_tile_constraint).

Red state: before tools/prog3_item_use_glue.py was wired, the build left
0x5C at both sites (the "bo" mojibake in the screenshot).
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

ITEM_USE_GLUE_OFFSETS = (0x2A0C3, 0x2A11B)
APOSTROPHE_S_TILE = 0x2C       # tile 44 = our 's glyph (sign-safe, < 0x80)
JP_GLUE = 0x5C                 # の particle tile in the JP baseline


def _prog3_from_build():
    from iso_tools import build_file_index, extract_file_data
    builds = sorted((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = builds[-1].read_bytes()
    idx = build_file_index(img)
    for p, e in idx.items():
        if p.upper().endswith("PROG_3.BIN"):
            return extract_file_data(img, e.extent, e.size)
    pytest.skip("PROG_3.BIN not found in build")


def test_item_use_glue_dict_is_apostrophe_s():
    """Fast guard on the patch dict (no build needed)."""
    from prog3_item_use_glue import PROG3_ITEM_USE_GLUE
    runs = dict(PROG3_ITEM_USE_GLUE["LANG/PROG_3.BIN"])
    for off in ITEM_USE_GLUE_OFFSETS:
        assert runs[off] == bytes([APOSTROPHE_S_TILE]), (
            f"item-use glue 0x{off:X} must target tile 0x{APOSTROPHE_S_TILE:02X} "
            f"('s), got {runs[off]!r}")


def test_apostrophe_s_tile_44_has_a_glyph():
    """The 0x2C immediate indexes tile 44 — it must carry the 's glyph in the
    generated font (absolute-glyph-index rule)."""
    jp = PROJECT / "data" / "jp" / "font_jp.bin"
    if not jp.exists():
        pytest.skip("data/jp/font_jp.bin not present")
    from font_tools import generate_english_font
    font = generate_english_font(jp.read_bytes())
    ink = sum(bin(b).count("1") for b in font[44 * 32:45 * 32])
    assert ink > 8, f"tile 44 ('s) has too little ink ({ink}) — would render blank"


def test_built_item_use_glue_is_apostrophe_s():
    p3 = _prog3_from_build()
    for off in ITEM_USE_GLUE_OFFSETS:
        assert p3[off] == APOSTROPHE_S_TILE, (
            f"PROG_3 0x{off:X} must be 0x{APOSTROPHE_S_TILE:02X} ('s), "
            f"got 0x{p3[off]:02X}")


def test_jp_baseline_glue_is_no_particle():
    """Provenance lock: the JP baseline at these sites is の (0x5C)."""
    jpdir = os.environ.get("LANG3_JP_DIR")
    if not jpdir:
        pytest.skip("LANG3_JP_DIR not set")
    import glob
    from iso_tools import build_file_index, extract_file_data
    t01 = [p for p in glob.glob(os.path.join(jpdir, "*.bin"))
           if "Track 01" in p or "Track01" in p]
    if not t01:
        pytest.skip("JP Track 01 not found")
    img = Path(t01[0]).read_bytes()
    idx = build_file_index(img)
    p3 = None
    for p, e in idx.items():
        if p.upper().endswith("PROG_3.BIN"):
            p3 = extract_file_data(img, e.extent, e.size)
    assert p3 is not None
    for off in ITEM_USE_GLUE_OFFSETS:
        assert p3[off] == JP_GLUE, f"JP 0x{off:X} expected の (0x5C)"
