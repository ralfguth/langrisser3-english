#!/usr/bin/env python3
"""
test_a0lang_options_menu_geometry.py — regression test for our OPTIONS-screen
text geometry disembark (tools/a0lang_options_menu_geometry.py).

We patch the **JP** A0LANG.BIN — 17 tile-X (and one tile-Y) coordinates in the
OPTIONS (システム設定) display list, disembarked from 0.2 patch English Menus v0.2.
Verified against the LIVE JP baseline (LANG3_JP_DIR), not a stored blob.
"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from iso_tools import build_file_index, extract_file_data            # noqa: E402
from a0lang_options_menu_geometry import (                           # noqa: E402
    A0LANG_OPTIONS_MENU_GEOMETRY as GEO,
    A0LANG_OPTIONS_MENU_GEOMETRY_JP_BASELINE as JP_BASE,
)

JP_DIR = os.environ.get('LANG3_JP_DIR')
A0LANG_PATH = 'A0LANG.BIN'
A0LANG_SIZE = 158288

# expected post-patch (0.2 patch v0.2) value at each offset — OPTIONS value columns only
EXPECTED_GEOMETRY = {
    0x25488: 0x21, 0x254B8: 0x21, 0x254C8: 0x1B, 0x254D8: 0x21, 0x254E8: 0x1B,
    0x254F8: 0x21, 0x25508: 0x13, 0x25518: 0x19, 0x25528: 0x21, 0x25538: 0x13,
    0x25548: 0x21,
}

# The 6 A0LANG bytes 0.2 patch also changes that belong to OTHER menus (LOAD/SAVE) and
# must STAY at JP — our module must NOT touch them (they broke the LOAD box).
OTHER_MENU_OFFSETS = {0x2521C, 0x252B0, 0x25300, 0x25310, 0x25320, 0x253CC}


def _load_jp_a0lang() -> bytes:
    jp = Path(JP_DIR)
    cands = list(jp.glob('*rack*01*.bin')) or list(jp.glob('*.bin'))
    image = bytearray(cands[0].read_bytes())
    idx = build_file_index(image)
    e = idx[A0LANG_PATH]
    return extract_file_data(image, e.extent, e.size)


class TestPatchDeclaration(unittest.TestCase):
    """Lock the module — runs without the JP disc."""

    def test_touches_only_a0lang(self):
        self.assertEqual(list(GEO), [A0LANG_PATH],
                         "module must touch exactly A0LANG.BIN")

    def test_has_11_single_byte_edits(self):
        edits = GEO[A0LANG_PATH]
        self.assertEqual(len(edits), 11, "OPTIONS value columns only — 11 bytes")
        for off, chunk in edits:
            self.assertEqual(len(chunk), 1, f"edit at 0x{off:X} not a single byte")

    def test_baseline_and_value_tables_agree(self):
        offs_geo = {off for off, _ in GEO[A0LANG_PATH]}
        self.assertEqual(offs_geo, set(JP_BASE))
        self.assertEqual(offs_geo, set(EXPECTED_GEOMETRY))

    def test_does_not_touch_other_menus(self):
        """The 6 LOAD/SAVE bytes 0.2 patch also moves must NOT be in our module."""
        offs_geo = {off for off, _ in GEO[A0LANG_PATH]}
        self.assertEqual(offs_geo & OTHER_MENU_OFFSETS, set(),
                         "module leaked an other-menu byte that broke the LOAD box")

    def test_not_in_byte_overlays(self):
        """Ours — must not also live in byte_overlays BYTE_OVERLAYS (A0LANG ships JP)."""
        from byte_overlays import BYTE_OVERLAYS
        self.assertNotIn(A0LANG_PATH, BYTE_OVERLAYS,
                         "A0LANG leaked into byte_overlays; it must stay our module")


@unittest.skipUnless(JP_DIR, "LANG3_JP_DIR not set — skipping JP-baseline checks")
class TestAgainstJPBaseline(unittest.TestCase):
    """Verify the patch sites against the live JP A0LANG.BIN."""

    @classmethod
    def setUpClass(cls):
        cls.jp = _load_jp_a0lang()

    def test_jp_size(self):
        self.assertEqual(len(self.jp), A0LANG_SIZE)

    def test_jp_baseline_bytes_match(self):
        for off, val in JP_BASE.items():
            self.assertEqual(self.jp[off], val,
                             f"JP A0LANG[0x{off:X}] = {self.jp[off]:#x}, expected {val:#x}")

    def test_patch_yields_expected_geometry(self):
        patched = bytearray(self.jp)
        for off, chunk in GEO[A0LANG_PATH]:
            patched[off:off + len(chunk)] = chunk
        for off, val in EXPECTED_GEOMETRY.items():
            self.assertEqual(patched[off], val,
                             f"patched A0LANG[0x{off:X}] = {patched[off]:#x}, expected {val:#x}")


if __name__ == '__main__':
    unittest.main()
