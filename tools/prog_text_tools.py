"""prog_text_tools.py — text-content encoders for prog_*.bin overlays.

Caminho B of the 0.2 patch disembark cycle. Replaces the text portions of
tools/byte_overlays.py with script-driven encoders so we own the
translation semantically (not just the packaging).

Pattern:
  - A "slot table" enumerates (offset, slot_width, default_name) for each
    text record in a fixed-stride table inside a prog_*.bin.
  - A script file (scripts/en/<binary>_<table>E.txt) lists one name per
    line in slot order.
  - The encoder pads each name to slot_width with NULs and emits a
    list of (offset, padded_bytes) overlay entries.
  - build.py merges the encoded entries with the static byte_overlays
    dict before applying. Entries from the encoder OVERRIDE static
    entries at the same offset.

Current scope: PROG_3 magic-name table (0x33960 stride-0x14 ×54 slots).
Other text tables (prog_3 skill region 0x3314C, prog_4 magic-icon
table 0x7F80, etc.) follow the same pattern but need per-table slot
maps; they remain in byte_overlays.py until factored out individually.
"""

from __future__ import annotations

import struct
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# PROG_3 — magic-name table at 0x3394C..0x33D98 (stride 0x14, 54 slots)
# ---------------------------------------------------------------------------
# Each slot: 12 bytes ASCII name (null-padded) + 8 bytes metadata.
# Metadata bytes (cost, range, level, target flags etc) are byte-identical
# between JP and 0.2 patch and are NOT touched by this encoder — only the name
# region (offset .. offset+12) is written.
PROG3_MAGIC_TABLE_BASE = 0x3394C
PROG3_MAGIC_NAME_WIDTH = 12      # bytes per name slot before metadata
PROG3_MAGIC_STRIDE = 0x14        # total bytes per record (name + metadata)
PROG3_MAGIC_COUNT = 55           # Fire..Baldur (verified via byte audit)

# ---------------------------------------------------------------------------
# PROG_3 — skill-name table at 0x3314C..0x331B7 (9 command-label slots)
# ---------------------------------------------------------------------------
# This table is POINTER-INDEXED, not uniform stride. Slots 0-6 sit at
# base+index*0xC, but "Treatment"[7] and "Item"[8] are reached through
# DEDICATED pointers in PROG_3 (file 0x1DD5C / 0x1DD60 -> SH-2 0x060859A6 /
# 0x060859B0, load base 0x06052800). The JP baseline pointers read 0x060859A0 /
# 0x060859AC; encode_prog3_skill_pointers() (below) redirects them to
# 0x331A6 / 0x331B0 — DERIVED from this very table (load base +
# PROG3_SKILL_OFFSETS[7/8]), so the redirect can never drift from the names it
# targets. (Disembarked 2026-06-14 from the opaque byte_overlays.PROG_3_OVERLAY
# 0x1DD5F patch.) The names are read NUL-terminated, so each name needs a NUL
# inside its slot — "Double Magic" (exactly 12 chars) cannot live in a 0xC slot
# with a terminator, which is why the table is non-uniform: slot 6 is 0x12 wide
# and slot 7 is 0xA, exactly reproducing the proven 0.2 patch v0.2 layout.
#
# Writing names at uniform 0xC put "Treatment" at 0x331A0 while its pointer reads
# 0x331A6 -> the in-game "ent" bug. We therefore place each name at its
# pointer-defined offset, NUL-terminated and NUL-padded to fill its slot (which
# also gives "Double Magic" its terminator in the gap before 0x331A6).
# Verified end-to-end by tests/test_prog3_skill.py.
PROG3_SKILL_OFFSETS = [
    0x3314C, 0x33158, 0x33164, 0x33170, 0x3317C,   # slots 0-4 (stride 0xC)
    0x33188, 0x33194,                              # slots 5-6 (stride 0xC)
    0x331A6,                                       # slot 7 "Treatment" (pointer)
    0x331B0,                                       # slot 8 "Item"      (pointer)
]
PROG3_SKILL_REGION_END = 0x331B8  # metadata (cost/level/icon) begins here
PROG3_SKILL_COUNT = len(PROG3_SKILL_OFFSETS)   # 9: Kiai Shout..Item

PROG3_LOAD_BASE = 0x06052800       # SH-2 runtime addr = file offset + this
# File offsets of the dedicated BE32 pointers for the slots whose name does NOT
# sit at the uniform base+index*0xC position (slots 7 "Treatment" and 8 "Item").
PROG3_SKILL_PTR_OFFSETS = {7: 0x1DD5C, 8: 0x1DD60}


def _read_script_lines(path: Path, expected_count: int) -> list[str]:
    """Read a names script: one entry per non-blank line."""
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    if len(lines) != expected_count:
        raise ValueError(
            f"{path.name}: expected {expected_count} lines, got {len(lines)}"
        )
    return lines


def _pack_ascii_slot(name: str, slot_width: int) -> bytes:
    """Encode `name` as ASCII, null-pad to `slot_width`. Truncate if too long."""
    raw = name.encode("ascii", errors="strict")
    if len(raw) > slot_width:
        raise ValueError(f"name {name!r} = {len(raw)} bytes > slot {slot_width}")
    return raw + b"\x00" * (slot_width - len(raw))


def encode_prog3_magic_table(
    script_path: Path = PROJ / "scripts" / "en" / "prog3_magicE.txt",
) -> list[tuple[int, bytes]]:
    """Return overlay entries (offset, bytes) for the prog_3 magic-name table.

    Each entry writes a 12-byte ASCII name slot at offset
    PROG3_MAGIC_TABLE_BASE + slot_idx * PROG3_MAGIC_STRIDE.
    The 8-byte metadata tail at offset+12 is untouched.
    """
    lines = _read_script_lines(script_path, PROG3_MAGIC_COUNT)
    if not lines:
        return []
    out: list[tuple[int, bytes]] = []
    for i, name in enumerate(lines):
        off = PROG3_MAGIC_TABLE_BASE + i * PROG3_MAGIC_STRIDE
        out.append((off, _pack_ascii_slot(name, PROG3_MAGIC_NAME_WIDTH)))
    return out


def _pack_skill_slot(name: str, slot_width: int) -> bytes:
    """Encode `name` ASCII, NUL-terminate, NUL-pad to fill `slot_width`.

    Unlike _pack_ascii_slot, this RESERVES a byte for the NUL terminator: the
    skill names are read as NUL-terminated C strings, so a name that exactly
    fills the slot (no terminator) would run into the next slot — the bug class
    behind "Double Magic"/"Treatment". Raises if name+NUL exceeds the slot.
    """
    raw = name.encode("ascii", errors="strict")
    if len(raw) + 1 > slot_width:
        raise ValueError(
            f"skill name {name!r} = {len(raw)}+NUL bytes > slot {slot_width}"
        )
    return raw + b"\x00" * (slot_width - len(raw))


def encode_prog3_skill_table(
    script_path: Path = PROJ / "scripts" / "en" / "prog3_skillE.txt",
) -> list[tuple[int, bytes]]:
    """Return overlay entries (offset, bytes) for the prog_3 skill-name table.

    Each name is written NUL-terminated at its POINTER-DEFINED offset
    (PROG3_SKILL_OFFSETS) and NUL-padded to fill its slot, so the in-game
    pointers to "Treatment"/"Item" resolve to whole names (not "ent") and
    "Double Magic" gets a terminator. See the table comment above.
    """
    lines = _read_script_lines(script_path, PROG3_SKILL_COUNT)
    if not lines:
        return []
    bounds = PROG3_SKILL_OFFSETS + [PROG3_SKILL_REGION_END]
    out: list[tuple[int, bytes]] = []
    for i, name in enumerate(lines):
        off = PROG3_SKILL_OFFSETS[i]
        width = bounds[i + 1] - off
        out.append((off, _pack_skill_slot(name, width)))
    return out


def encode_prog3_skill_pointers() -> list[tuple[int, bytes]]:
    """Return overlay entries (offset, BE32) for the dedicated skill-name
    pointers of slots 7/8, redirected to where this module places those names.

    The pointer is DERIVED from the table layout (PROG3_LOAD_BASE +
    PROG3_SKILL_OFFSETS[slot]), so it can never drift from the name it targets.
    JP baseline pointers read 0x060859A0 / 0x060859AC (the JP name positions);
    these point them at 0x060859A6 / 0x060859B0 — the "Treatment"/"Item" fix.
    Disembarked from byte_overlays.PROG_3_OVERLAY (the 0x1DD5F patch).
    """
    out: list[tuple[int, bytes]] = []
    for slot, ptr_off in PROG3_SKILL_PTR_OFFSETS.items():
        addr = PROG3_LOAD_BASE + PROG3_SKILL_OFFSETS[slot]
        out.append((ptr_off, struct.pack(">I", addr)))
    return out


def encoded_overlays() -> dict[str, list[tuple[int, bytes]]]:
    """All script-driven overlay entries, keyed by ISO path.

    Called by build.py to merge with the static byte_overlays.BYTE_OVERLAYS.
    Multiple encoder outputs for the same ISO path are concatenated; build.py
    applies them in order, so later entries win at overlapping offsets.
    """
    return {
        "LANG/PROG_3.BIN": (
            encode_prog3_skill_pointers()
            + encode_prog3_skill_table()
            + encode_prog3_magic_table()
        ),
    }
