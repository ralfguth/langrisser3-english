#!/usr/bin/env python3
"""test_a0lang_loadsave_title.py — regression test for the LOAD/SAVE-screen title
centring (tools/a0lang_loadsave_title.py). One JP A0LANG.BIN byte; verified
against the live JP baseline (LANG3_JP_DIR).

The patched node 0x06033218 is SHARED by both the LOAD and SAVE modes (Ghidra:
installers PC 0x060142EC and 0x06014AF0 both write node+0xC). Centring it once
centres both — but ONLY because both "LOAD" and "SAVE" are 4 half-width cells.
The shared-width guard pins that invariant: if either word stopped being 4 cells,
the single X=4 would no longer centre it.
"""

import os
import re
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from iso_tools import build_file_index, extract_file_data            # noqa: E402
from a0lang_loadsave_title import (                                  # noqa: E402
    A0LANG_LOADSAVE_TITLE as GEO,
    A0LANG_LOADSAVE_TITLE_JP_BASELINE as JP_BASE,
)

JP_DIR = os.environ.get('LANG3_JP_DIR')
A0LANG_PATH = 'A0LANG.BIN'
LOADSAVE_TITLE_X = 0x0002521C
EXPECTED = {LOADSAVE_TITLE_X: 0x04}
FNTSYS1 = PROJECT_DIR / 'scripts' / 'en' / 'fntsys1E.txt'


class TestPatchDeclaration(unittest.TestCase):
    def test_touches_only_a0lang_one_byte(self):
        self.assertEqual(list(GEO), [A0LANG_PATH])
        edits = GEO[A0LANG_PATH]
        self.assertEqual(len(edits), 1)
        self.assertEqual(len(edits[0][1]), 1)

    def test_baseline_and_value_tables_agree(self):
        offs = {off for off, _ in GEO[A0LANG_PATH]}
        self.assertEqual(offs, set(JP_BASE))
        self.assertEqual(offs, set(EXPECTED))

    def test_centres_four_cell_text(self):
        """node X 2 -> 4: a 4-cell word spans screen 18..22, centred in the
        14..26 title box (centre 20). JP was X=2 (zenkaku, 8 cells)."""
        self.assertEqual(JP_BASE[LOADSAVE_TITLE_X], 0x02)
        self.assertEqual(EXPECTED[LOADSAVE_TITLE_X], 0x04)

    def test_load_and_save_are_both_four_cells(self):
        """Shared node ⇒ the single X=4 only centres both modes while LOAD and
        SAVE are each 4 half-width cells. Pin that the EN fntsys carries both as
        4-char standalone records."""
        text = FNTSYS1.read_text(encoding='utf-8', errors='replace')
        for word in ('LOAD', 'SAVE'):
            self.assertRegex(
                text, rf'(?m)^{word}<\$FFFF>$',
                f"{word} is no longer a 4-char standalone record — shared X=4 "
                f"would mis-centre it")


@unittest.skipUnless(JP_DIR, "LANG3_JP_DIR not set — skipping JP-baseline check")
class TestAgainstJPBaseline(unittest.TestCase):
    def test_jp_baseline_byte_matches(self):
        jp = Path(JP_DIR)
        cands = list(jp.glob('*rack*01*.bin')) or list(jp.glob('*.bin'))
        image = bytearray(cands[0].read_bytes())
        idx = build_file_index(image)
        e = idx[A0LANG_PATH]
        data = extract_file_data(image, e.extent, e.size)
        for off, val in JP_BASE.items():
            self.assertEqual(data[off], val)


if __name__ == '__main__':
    unittest.main()
