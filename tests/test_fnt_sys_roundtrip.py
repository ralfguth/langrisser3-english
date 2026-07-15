"""test_fnt_sys_roundtrip.py — FNT_SYS structural invariants vs the JP baseline.

Locks the format facts that make FNT_SYS editing safe:

1. parse(x) -> build() is byte-identical for the pristine JP FNT_SYS.BIN
   (cache/fnt_sys_jp.bin, populated by build.py from the user's JP ISO).
2. encode_fntsys(JP, scripts/en) preserves the JP per-pair RECORD COUNTS.
   Counts are the pointer-shift invariant: a dropped/merged record shifts
   every later string in its section. Content is intentionally divergent
   (all 15 pairs are EN, half-width bigram encoded — EN output is smaller
   than JP, so total size is NOT an invariant) and is covered by the
   per-section tests (test_fntsys2/12/13, fntsys_desc_qa, ...).
3. Pair 13 (name-entry keyboard) exposes the full EN key set: UC page
   tiles 17-42, LC page tiles 1585-1610, control icons 1488-1490.

History: this file previously also round-tripped archive/v02_baseline/
fnt_sys.bin (the 0.2 patch-era blob with known count corruption). That archive
was deleted — the 0.2 patch reference is the 'English Menus v0.2' ISO, forensic
only — so those tests were retired with it (2026-06-10, roadmap T02).
"""

import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from fnt_sys_tools import (
    PAIR_INDICES, EXPECTED_JP_RECORD_COUNTS, JP_FILE_SIZE,
    LOOKUP_SECTION_BYTES, WRAM_BASE, SECTION_BASE_OFFSET,
    parse_fnt_sys, build_fnt_sys, encode_fntsys,
)

JP_PATH = PROJECT / "cache" / "fnt_sys_jp.bin"
SCRIPTS_DIR = PROJECT / "scripts" / "en"


def _require(path: Path):
    if not path.exists():
        pytest.skip(f"{path.relative_to(PROJECT)} not present "
                    f"(run build.py once to populate cache/fnt_sys_jp.bin)")


def _record_tile_ids(rec: bytes) -> set[int]:
    return {struct.unpack_from(">H", rec, i)[0]
            for i in range(0, len(rec) - 1, 2)}


# ---------------------------------------------------------------------------
# JP round-trip
# ---------------------------------------------------------------------------

def test_jp_file_size():
    _require(JP_PATH)
    assert JP_PATH.stat().st_size == JP_FILE_SIZE


def test_jp_parses():
    _require(JP_PATH)
    fs = parse_fnt_sys(JP_PATH.read_bytes())
    assert len(fs.pairs) == 15
    assert len(fs.lookup) == LOOKUP_SECTION_BYTES
    assert fs.pointers[0] == WRAM_BASE + SECTION_BASE_OFFSET


def test_jp_record_counts():
    _require(JP_PATH)
    fs = parse_fnt_sys(JP_PATH.read_bytes())
    actual = [p.record_count for p in fs.pairs]
    assert actual == EXPECTED_JP_RECORD_COUNTS


def test_jp_roundtrip_byte_identical():
    _require(JP_PATH)
    data = JP_PATH.read_bytes()
    fs = parse_fnt_sys(data)
    rebuilt = build_fnt_sys(fs)
    assert rebuilt == data, (
        f"JP round-trip diverged: {sum(1 for a, b in zip(rebuilt, data) if a != b)} "
        f"bytes differ; len {len(rebuilt)} vs {len(data)}"
    )


# ---------------------------------------------------------------------------
# EN encode: record-count parity with JP (the pointer-shift invariant)
# ---------------------------------------------------------------------------

def test_encode_fntsys_preserves_jp_record_counts():
    """Every pair encoded from scripts/en must keep the JP record count.

    This replaced the old `encoded size >= JP size` canary: with all 15
    pairs disembarked to half-width bigram EN, the encoded file is
    legitimately SMALLER than JP. What must never change is the record
    count per section — the engine indexes records by position."""
    _require(JP_PATH)
    if not (SCRIPTS_DIR / "fntsys1E.txt").exists():
        pytest.skip("scripts/en/fntsys*E.txt not present")

    encoded = encode_fntsys(JP_PATH.read_bytes(), SCRIPTS_DIR)
    fs_enc = parse_fnt_sys(encoded)
    actual = [p.record_count for p in fs_enc.pairs]
    assert actual == EXPECTED_JP_RECORD_COUNTS, (
        "encoded FNT_SYS record counts diverge from JP "
        f"(pair_index: enc vs jp): "
        f"{[(i, a, j) for i, (a, j) in enumerate(zip(actual, EXPECTED_JP_RECORD_COUNTS)) if a != j]}"
    )


def test_pair_13_keyboard_exposes_full_en_key_set():
    """Pair 13 (name-entry keyboard) must carry 21 records exposing the
    complete EN key set: UC page (tiles 17-42), LC page (tiles
    1585-1610), and the BACK/END/FORWARD control icons (1488-1490).

    Structural successor of the old byte-compare against the deleted 0.2 patch
    baseline blob; the key-set facts are the part that must not regress."""
    _require(JP_PATH)
    if not (SCRIPTS_DIR / "fntsys14E.txt").exists():
        pytest.skip("scripts/en/fntsys14E.txt not present")

    encoded = encode_fntsys(JP_PATH.read_bytes(), SCRIPTS_DIR)
    pair13 = parse_fnt_sys(encoded).pairs[13]
    assert len(pair13.records) == 21

    ids: set[int] = set()
    for rec in pair13.records:
        ids |= _record_tile_ids(rec)

    uc = set(range(17, 43))          # A-Z full-width page
    lc = set(range(1585, 1611))      # a-z keyboard page
    icons = {1488, 1489, 1490}       # BACK / END / FORWARD
    for name, want in (("UC page", uc), ("LC page", lc), ("control icons", icons)):
        missing = sorted(want - ids)
        assert not missing, f"pair 13 keyboard missing {name} tiles: {missing}"


# ---------------------------------------------------------------------------
# Edit semantics: marking a pair as edited regenerates its offset table
# ---------------------------------------------------------------------------

def test_edited_pair_regenerates_offset_table():
    """When pair.edited=True, build_fnt_sys recomputes the offset table
    from the current record list (the path used by Phase 2+ editing)."""
    _require(JP_PATH)
    fs = parse_fnt_sys(JP_PATH.read_bytes())
    # Drop the last record from pair 0 and mark as edited. Trailer cleared
    # since we changed the data section length.
    fs.pairs[0].records = fs.pairs[0].records[:-1]
    fs.pairs[0].data_trailer = b""
    fs.pairs[0].edited = True

    rebuilt = build_fnt_sys(fs)
    # Re-parse and verify the change took effect.
    fs2 = parse_fnt_sys(rebuilt)
    assert fs2.pairs[0].record_count == EXPECTED_JP_RECORD_COUNTS[0] - 1
    # Other pairs unaffected.
    for i in range(1, 15):
        assert fs2.pairs[i].record_count == EXPECTED_JP_RECORD_COUNTS[i]
