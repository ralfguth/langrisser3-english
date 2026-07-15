"""TDD gate for the PROG_3 skill-name table (battle command labels).

Root cause of the in-game "Treatment" -> "ent" bug (found 2026-06-07 by RE):
the skill-name table at PROG_3 0x3314C is POINTER-INDEXED, not uniform stride.
Slots 0-6 are base+index*0xC, but "Treatment"[7] and "Item"[8] have dedicated
pointers in PROG_3 (file 0x1DD5C / 0x1DD60 -> SH-2 0x060859A6 / 0x060859B0,
load base 0x06052800) that place them at 0x331A6 / 0x331B0. Those pointers are
set by byte_overlays.PROG_3_OVERLAY (0x1DD5F patch).

The old encoder wrote every slot at uniform stride 0xC, so:
  - "Double Magic" (exactly 12 chars) filled its 0xC slot with NO NUL terminator;
  - "Treatment" landed at 0x331A0, but the pointer reads 0x331A6 -> "ent".

These tests lock the END-TO-END invariant: after applying the prog_text encoders
onto JP PROG_3, the NUL-terminated string at each pointer target equals the
intended name, and every command name is correctly terminated. This is the
invariant the bug violated.

Disembark note (2026-06-14): the slot-7/8 pointer redirect used to live in the
opaque byte_overlays.PROG_3_OVERLAY (0x1DD5F). It is now DERIVED from the table
layout by prog_text_tools.encode_prog3_skill_pointers() (pointer = load base +
PROG3_SKILL_OFFSETS[slot]), so PROG_3 no longer appears in byte_overlays.
"""

import struct
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from iso_tools import build_file_index, extract_file_data            # noqa: E402
import byte_overlays                                                 # noqa: E402
from prog_text_tools import (                                       # noqa: E402
    encode_prog3_skill_table, encode_prog3_magic_table,
    encode_prog3_skill_pointers, PROG3_SKILL_OFFSETS,
)

JP_ISO = Path("/home/ralf/Jogos/emulacao/romsets/sega-saturn/cue-bin/"
              "Langrisser III (Japan)/Langrisser III (Japan) (3M) (Track 01).bin")

PROG3_LOAD_BASE = 0x06052800        # SH-2 addr = file offset + this
PTR_TREATMENT = 0x1DD5C             # BE32 pointer to the "Treatment" name
PTR_ITEM = 0x1DD60                  # BE32 pointer to the "Item" name
SKILL_SCRIPT = PROJ / "scripts" / "en" / "prog3_skillE.txt"

pytestmark = pytest.mark.skipif(not JP_ISO.exists(), reason="JP ISO absent")


def _jp_prog3() -> bytearray:
    img = bytearray(JP_ISO.read_bytes())
    e = build_file_index(img)["LANG/PROG_3.BIN"]
    return bytearray(extract_file_data(img, e.extent, e.size))


def _built_prog3() -> bytes:
    """JP PROG_3 with the same overlays build.py applies (encoders only now —
    the pointer redirect is one of them via encode_prog3_skill_pointers)."""
    buf = _jp_prog3()
    for off, b in (encode_prog3_skill_pointers()
                   + encode_prog3_skill_table() + encode_prog3_magic_table()):
        buf[off:off + len(b)] = b
    return bytes(buf)


def test_prog3_fully_disembarked_from_byte_overlays():
    """The skill-name pointer redirect was the last PROG_3 run in the opaque
    overlay; carving it into encode_prog3_skill_pointers() empties PROG_3."""
    assert "LANG/PROG_3.BIN" not in byte_overlays.BYTE_OVERLAYS, (
        "PROG_3 still in byte_overlays — pointer redirect not fully carved"
    )


def test_skill_pointers_derived_from_table():
    """The redirect is DERIVED, not magic: each emitted pointer equals
    load base + the slot's name offset, and differs from the JP baseline
    (slot7 0x060859A0 -> 0x060859A6, slot8 0x060859AC -> 0x060859B0)."""
    emitted = dict(encode_prog3_skill_pointers())
    jp = _jp_prog3()
    for slot, ptr_off in ((7, PTR_TREATMENT), (8, PTR_ITEM)):
        want = PROG3_LOAD_BASE + PROG3_SKILL_OFFSETS[slot]
        got = struct.unpack(">I", emitted[ptr_off])[0]
        assert got == want, f"slot{slot} ptr 0x{got:08X} != derived 0x{want:08X}"
        jp_ptr = struct.unpack_from(">I", jp, ptr_off)[0]
        assert got != jp_ptr, f"slot{slot} ptr is a no-op vs JP 0x{jp_ptr:08X}"


def _cstr(buf: bytes, off: int) -> str:
    end = buf.index(b"\x00", off)
    return buf[off:end].decode("ascii", errors="replace")


def _name_at_pointer(buf: bytes, ptr_off: int) -> str:
    addr = struct.unpack_from(">I", buf, ptr_off)[0]
    return _cstr(buf, addr - PROG3_LOAD_BASE)


def test_treatment_pointer_resolves_to_treatment():
    """The exact in-game bug: pointer -> "ent" must now be "Treatment"."""
    assert _name_at_pointer(_built_prog3(), PTR_TREATMENT) == "Treatment"


def test_item_pointer_resolves_to_item():
    assert _name_at_pointer(_built_prog3(), PTR_ITEM) == "Item"


def test_double_magic_is_nul_terminated():
    """12-char "Double Magic" must not run into the next slot."""
    buf = _built_prog3()
    # slot 6 lives at base+6*0xC = 0x33194 (slots 0-6 are uniform stride)
    assert _cstr(buf, 0x33194) == "Double Magic"


def test_all_skill_names_match_script_in_order():
    buf = _built_prog3()
    want = [l for l in SKILL_SCRIPT.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    got, off = [], 0x3314C
    region_end = 0x331B8
    while off < region_end and len(got) < len(want):
        if buf[off] == 0:
            off += 1
            continue
        s = _cstr(buf, off)
        got.append(s)
        off += len(s)
    assert got == want


def test_encoder_rejects_overlong_name():
    """A name that cannot fit its pointer-defined slot must raise, not corrupt."""
    import prog_text_tools as p
    with pytest.raises(ValueError):
        p._pack_skill_slot("WayTooLongName", 10)  # 14+NUL > 10-byte slot
