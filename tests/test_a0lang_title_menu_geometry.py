#!/usr/bin/env python3
"""
test_a0lang_title_menu_geometry.py — regression test for the title
START/LOAD/OPTIONS box resize+centre (tools/a0lang_title_menu_geometry.py).

RED→GREEN history: the first cut of this branch patched the STATIC A0LANG
group struct at file 0x253C4 (+4 parent X, +8 box width). Instrumented Ymir
proved that struct is a DEAD DEFAULT — the title menu group at RAM 0x060333C4
is rebuilt by CODE at boot (the START/LOAD/OPTIONS installer near PC
0x06015D16). The setup code writes the live geometry with `mov #imm,r1` /
`mov.b r1,@(disp,group)` sequences:

    0x06015CD2  E10B  mov #0x0b,r1   ; 11   -> parent X  (file 0x07CD2/3)
    0x06015CDA  E112  mov #0x12,r1   ; 18   -> parent Y
    0x06015CE2  E113  mov #0x13,r1   ; 19   -> box WIDTH (file 0x07CE2/3)
    0x06015CE8  E108  mov #0x08,r1   ; 8    -> box HEIGHT

So the EFFECTIVE bytes are the 8-bit immediates inside those `mov` opcodes,
NOT the struct data. (The JP code already writes width 19, not the 22 in the
static struct — the old "JP width 22" reading was the dead default.)

This test pins the CODE immediates: JP baseline 0x0B/0x13, patched 0x0D/0x0E,
verified against the LIVE JP A0LANG.BIN (LANG3_JP_DIR), and guards that we are
editing the low byte of a `mov #imm,r1` (0xE1) opcode, not arbitrary data.

Path B (the no-save START/OPTIONS layout near PC 0x06015D5E) shares one
immediate for parent Y AND width and is intentionally left to a follow-up.
"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from iso_tools import build_file_index, extract_file_data            # noqa: E402
from a0lang_title_menu_geometry import (                            # noqa: E402
    A0LANG_TITLE_MENU_GEOMETRY as GEO,
    A0LANG_TITLE_MENU_GEOMETRY_JP_BASELINE as JP_BASE,
)

JP_DIR = os.environ.get('LANG3_JP_DIR')
A0LANG_PATH = 'A0LANG.BIN'
A0LANG_SIZE = 158288

# Path-A setup-code immediates (file offsets = low byte of the mov #imm,r1 word)
MENU_PARENT_X = 0x00007CD3   # mov #0x0b,r1 @ 0x06015CD2  -> group +4 parent X
MENU_WIDTH = 0x00007CE3      # mov #0x13,r1 @ 0x06015CE2  -> group +8 box width
# the byte BEFORE each immediate must be 0xE1 (opcode of `mov #imm,r1`)
MENU_PARENT_X_OPCODE = MENU_PARENT_X - 1
MENU_WIDTH_OPCODE = MENU_WIDTH - 1

EXPECTED_GEOMETRY = {MENU_PARENT_X: 0x0E, MENU_WIDTH: 0x0C}


class TestPatchDeclaration(unittest.TestCase):
    """Lock the module — runs without the JP disc."""

    def test_touches_only_a0lang(self):
        self.assertEqual(list(GEO), [A0LANG_PATH])

    def test_two_single_byte_edits(self):
        edits = GEO[A0LANG_PATH]
        self.assertEqual(len(edits), 2)
        for off, chunk in edits:
            self.assertEqual(len(chunk), 1, f"edit at 0x{off:X} not a single byte")

    def test_patches_the_code_immediates_not_the_dead_struct(self):
        """The effective site is the setup-code immediate, never the static
        struct (0x253C8/0x253CC = dead default that the code overwrites)."""
        offs = {off for off, _ in GEO[A0LANG_PATH]}
        self.assertEqual(offs, {MENU_PARENT_X, MENU_WIDTH})
        self.assertNotIn(0x000253C8, offs)
        self.assertNotIn(0x000253CC, offs)

    def test_baseline_and_value_tables_agree(self):
        offs = {off for off, _ in GEO[A0LANG_PATH]}
        self.assertEqual(offs, set(JP_BASE))
        self.assertEqual(offs, set(EXPECTED_GEOMETRY))

    def test_box_extent_eye_tuned(self):
        """Eye-tuned by playtest (2026-06-28): box left edge kept at cell 14 (the
        approved position — user: "don't move the box"), right edge trimmed one
        cell (8px) from 27 to 26. Box spans cells 14..26; its centre lands on
        screen centre 20."""
        px = EXPECTED_GEOMETRY[MENU_PARENT_X]
        w = EXPECTED_GEOMETRY[MENU_WIDTH]
        self.assertEqual(px, 14)                 # left edge unchanged ("don't move")
        self.assertEqual(px + w, 26)             # right edge trimmed to 26 (was 27)
        self.assertEqual(px * 2 + w, 40)         # centre lands on cell 20

    def test_width_reduced_from_jp_nineteen(self):
        """JP setup code writes width 19; we narrow to 12 (eye-tuned)."""
        self.assertEqual(JP_BASE[MENU_WIDTH], 0x13)          # JP = 19
        self.assertEqual(EXPECTED_GEOMETRY[MENU_WIDTH], 0x0C)  # 12

    def test_not_in_byte_overlays(self):
        from byte_overlays import BYTE_OVERLAYS
        self.assertNotIn(A0LANG_PATH, BYTE_OVERLAYS)


@unittest.skipUnless(JP_DIR, "LANG3_JP_DIR not set — skipping JP-baseline checks")
class TestAgainstJPBaseline(unittest.TestCase):
    """Verify the patch sites against the live JP A0LANG.BIN."""

    @classmethod
    def setUpClass(cls):
        jp = Path(JP_DIR)
        cands = list(jp.glob('*rack*01*.bin')) or list(jp.glob('*.bin'))
        image = bytearray(cands[0].read_bytes())
        idx = build_file_index(image)
        e = idx[A0LANG_PATH]
        cls.jp = extract_file_data(image, e.extent, e.size)

    def test_jp_size(self):
        self.assertEqual(len(self.jp), A0LANG_SIZE)

    def test_jp_baseline_bytes_match(self):
        for off, val in JP_BASE.items():
            self.assertEqual(self.jp[off], val,
                             f"JP A0LANG[0x{off:X}] = {self.jp[off]:#x}, expected {val:#x}")

    def test_sites_are_mov_immediate_opcodes(self):
        """Guard that each patched byte is the immediate of a `mov #imm,r1`
        (high byte 0xE1) — i.e. we edit a real instruction, not stray data."""
        self.assertEqual(self.jp[MENU_PARENT_X_OPCODE], 0xE1,
                         "parent-X site is not a mov #imm,r1 opcode")
        self.assertEqual(self.jp[MENU_WIDTH_OPCODE], 0xE1,
                         "width site is not a mov #imm,r1 opcode")

    def test_dead_struct_default_still_present(self):
        """The static struct keeps its JP default (22) — we deliberately do NOT
        touch it, proving the fix moved to the code site."""
        self.assertEqual(self.jp[0x000253CC], 0x16)

    def test_patch_yields_expected_geometry(self):
        patched = bytearray(self.jp)
        for off, chunk in GEO[A0LANG_PATH]:
            patched[off:off + len(chunk)] = chunk
        for off, val in EXPECTED_GEOMETRY.items():
            self.assertEqual(patched[off], val)


if __name__ == '__main__':
    unittest.main()
