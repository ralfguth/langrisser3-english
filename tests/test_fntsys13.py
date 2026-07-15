"""TDD gate for fntsys13 (item descriptions).

fntsys13 is the item-description text in FNT_SYS.BIN pair 12. It renders in an
18-tile-wide box that does NOT auto-wrap: each record is exactly one screen line,
so a record wider than the box runs off-screen (the historical failure mode).
fntsys13 is encoded half-width (BIGRAM_PAIRS={12}); see
archive/docs/20260607_fntsys13_handoff.md.

These tests lock the deterministic invariants BEFORE the translation is finalized:
  1. the source builds to exactly 701 records with NO line/width overflow,
  2. every record fits the 18-tile box under the real bigram encoder,
  3. the structural item->record grid (175*4 + 1) is preserved,
  4. scripts/en/fntsys13E.txt on disk equals the deterministic build output,
  5. encode_fntsys accepts it and yields 701 records in pair 12.
"""

import re
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

FNTSYS10 = PROJ / "scripts" / "en" / "fntsys10E.txt"
FNTSYS13_SRC = PROJ / "metadata" / "en" / "fntsys13_src.txt"
JP13 = PROJ / "scripts" / "jp" / "fntsys13J.txt"


def _records(path):
    return [l.rstrip("\n").replace("<$FFFF>", "")
            for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _fntsys10_names():
    return _records(FNTSYS10)


def _src_item_names():
    names = []
    for l in FNTSYS13_SRC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#\s+\d+\s+(.*)", l)
        if m:
            names.append(m.group(1).strip())
    return names


def _grid_starts():
    """Record offset where each item's description begins (cumulative grid)."""
    starts, s = [], 0
    for c in b13.ITEM_RECORD_COUNTS:
        starts.append(s)
        s += c
    return starts, s

import build_fntsys13 as b13          # noqa: E402
from fnt_sys_tools import (            # noqa: E402
    parse_fnt_sys, encode_fntsys, EXPECTED_JP_RECORD_COUNTS,
)

MAX_TILES = 18
TOTAL_RECORDS = 701
JP_FNTSYS = PROJ / "cache" / "fnt_sys_jp.bin"


def test_source_builds_without_overflow():
    """Every item's prose fits its JP record budget; no record exceeds 18 tiles."""
    records, overflows = b13.build_records()
    assert overflows == [], (
        f"{len(overflows)} item(s) over budget: "
        + "; ".join(f"{h} ({g}>{bud})" for _, h, g, bud, _ in overflows[:12])
    )
    assert len(records) == TOTAL_RECORDS


def test_every_record_within_box():
    """No record may exceed the 18-tile description box (no off-screen run)."""
    records, _ = b13.build_records()
    too_wide = [(i, b13.tile_width(r)) for i, r in enumerate(records)
                if b13.tile_width(r) > MAX_TILES]
    assert too_wide == [], f"records over {MAX_TILES} tiles: {too_wide[:12]}"


def test_record_count_matches_jp_grid():
    """175 items * 4 records + 1 blank == 701 (the rigid grid)."""
    assert sum(b13.ITEM_RECORD_COUNTS) == TOTAL_RECORDS
    assert len(b13.ITEM_RECORD_COUNTS) == 176
    assert EXPECTED_JP_RECORD_COUNTS[12] == TOTAL_RECORDS


def test_disk_file_matches_build():
    """scripts/en/fntsys13E.txt must be the deterministic build output."""
    records, overflows = b13.build_records()
    assert overflows == []
    expected = "".join(r + "<$FFFF>\n" for r in records)
    assert b13.OUT.read_text(encoding="utf-8") == expected, (
        "fntsys13E.txt is stale — run tools/build_fntsys13.py"
    )


@pytest.mark.skipif(not JP_FNTSYS.exists(), reason="JP FNT_SYS baseline absent")
def test_encode_fntsys_accepts_fntsys13():
    """encode_fntsys builds a FNT_SYS whose pair 12 has 701 records."""
    out = encode_fntsys(JP_FNTSYS.read_bytes(), PROJ / "scripts" / "en")
    fs = parse_fnt_sys(out)
    assert fs.pairs[12].record_count == TOTAL_RECORDS


# --- item <-> record boundary mapping -------------------------------------
# These lock WHICH item each description belongs to. A skipped/reordered/merged
# item (the historical "Wisdom Fruit" bug) shifts every later description into
# the wrong item; these tests catch that immediately.

def test_item_order_matches_fntsys10():
    """Each fntsys13 block maps 1:1, in order, to fntsys10 items 2..177."""
    expected = _fntsys10_names()[1:177]   # fntsys10 line 1 = "None" (no desc)
    got = _src_item_names()
    assert len(got) == 176, f"{len(got)} item blocks, expected 176"
    # first divergence is the easiest to read when this fails
    for i, (a, e) in enumerate(zip(got, expected)):
        assert a == e, f"item block {i} = {a!r}, expected fntsys10 {e!r}"
    assert got == expected


def test_item_record_boundaries():
    """Item k (1-based) owns the 4-grid slice [start : start+count]."""
    counts = b13.ITEM_RECORD_COUNTS
    starts, total = _grid_starts()
    assert total == TOTAL_RECORDS
    assert len(counts) == 176
    assert all(c == 4 for c in counts[:175]) and counts[175] == 1
    # anchors verified semantically in the handoff doc
    assert starts[0] == 0        # item 1  Masayan Sword -> recs 0-3
    assert starts[8] == 32       # item 9  Kusanagi      -> recs 32-35
    assert starts[164] == 656    # item 165 Earth Rune    -> recs 656-659
    assert starts[175] == 700    # item 176 (dup)         -> rec 700


def test_jp_boundaries_are_terminal():
    """Each item's LAST jp record is a terminal line (stat / sentence-end /
    blank), proving the 4-grid boundaries line up with the JP source itself."""
    jp = _records(JP13)
    assert len(jp) == TOTAL_RECORDS
    starts, _ = _grid_starts()
    counts = b13.ITEM_RECORD_COUNTS
    # ＤＦ/ＡＴ = defense/attack stat labels. They used to decode as "Ｄゲ" / "Ａ<$0024>"
    # because tiles 22 (Ｆ), 36 (Ｔ) and 370 (＋) were mislabeled / unmapped in the
    # JP decode map; corrected in data/jp/tile_map.json (see
    # tests/test_jp_tile_map_misdecode.py and test_jp_tile_map_unmapped_filled.py).
    term = re.compile(
        r"(修正|ＤＦ|ＡＴ|射程|知力|ＭＶ|ＭＰ|ＨＰ|魔法抵抗|範囲|クリティカル|消費|強さ|"
        r"発動|効果|耐性|属性|上昇|ドレイン|レベル|回復|増加)")
    for k, (st, c) in enumerate(zip(starts, counts), start=1):
        last = jp[st + c - 1].rstrip("　 ")   # drop trailing pad space
        ok = (not last
              or last.endswith(("。", "！", "」", "）", "？"))
              or term.search(last))
        assert ok, f"item {k}: last jp record not terminal: {last!r}"


def test_first_jp_record_is_description_start():
    """Each item's FIRST jp record is a description start, not a continuation
    (a continuation here would mean the previous item's text bled across)."""
    jp = _records(JP13)
    starts, _ = _grid_starts()
    # hiragana okurigana / closing punctuation never begin a real description
    cont = set("るりられろっんをにのはがでとも、。」）")
    # item 144 (Power Fruit) genuinely begins "の方の島に…" in the JP source: the
    # leading 東 of "東の方の島" is elided/rare-encoded. Content (巨木の木の実→STR)
    # confirms the boundary is correct, so this is a known JP quirk, not a bug.
    KNOWN_QUIRK = {144}
    bad = []
    for k, st in enumerate(starts, start=1):
        first = jp[st]
        if k in KNOWN_QUIRK:
            continue
        if first and first != "　" and first[0] in cont:
            bad.append((k, first))
    assert bad == [], f"items whose first jp record looks like a continuation: {bad}"
