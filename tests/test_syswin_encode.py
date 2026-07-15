"""test_syswin_encode.py — gate tests for the script-driven SYSWIN encoder.

Phase 6 completion: SYSWIN.BIN is generated from scripts/en/syswinE.txt via
syswin_tools.encode_syswin (FNTSYS bigram maps), replacing the 0.2 patch-derived
SYSWIN_OVERLAY blob. Locks:

  - 43 records, strict parse_syswin round-trip (0.2 patch shipped 42 — it ate a
    terminator; ours must not).
  - Blank script lines preserve the JP record bytes (single 0x0000 tile).
  - Translated records decode back to the script text through the reverse
    FNTSYS maps (the encoder right-blank-space rule may drop a space byte,
    so spaces are normalized before comparing).
  - The Loading record carries NO dot/ellipsis tiles (the 0.2 patch blob drew
    'Loading.……'; JP is ロード中です — no dots).
  - Everything outside the win[0]..win[2] text region is byte-identical to
    the JP shell (window pointers fixed).
  - The stream fits the win[1]..win[2] budget (build_syswin raises if not).
"""

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from syswin_tools import parse_syswin, encode_syswin
from font_tools import FNTSYS_CHAR_TILE_MAP, FNTSYS_BIGRAM_TILE_MAP

JP_PATH = PROJECT / "cache" / "syswin_jp.bin"
EN_SRC = PROJECT / "scripts" / "en" / "syswinE.txt"

EXPECTED_RECORDS = 43


def _require(path: Path):
    if not path.exists():
        pytest.skip(f"{path.relative_to(PROJECT)} not present "
                    f"(run build.py once to populate cache/syswin_jp.bin)")


def _reverse_map():
    rev = {}
    for ch, t in FNTSYS_CHAR_TILE_MAP.items():
        rev.setdefault(t, ch if isinstance(ch, str) else "".join(ch))
    for bg, t in FNTSYS_BIGRAM_TILE_MAP.items():
        rev.setdefault(t, bg if isinstance(bg, str) else "".join(bg))
    return rev


def _encoded():
    _require(JP_PATH)
    _require(EN_SRC)
    jp = JP_PATH.read_bytes()
    return jp, encode_syswin(jp, EN_SRC)


def test_encode_keeps_43_records_and_strict_parse():
    _, en = _encoded()
    sw = parse_syswin(en)          # strict: offset table must match stream
    assert len(sw.records) == EXPECTED_RECORDS


def test_blank_lines_are_empty_records():
    # Blank script lines -> empty records (FFFF only). The JP placeholders
    # each hold a 0x0000 space tile; emptying reclaims the padding bytes that
    # let longer English labels fit the fixed win[1]..win[2] byte budget.
    _, en = _encoded()
    sw_en = parse_syswin(en)
    lines = EN_SRC.read_text(encoding="utf-8").splitlines()
    assert len(lines) == EXPECTED_RECORDS
    for line, rec_en in zip(lines, sw_en.records):
        if not line.strip():
            assert rec_en == []


def test_records_decode_back_to_script_text():
    _, en = _encoded()
    sw = parse_syswin(en)
    rev = _reverse_map()
    lines = EN_SRC.read_text(encoding="utf-8").splitlines()
    for line, rec in zip(lines, sw.records):
        if not line.strip():
            continue
        decoded = "".join(rev.get(t, f"<{t:04X}>") for t in rec)
        assert "<" not in decoded, f"unmapped tile in {line!r}: {decoded!r}"
        assert decoded.replace(" ", "") == line.replace(" ", ""), (
            f"{line!r} decoded as {decoded!r}")


def test_loading_record_has_no_dots():
    _, en = _encoded()
    sw = parse_syswin(en)
    rev = _reverse_map()
    decoded = "".join(rev.get(t, "") for t in sw.records[42])
    assert "." not in decoded and "…" not in decoded
    assert decoded.replace(" ", "") == "Loading"


def test_shell_outside_text_region_is_jp_verbatim():
    jp, en = _encoded()
    sw = parse_syswin(jp)
    assert en[:sw.win0] == jp[:sw.win0]
    assert en[sw.win2:] == jp[sw.win2:]
    assert len(en) == len(jp)
