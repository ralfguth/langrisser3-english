"""test_prog4_spell_name_table.py — magic-icon spell-name table, disembarked.

Carves the PROG_4 magic-icon spell-name table out of the opaque byte_overlays
blob into a named, declared module (feedback_patch_per_module_closed_scope).

USER DECISION (2026-06-14): ship this table BYTE-IDENTICAL to the inherited 0.2
English text for now — it is TEXT, not geometry, and the proper script-driven,
font-aware encoder is deferred to Phase B (roadmap T28). The table is
crash-prone (feedback_magic_table_fragile): never change entry lengths without
Ghidra RE. So this carve only relocates the bytes into a self-documenting home;
it does not re-encode them.

RE provenance (see tools/prog4_spell_name_table.py): the table lives at PROG_4
0x7F80 (runtime 0x06090F80, load base 0x06089000), a stride-0xC array of
half-width katakana names + per-entry level/icon metadata, index-accessed by
FUN_060912e8 (confirmed by Ghidra xref into the region). The 33 EN labels are
the uppercase magic-cast icon names (TELEPORT, HEAL3, FIRE, ...).

Red state (pre-carve, 2026-06-14): the 3 runs lived in
byte_overlays.PROG_4_OVERLAY (offsets < 0x8100).
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

from iso_tools import build_file_index, extract_file_data        # noqa: E402
from prog4_spell_name_table import PROG4_SPELL_NAME_TABLE         # noqa: E402
import byte_overlays                                             # noqa: E402

JP_ENV = "LANG3_JP_DIR"
ISO_PATH = "LANG/PROG_4.BIN"
TABLE_LO, TABLE_HI = 0x7F80, 0x80A9

EXPECTED_NAMES = [
    "TELEPORT", "F.HEAL3", "F.HEAL2", "F.HEAL1", "HEAL3", "HEAL2", "HEAL1",
    "RESIST", "QUICK", "ATTACK2", "ATTACK1", "PROTECT2", "PROTECT1", "DECLINE",
    "MUTE", "ZONE", "CONFUSE", "SLEEP", "BLAST", "MP DRAIN", "HP DRAIN",
    "T.UNDEAD", "HOLY BLZ", "METEOR", "EARTHQKE", "TORNADO", "WINDCUTR",
    "T.STORM", "THUNDER", "BLIZZARD", "FREEZE", "FIREBALL", "FIRE",
]


@pytest.fixture(scope="module")
def jp_prog4():
    jp_dir = os.environ.get(JP_ENV)
    if not jp_dir:
        pytest.skip(f"{JP_ENV} env var not set")
    cands = list(Path(jp_dir).glob("*rack*01*.bin")) or \
            list(Path(jp_dir).glob("*rack*1*.bin")) or list(Path(jp_dir).glob("*.bin"))
    if not cands:
        pytest.skip(f"no Track 01 .bin in {jp_dir}")
    image = cands[0].read_bytes()
    entry = build_file_index(image).get(ISO_PATH)
    assert entry is not None
    return bytearray(extract_file_data(image, entry.extent, entry.size))


def _decode_names(region: bytes) -> list[str]:
    return [t.decode("ascii") for t in region.split(b"\x00")
            if len(t) >= 2 and all(32 <= c < 127 for c in t)]


def test_module_owns_three_runs_289_bytes():
    runs = PROG4_SPELL_NAME_TABLE[ISO_PATH]
    assert [off for off, _ in runs] == [0x7F80, 0x800C, 0x8014]
    assert sum(len(b) for _, b in runs) == 289


def test_table_decodes_to_canonical_spell_names(jp_prog4):
    """Apply the module's runs over JP and decode the table: the 33 uppercase
    magic-icon names must appear in order (semantic + offset fidelity)."""
    buf = bytearray(jp_prog4)
    for off, chunk in PROG4_SPELL_NAME_TABLE[ISO_PATH]:
        buf[off:off + len(chunk)] = chunk
    assert _decode_names(bytes(buf[TABLE_LO:TABLE_HI])) == EXPECTED_NAMES


def test_truth_lock_overwrites_jp_katakana(jp_prog4):
    """JP baseline is half-width katakana (non-ASCII); the EN table must differ
    (a no-op would mean the offsets drifted off the table)."""
    for off, chunk in PROG4_SPELL_NAME_TABLE[ISO_PATH]:
        assert jp_prog4[off:off + len(chunk)] != chunk


def test_spell_table_carved_out_of_byte_overlays():
    """The 3 magic-name runs (offsets < 0x8100) must no longer live in the
    opaque PROG_4 overlay."""
    leftover = [off for off, _ in byte_overlays.BYTE_OVERLAYS.get(ISO_PATH, ())
                if off < 0x8100]
    assert leftover == [], f"magic-name runs still in byte_overlays: {leftover}"
