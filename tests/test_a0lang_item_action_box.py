#!/usr/bin/env python3
"""
test_a0lang_item_action_box.py — guard for the item-action confirmation box fix.

The field item-action box ("[item] を 使用/装備 します") is assembled by the
A0LANG builder FUN_0601299c in FIXED Japanese SOV slots:

    [item name] + を(tile 0x7C, hardcoded `mov #0x7C` @ A0LANG file 0x49CA)
                + [fntsys1 rec14 使用 / rec13 装備]
                + [fntsys1 rec96 します]   (piece-B index = const 0xC0 @ file 0x4A75)

With our repainted font, tile 0x7C draws as the "cp" bigram, and fntsys1
rec96 (JP します) is "Equipment" in our EN fntsys1 — so the box rendered the
garbage "Magic Herb cp Use Equipment" (RE + RAM dumps 2026-06-13).

rec96 CANNOT be blanked: it is also the X=12 centre piece of the equip-title
screen (test_prog4_equip_title). So the fix is two A0LANG byte patches and
touches NO fntsys record:

  1. を glue tile 0x7C -> 0x01  (tile 0x01 = ": " colon + half-width space).
     SIGN-SAFE: SH-2 `mov #imm8` sign-extends, so the separator MUST be a low
     (<= 0x7F) tile. *** tile 0x01 = ": " is now LOAD-BEARING for this
     `mov #imm`; the FONT refactor must keep a ": " glyph at a low index. ***
  2. piece-B index 0xC0 (rec96) -> 0xF8 (rec124, an empty fntsys1 record), so
     the builder appends nothing after Use/Equip. Constant-pool value, not a
     `mov #imm` (no sign-ext rule). Only the use/equip boxes read this index.

Result: "Magic Herb: Use" / "Long Sword: Equip".

Red state (pre-fix): the module is absent; in-game both slots are wrong.
"""

import os
import struct
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from iso_tools import build_file_index, extract_file_data            # noqa: E402
from fnt_sys_tools import parse_fnt_sys, encode_fntsys               # noqa: E402
from a0lang_item_action_box import (                                 # noqa: E402
    A0LANG_ITEM_ACTION_BOX as BOX,
    A0LANG_ITEM_ACTION_BOX_JP_BASELINE as JP_BASE,
)

JP_DIR = os.environ.get('LANG3_JP_DIR')
A0LANG_PATH = 'A0LANG.BIN'

WO_GLUE_OFF = 0x000049CB     # を glue immediate (operand of `mov #0x7C,r0`)
SEP_TILE = 0x01              # ": " colon + half-width space; replaces を (0x7C)
PIECEB_OFF = 0x00004A75      # low byte of DAT_06012a74 (piece-B index const)
PIECEB_VAL = 0xF8            # rec124 byte-offset (was 0xC0 = rec96)
EMPTY_REC = PIECEB_VAL // 2  # 0x7C = 124
NUM_TILES = 1691


def effective_tile(imm8):
    """Tile code an SH-2 `mov #imm8; mov.w` actually writes (sign-extended)."""
    v = imm8 if imm8 < 0x80 else (imm8 | 0xFFFFFF00)
    return v & 0xFFFF


def _en_fntsys1():
    jp = (PROJECT_DIR / 'cache' / 'fnt_sys_jp.bin').read_bytes()
    en = parse_fnt_sys(encode_fntsys(jp, PROJECT_DIR / 'scripts' / 'en'))
    return en.pairs[0].records          # fntsys1 = pair 0


class TestPatchDeclaration(unittest.TestCase):
    """Lock the module — runs without the JP disc."""

    def test_touches_only_a0lang_two_bytes(self):
        self.assertEqual(list(BOX), [A0LANG_PATH])
        edits = dict(BOX[A0LANG_PATH])
        self.assertEqual(len(edits), 2, "を glue tile + piece-B index")
        self.assertEqual(edits[WO_GLUE_OFF], bytes([SEP_TILE]), "を -> 0x01 ': '")
        self.assertEqual(edits[PIECEB_OFF], bytes([PIECEB_VAL]), "rec96 -> rec124 (empty)")

    def test_separator_is_sign_safe_and_renderable(self):
        """0x01 must survive sign-extension into a real tile (the 0xD4 trap)."""
        self.assertLessEqual(SEP_TILE, 0x7F, "mov #imm sign-extends; need <= 0x7F")
        self.assertEqual(effective_tile(SEP_TILE), SEP_TILE)
        self.assertLess(effective_tile(SEP_TILE), NUM_TILES)

    def test_separator_glyph_is_colon_space(self):
        """Tile 0x01 must be ': ' — load-bearing; INVARIANT for the font refactor."""
        import font_tools as ft
        self.assertEqual(ft.CHAR_TILE_MAP.get(':'), SEP_TILE,
                         "tile 0x01 must map ':' — keep it at a low (<=0x7F) slot")

    def test_not_in_byte_overlays(self):
        from byte_overlays import BYTE_OVERLAYS
        self.assertNotIn(A0LANG_PATH, BYTE_OVERLAYS,
                         "A0LANG ships JP + our modules; must not leak here")


class TestSuffixRepoint(unittest.TestCase):
    """The piece-B repoint must land on an EMPTY record, and must NOT disturb
    rec96 (shared with the equip-title screen)."""

    def test_repoint_target_record_is_empty(self):
        recs = _en_fntsys1()
        self.assertEqual(recs[EMPTY_REC], b'\xff\xff',
                         f"piece-B repoint target fntsys1 rec{EMPTY_REC} must stay "
                         "empty; filling it re-introduces a bad suffix in the box")

    def test_rec96_left_intact_for_equip_title(self):
        """rec96 ('Equipment') must NOT be blanked — the equip-title needs it."""
        recs = _en_fntsys1()
        self.assertNotEqual(recs[96], b'\xff\xff',
                            "rec96 is the equip-title X=12 centre piece; do not blank it")

    def test_rec14_use_intact(self):
        recs = _en_fntsys1()
        tiles = [struct.unpack_from('>H', recs[14], i)[0]
                 for i in range(0, len(recs[14]) - 1, 2)]
        self.assertTrue(tiles and tiles[0] != 0xFFFF, "rec14 must be non-empty ('Use')")
        self.assertNotIn(0x007C, tiles, "no stray を/cp in the action label")


@unittest.skipUnless(JP_DIR, "LANG3_JP_DIR not set — skipping JP-baseline checks")
class TestAgainstJPBaseline(unittest.TestCase):
    """Truth-lock the patch sites against the live JP A0LANG.BIN."""

    @classmethod
    def setUpClass(cls):
        jp = Path(JP_DIR)
        cands = list(jp.glob('*rack*01*.bin')) or list(jp.glob('*.bin'))
        image = bytearray(cands[0].read_bytes())
        idx = build_file_index(image)
        e = idx[A0LANG_PATH]
        cls.jp = extract_file_data(image, e.extent, e.size)

    def test_jp_baseline_bytes_match(self):
        for off, val in JP_BASE.items():
            self.assertEqual(self.jp[off], val,
                             f"JP A0LANG[0x{off:X}] = {self.jp[off]:#x}, expected {val:#x}")
        self.assertEqual(JP_BASE[WO_GLUE_OFF], 0x7C, "JP glue tile is を (0x7C)")
        self.assertEqual(JP_BASE[PIECEB_OFF], 0xC0, "JP piece-B index = rec96 (0xC0)")

    def test_patch_yields_separator_and_repoint(self):
        patched = bytearray(self.jp)
        for off, chunk in BOX[A0LANG_PATH]:
            patched[off:off + len(chunk)] = chunk
        self.assertEqual(patched[WO_GLUE_OFF], SEP_TILE)
        self.assertEqual(patched[PIECEB_OFF], PIECEB_VAL)


if __name__ == '__main__':
    unittest.main()
