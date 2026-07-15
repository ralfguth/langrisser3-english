"""test_syswin_roundtrip.py — gate test for the SYSWIN.BIN disembark.

Locks the Phase 6 foundation: parse(x) -> build() is byte-identical to the
pristine JP SYSWIN.BIN, and the parsed structure matches what we RE'd
(30 window pointers, 43 records, the FFFF-terminated tile-id stream framed
by win[1]..win[2]). See archive/docs/20260606_syswin_format_re.md.

Round-trip is the only safe foundation for editing syswin content. The
EN/JP source files (scripts/{en,jp}/syswin*.txt) are slot-aligned to these
43 records; this test also pins that alignment.
"""

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from syswin_tools import parse_syswin, build_syswin, N_WINDOW_PTRS

JP_PATH = PROJECT / "cache" / "syswin_jp.bin"
EN_SRC = PROJECT / "scripts" / "en" / "syswinE.txt"
JP_SRC = PROJECT / "scripts" / "jp" / "syswinJ.txt"

EXPECTED_RECORDS = 43


def _require(path: Path):
    if not path.exists():
        pytest.skip(f"{path.relative_to(PROJECT)} not present "
                    f"(run build.py once to populate cache/syswin_jp.bin)")


def test_jp_parses_to_expected_shape():
    _require(JP_PATH)
    sw = parse_syswin(JP_PATH.read_bytes())
    assert len(sw.records) == EXPECTED_RECORDS
    assert sw.win0 == 0x78 and sw.win1 == 0xCE and sw.win2 == 0x1D4


def test_jp_roundtrip_byte_identical():
    _require(JP_PATH)
    data = JP_PATH.read_bytes()
    assert build_syswin(parse_syswin(data)) == data


def test_window_pointer_count():
    _require(JP_PATH)
    # The 30 window pointers frame the file; parser depends on the first three.
    assert N_WINDOW_PTRS == 30


def test_source_files_have_one_line_per_record():
    """syswinE.txt / syswinJ.txt are slot-aligned to the 43 records."""
    en = EN_SRC.read_text(encoding="utf-8").splitlines()
    jp = JP_SRC.read_text(encoding="utf-8").splitlines()
    assert len(en) == EXPECTED_RECORDS, f"syswinE.txt has {len(en)} lines"
    assert len(jp) == EXPECTED_RECORDS, f"syswinJ.txt has {len(jp)} lines"


def test_source_known_slots():
    """A few anchor slots must hold the JP-faithful translation (and NOT the
    legacy 0.2 patch misalignment where Yes/No sat at slots 38/39)."""
    en = EN_SRC.read_text(encoding="utf-8").splitlines()
    assert en[0] == "Orders"   # 命令 = order menu (series canon; was "Command")
    assert en[40] == "Yes"
    assert en[41] == "No"
    assert en[42] == "Loading"   # "Now " cut 2026-06-12: win[1] budget (JP fills it exactly)
    assert en[38] == "" and en[39] == ""   # JP blanks, not Yes/No
