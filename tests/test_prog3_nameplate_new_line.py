#!/usr/bin/env python3
"""
test_prog3_nameplate_new_line.py — regression test for our nameplate
newline engine patch (tools/prog3_nameplate_new_line.py).

We patch the **JP** LANG/PROG_3.BIN — not 0.2 patch. The balloon composer emits
`<$FFFC>` (newline) instead of `<$0001>` (the `:` tile) after the nameplate,
turning `[NAMEPLATE]<$0001>[DIALOGO]` (inline) into
`[NAMEPLATE]<$FFFC>[DIALOGO]` (name on line 1, dialogue on line 2).

Verified against the LIVE JP baseline (LANG3_JP_DIR), not a stored blob —
the old archive/v02_baseline/prog_3.bin was deleted in the disembark cleanup.

Single-byte diff vs JP baseline:  prog_3.bin[0x2CB77] : 0x01 -> 0xFC
"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from iso_tools import build_file_index, extract_file_data            # noqa: E402
from prog3_nameplate_new_line import PROG3_NAMEPLATE_NEW_LINE        # noqa: E402

JP_DIR = os.environ.get('LANG3_JP_DIR')

# --- patch-site facts (file offsets in LANG/PROG_3.BIN) --------------------
COMPOSER_ENTRY_OFFSET = 0x2CB64
EXPECTED_PROLOGUE = bytes.fromhex(
    '2F86'  # push r8
    '2F96'  # push r9
    '2FA6'  # push r10
    '2FB6'  # push r11
    '2FE6'  # push r14
    '4F22'  # sts.l pr, @-r15
    '7FFC'  # add #-4, r15  (allocate 4-byte local)
    '6EF3'  # mov r15, r14   (r14 = frame ptr)
    '6B53'  # mov r5, r11    (save caller R5)
)
IMM_OFFSET = 0x2CB76
JP_IMM = bytes.fromhex('E001')          # mov #1, R0   (':' tile, JP baseline)
PATCHED_IMM = bytes.fromhex('E0FC')     # mov #-4, R0  -> mov.w writes 0xFFFC
WRITE_OFFSET = 0x2CB7E
WRITE_BYTES = bytes.fromhex('2E01')     # mov.w R0, @R14  (must stay)
PATCH_OFFSET = 0x2CB77
PATCH_BYTE = b'\xfc'
PROG_3_PATH = 'LANG/PROG_3.BIN'
PROG_3_SIZE = 219772


def _load_jp_prog3() -> bytes:
    jp = Path(JP_DIR)
    cands = list(jp.glob('*rack*01*.bin')) or list(jp.glob('*.bin'))
    image = bytearray(cands[0].read_bytes())
    idx = build_file_index(image)
    e = idx[PROG_3_PATH]
    return extract_file_data(image, e.extent, e.size)


class TestPatchDeclaration(unittest.TestCase):
    """Lock the module — runs without the JP disc."""

    def test_is_a_single_patch(self):
        self.assertEqual(list(PROG3_NAMEPLATE_NEW_LINE), [PROG_3_PATH],
                         "module must touch exactly LANG/PROG_3.BIN")
        edits = PROG3_NAMEPLATE_NEW_LINE[PROG_3_PATH]
        self.assertEqual(len(edits), 1, "must be a single byte patch")
        off, chunk = edits[0]
        self.assertEqual(off, PATCH_OFFSET)
        self.assertEqual(chunk, PATCH_BYTE)

    def test_not_in_byte_overlays(self):
        """The patch is ours — it must NOT live in the opaque byte_overlays.
        PROG_3 is fully disembarked (2026-06-14), so it is not even a key."""
        from byte_overlays import BYTE_OVERLAYS
        offsets = {off for off, _ in BYTE_OVERLAYS.get("LANG/PROG_3.BIN", ())}
        self.assertNotIn(PATCH_OFFSET, offsets,
                         "nameplate newline patch leaked back into byte_overlays")

    def test_offsets_are_aligned(self):
        for off in (COMPOSER_ENTRY_OFFSET, IMM_OFFSET, WRITE_OFFSET):
            self.assertEqual(off & 1, 0, f"offset 0x{off:X} not 2-byte aligned")


@unittest.skipUnless(JP_DIR, "LANG3_JP_DIR not set — skipping JP-baseline checks")
class TestAgainstJPBaseline(unittest.TestCase):
    """Verify the patch site against the live JP PROG_3.BIN."""

    @classmethod
    def setUpClass(cls):
        cls.jp = _load_jp_prog3()

    def test_jp_size(self):
        self.assertEqual(len(self.jp), PROG_3_SIZE)

    def test_jp_composer_prologue_intact(self):
        end = COMPOSER_ENTRY_OFFSET + len(EXPECTED_PROLOGUE)
        self.assertEqual(self.jp[COMPOSER_ENTRY_OFFSET:end], EXPECTED_PROLOGUE,
                         "composer prologue drifted — patch offset may be wrong")

    def test_jp_baseline_is_colon_tile(self):
        """JP emits <$0001> (the ':' tile) — this is what we replace."""
        self.assertEqual(self.jp[IMM_OFFSET:IMM_OFFSET + 2], JP_IMM)
        self.assertEqual(self.jp[PATCH_OFFSET], 0x01)

    def test_jp_write_instruction_intact(self):
        self.assertEqual(self.jp[WRITE_OFFSET:WRITE_OFFSET + 2], WRITE_BYTES,
                         "mov.w R0,@R14 gone — patch site invalid")

    def test_patch_yields_fffc(self):
        """Applying our patch over JP turns E001 into E0FC (writes 0xFFFC)."""
        patched = bytearray(self.jp)
        for off, chunk in PROG3_NAMEPLATE_NEW_LINE[PROG_3_PATH]:
            patched[off:off + len(chunk)] = chunk
        self.assertEqual(patched[IMM_OFFSET:IMM_OFFSET + 2], PATCHED_IMM)


if __name__ == '__main__':
    unittest.main()
