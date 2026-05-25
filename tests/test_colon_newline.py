#!/usr/bin/env python3
"""
test_colon_newline.py — regression test for the v0.6 nameplate
`:` → newline engine patch on `patches/prog_3.bin`.

Locks the specific bytes that implement the colon-newline transform.
If a future edit reverts the patch (e.g., a rebuild of prog_3.bin from
a stale source, or an accidental hex-edit), this test fails.

Patch summary (see archive/docs/20260511_colon_phase7_composer_found.md
for the full investigation):

- Composer function entry at runtime 0x0607F364 (file_off 0x2CB64)
  allocates a 4-byte stack local and writes the colon tile-code into
  it via `mov.w R0, @R14` at 0x0607F37E.
- The byte being written comes from `mov #<imm>, R0` at 0x0607F376.
- Original immediate was `0x01` (= tile 1 = `:` glyph after EN font
  remap from JP `「`). The patch changes the immediate to `0xFC`,
  which `mov` sign-extends to `0xFFFFFFFC`, so the `mov.w` writes
  `0xFFFC` — a value the downstream layout/dispatcher interprets as
  a newline / Y-advance control code, dropping the dialog text to
  the next line.

Single-byte diff vs. JP baseline:
  prog_3.bin[0x2CB77] : 0x01 → 0xFC
"""

import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROG_3 = PROJECT_DIR / 'patches' / 'prog_3.bin'

# Composer function — colon-source writer (runtime 0x0607F364 = prog_3 file_off 0x2CB64)
COMPOSER_ENTRY_OFFSET = 0x2CB64

# Expected prologue bytes (push r8..r14, push pr, alloc 4-byte local, mov r15,r14)
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

# Patched colon-immediate: E0FC = `mov #-4, R0` (was E001 = `mov #1, R0` in baseline)
PATCHED_COLON_IMM_OFFSET = 0x2CB76
PATCHED_COLON_IMM_BYTES = bytes.fromhex('E0FC')

# The mov.w R0, @R14 that actually writes the colon byte to the local —
# this instruction must remain unchanged, otherwise the patch site is gone.
COLON_WRITE_INSTRUCTION_OFFSET = 0x2CB7E
COLON_WRITE_INSTRUCTION_BYTES = bytes.fromhex('2E01')


class TestColonNewlinePatch(unittest.TestCase):
    """Lock the bytes that implement v0.6 nameplate `:` → newline."""

    @classmethod
    def setUpClass(cls):
        cls.data = PROG_3.read_bytes()

    def test_prog_3_size_unchanged(self):
        """patches/prog_3.bin must keep its baseline size."""
        self.assertEqual(len(self.data), 219772)

    def test_composer_prologue_intact(self):
        """
        The composer function entry at file_off 0x2CB64 must match the
        expected SH-2 prologue. If the function shifts (e.g., someone
        rebuilt prog_3.bin from a different source), the colon-immediate
        offset is no longer valid.
        """
        end = COMPOSER_ENTRY_OFFSET + len(EXPECTED_PROLOGUE)
        actual = self.data[COMPOSER_ENTRY_OFFSET:end]
        self.assertEqual(
            actual, EXPECTED_PROLOGUE,
            f"Composer prologue at 0x{COMPOSER_ENTRY_OFFSET:X} drifted — "
            f"colon-immediate offset 0x{PATCHED_COLON_IMM_OFFSET:X} may no "
            f"longer point at the right instruction. Expected "
            f"{EXPECTED_PROLOGUE.hex()}, got {actual.hex()}."
        )

    def test_colon_immediate_is_FFFC_not_0001(self):
        """
        The colon immediate at file_off 0x2CB76 must be E0FC (mov #-4, R0)
        so that the subsequent mov.w writes 0xFFFC (newline control code).

        If this byte reverts to E001 (mov #1, R0) the nameplate colon
        re-appears and the dialog goes back to inline-with-name.
        If it becomes E000 (mov #0, R0) the colon is blanked but the
        newline is lost — Part 1 only, not Part 2.
        """
        end = PATCHED_COLON_IMM_OFFSET + 2
        actual = self.data[PATCHED_COLON_IMM_OFFSET:end]
        self.assertEqual(
            actual, PATCHED_COLON_IMM_BYTES,
            f"Colon immediate at 0x{PATCHED_COLON_IMM_OFFSET:X} expected "
            f"{PATCHED_COLON_IMM_BYTES.hex()} (E0FC, mov #-4, R0 → R0=0xFFFFFFFC "
            f"→ mov.w writes 0xFFFC = newline control code), "
            f"got {actual.hex()}. v0.6 colon-newline patch is reverted or "
            f"corrupted."
        )

    def test_colon_write_instruction_intact(self):
        """
        The actual write `mov.w R0, @R14` at file_off 0x2CB7E must stay.
        Without this instruction the colon-immediate is loaded but never
        stored, so neither tile 1 nor newline reaches the layout source.
        """
        end = COLON_WRITE_INSTRUCTION_OFFSET + 2
        actual = self.data[COLON_WRITE_INSTRUCTION_OFFSET:end]
        self.assertEqual(
            actual, COLON_WRITE_INSTRUCTION_BYTES,
            f"`mov.w R0, @R14` at 0x{COLON_WRITE_INSTRUCTION_OFFSET:X} "
            f"expected {COLON_WRITE_INSTRUCTION_BYTES.hex()} (2E01), "
            f"got {actual.hex()}. The colon-source write is gone, patch "
            f"is non-functional even if the immediate is correct."
        )

    def test_patch_does_not_break_alignment(self):
        """
        SH-2 instructions are 16-bit aligned. All three locked addresses
        must be 2-byte aligned, otherwise the disassembly framing is wrong
        and the patch is in the middle of an unrelated instruction.
        """
        for label, off in [
            ('composer entry',     COMPOSER_ENTRY_OFFSET),
            ('colon immediate',    PATCHED_COLON_IMM_OFFSET),
            ('colon write instr',  COLON_WRITE_INSTRUCTION_OFFSET),
        ]:
            self.assertEqual(
                off & 1, 0,
                f"{label} offset 0x{off:X} is not 2-byte aligned"
            )


if __name__ == '__main__':
    unittest.main()
