#!/usr/bin/env python3
"""
test_d00.py - TDD tests for D00.DAT parsing and rebuilding.

Verifies:
1. Parser correctly identifies section count and entry counts
2. Round-trip: parse -> rebuild produces identical text areas
3. In-place patching preserves D00.DAT structure
4. Text encoding produces valid tile codes
5. Entry count matching between JP and EN scripts
"""

import struct
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from d00_tools import (
    parse_d00, rebuild_d00, build_text_area, patch_d00_inplace,
    parse_script_file, encode_text_to_entry, insert_translations,
    OFFSET_TABLE_SENTINEL
)
from font_tools import CHAR_TILE_MAP, TILE_CHAR_MAP

JP_D00 = PROJECT_DIR / 'build' / 'd00_jp.dat'
SCRIPTS_DIR = PROJECT_DIR / 'scripts' / 'en'


class TestD00Parsing(unittest.TestCase):
    """Test D00.DAT parsing correctness."""

    @classmethod
    def setUpClass(cls):
        cls.d00 = JP_D00.read_bytes()
        cls.sections = parse_d00(cls.d00)

    def test_section_count(self):
        self.assertEqual(len(self.sections), 125)

    def test_all_entries_are_word_aligned(self):
        """Every text entry should have even byte length (2-byte tile codes)."""
        for sec in self.sections:
            for j, entry in enumerate(sec.entries):
                self.assertEqual(len(entry) % 2, 0,
                                 f"Section {sec.index} entry {j} has odd length {len(entry)}")

    def test_no_empty_entries(self):
        """No entry should be empty (0 bytes)."""
        for sec in self.sections:
            for j, entry in enumerate(sec.entries):
                self.assertGreater(len(entry), 0,
                                   f"Section {sec.index} entry {j} is empty")

    def test_entry_offsets_are_monotonic(self):
        """Entry offsets should be strictly increasing."""
        for sec in self.sections:
            ta = sec.text_area_offset
            offsets = []
            for j in range(sec.entry_count):
                off = struct.unpack_from('>H', self.d00, ta + 6 + j * 2)[0]
                offsets.append(off)
            for j in range(1, len(offsets)):
                self.assertGreater(offsets[j], offsets[j-1],
                                   f"Section {sec.index}: offset[{j}]={offsets[j]} "
                                   f"<= offset[{j-1}]={offsets[j-1]}")

    def test_sentinel_is_always_164(self):
        """The sentinel value after entry offsets is always 0x00A4."""
        for sec in self.sections:
            ta = sec.text_area_offset
            raw_count = (sec.offset_table_size - 4) // 2
            sentinel_off = ta + 6 + (raw_count - 1) * 2
            sentinel = struct.unpack_from('>H', self.d00, sentinel_off)[0]
            self.assertEqual(sentinel, OFFSET_TABLE_SENTINEL,
                             f"Section {sec.index}: sentinel=0x{sentinel:04X}")


class TestD00RoundTrip(unittest.TestCase):
    """Test that parse -> rebuild produces identical data."""

    @classmethod
    def setUpClass(cls):
        cls.d00 = JP_D00.read_bytes()
        cls.sections = parse_d00(cls.d00)
        cls.rebuilt = rebuild_d00(cls.sections)

    def test_rebuilt_size_matches(self):
        self.assertEqual(len(self.rebuilt), len(self.d00))

    def test_all_text_areas_match(self):
        """Every section's text area should be identical after round-trip."""
        for i, sec in enumerate(self.sections):
            orig_ta = sec.text_area_offset
            orig_ts = sec.text_size
            orig_text = self.d00[orig_ta:orig_ta + orig_ts]

            off = 4 + i * 8
            rebuilt_sector = struct.unpack_from('>I', self.rebuilt, off)[0]
            rebuilt_start = rebuilt_sector * 2048
            rebuilt_tbo = struct.unpack_from('>I', self.rebuilt, rebuilt_start)[0]
            rebuilt_tar = struct.unpack_from(
                '>I', self.rebuilt, rebuilt_start + rebuilt_tbo + 0x40)[0]
            rebuilt_ta = rebuilt_start + rebuilt_tbo + rebuilt_tar
            rebuilt_ts = struct.unpack_from('>I', self.rebuilt, rebuilt_ta)[0]
            rebuilt_text = self.rebuilt[rebuilt_ta:rebuilt_ta + rebuilt_ts]

            self.assertEqual(orig_text, rebuilt_text,
                             f"Section {i}: text area mismatch "
                             f"(orig={len(orig_text)}, rebuilt={len(rebuilt_text)})")


class TestTextEncoding(unittest.TestCase):
    """Test English text encoding to tile codes."""

    def test_basic_text(self):
        encoded = encode_text_to_entry("Hello", CHAR_TILE_MAP)
        # H=0x0018, e=0x0031, l=0x0038, l=0x0038, o=0x003B
        self.assertEqual(len(encoded), 10)  # 5 chars * 2 bytes
        codes = [struct.unpack_from('>H', encoded, i)[0] for i in range(0, 10, 2)]
        self.assertEqual(codes, [
            CHAR_TILE_MAP['H'],
            CHAR_TILE_MAP['e'],
            CHAR_TILE_MAP['l'],
            CHAR_TILE_MAP['l'],
            CHAR_TILE_MAP['o'],
        ])

    def test_control_codes_preserved(self):
        encoded = encode_text_to_entry("Hi<$FFFE>", CHAR_TILE_MAP)
        codes = [struct.unpack_from('>H', encoded, i)[0]
                 for i in range(0, len(encoded), 2)]
        self.assertIn(0xFFFE, codes)

    def test_name_variable(self):
        encoded = encode_text_to_entry("[Diehardt's name]!", CHAR_TILE_MAP)
        codes = [struct.unpack_from('>H', encoded, i)[0]
                 for i in range(0, len(encoded), 2)]
        self.assertIn(0xF600, codes)
        self.assertIn(0x0000, codes)

    def test_space_is_tile_0(self):
        encoded = encode_text_to_entry("A B", CHAR_TILE_MAP)
        codes = [struct.unpack_from('>H', encoded, i)[0]
                 for i in range(0, len(encoded), 2)]
        self.assertEqual(codes[1], 0x0000)  # space = tile 0


class TestScriptParsing(unittest.TestCase):
    """Test EN script file parsing."""

    def test_scen001_entry_count(self):
        """scen001E.txt should have entries close to JP count."""
        d00 = JP_D00.read_bytes()
        sections = parse_d00(d00)
        jp_count = sections[0].entry_count

        entries = parse_script_file(SCRIPTS_DIR / 'scen001E.txt')
        # EN count should be within reasonable range of JP count
        # (some padding will be needed for short scripts)
        self.assertGreater(len(entries), 0)
        self.assertLessEqual(abs(len(entries) - jp_count), jp_count * 0.2,
                             f"EN={len(entries)} vs JP={jp_count}")

    def test_all_scripts_parseable(self):
        """All EN scripts should parse without errors."""
        for f in sorted(SCRIPTS_DIR.glob('scen*E.txt')):
            entries = parse_script_file(f)
            self.assertGreater(len(entries), 0, f"{f.name} parsed 0 entries")


class TestInPlacePatching(unittest.TestCase):
    """Test D00.DAT in-place patching."""

    @classmethod
    def setUpClass(cls):
        cls.d00 = JP_D00.read_bytes()
        cls.sections = parse_d00(cls.d00)

    def test_inplace_patch_preserves_size(self):
        """In-place patching should not change D00.DAT size."""
        # Create a small text area that fits
        small_entries = [b'\xff\xff'] * self.sections[0].entry_count
        new_ta = build_text_area(small_entries)
        patched, count, skipped = patch_d00_inplace(
            self.d00, self.sections, {0: new_ta})
        self.assertEqual(len(patched), len(self.d00))
        self.assertEqual(count, 1)

    def test_inplace_skips_overflow(self):
        """In-place patching should skip sections where text doesn't fit."""
        # Create a text area larger than the allocated space (sector gap)
        # Allocated space for section 0 = next section's byte_offset - section 0's byte_offset
        sec = self.sections[0]
        if len(self.sections) > 1:
            allocated_end = self.sections[1].byte_offset
        else:
            allocated_end = len(self.d00)
        available = allocated_end - sec.text_area_offset
        oversized = b'\x00' * (available + 1000)
        patched, count, skipped = patch_d00_inplace(
            self.d00, self.sections, {0: oversized})
        self.assertEqual(skipped, 1)
        self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
