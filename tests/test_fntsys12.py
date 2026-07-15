"""TDD gate for fntsys12 (class descriptions) — mirrors test_fntsys13.

fntsys12 is the class-description text in FNT_SYS.BIN pair 11. Like fntsys13 it
renders in an 18-tile-wide box that does NOT auto-wrap, on a rigid grid of 4
records per class (class k=1..87 -> 4 records, entry 88 -> 1 blank = 349 total).
A record wider than 18 tiles runs off the box border on screen (the bug the user
reported: lines "saindo das bordas dos quadros").

These tests lock the deterministic invariants:
  1. every record in the SHIPPED scripts/en/fntsys12E.txt fits the 18-tile box
     (builder-independent — guards the actual file the build embeds),
  2. the source builds to exactly 349 records with NO line/width overflow,
  3. the item->record grid (87*4 + 1) is preserved,
  4. scripts/en/fntsys12E.txt on disk equals the deterministic build output,
  5. encode_fntsys accepts it and yields 349 records in pair 11.

The same 18-tile guard is also applied to fntsys13E.txt so a single test file
covers every fixed-grid description box that renders through the shared font.
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import build_fntsys12 as b12          # noqa: E402
import build_fntsys13 as b13          # noqa: E402  (tile_width via real encoder)
from fnt_sys_tools import (            # noqa: E402
    parse_fnt_sys, encode_fntsys, EXPECTED_JP_RECORD_COUNTS,
)

MAX_TILES = 18
TOTAL_RECORDS = 349
JP_FNTSYS = PROJ / "cache" / "fnt_sys_jp.bin"

SHIPPED = {
    "fntsys12E.txt": PROJ / "scripts" / "en" / "fntsys12E.txt",
    "fntsys13E.txt": PROJ / "scripts" / "en" / "fntsys13E.txt",
}


def _records(path: Path):
    return [l.rstrip("\n").replace("<$FFFF>", "")
            for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# --- builder-independent guard on the actual shipped files ----------------

@pytest.mark.parametrize("name", sorted(SHIPPED))
def test_shipped_records_fit_18_tile_box(name):
    """Every record in the file the build embeds must fit the 18-tile box,
    measured with the REAL encoder. This is what stops a stale/over-long line
    from running off the screen, regardless of how the file was produced."""
    path = SHIPPED[name]
    if not path.exists():
        pytest.skip(f"{path.relative_to(PROJ)} not present")
    too_wide = [(i, b13.tile_width(r), r)
                for i, r in enumerate(_records(path))
                if b13.tile_width(r) > MAX_TILES]
    assert too_wide == [], (
        f"{name}: {len(too_wide)} record(s) exceed {MAX_TILES} tiles "
        f"(run off the box border):\n"
        + "\n".join(f"  rec {i}: {w} tiles  {r!r}" for i, w, r in too_wide[:15])
    )


# --- fntsys12 deterministic build invariants ------------------------------

def test_source_builds_without_overflow():
    """Every class's prose fits its 4-record budget; no record exceeds 18 tiles."""
    records, overflows = b12.build_records()
    assert overflows == [], (
        f"{len(overflows)} class(es) over budget (tighten these): "
        + "; ".join(f"{h} ({g}>{bud})" for _, h, g, bud, _ in overflows[:25])
    )
    assert len(records) == TOTAL_RECORDS


def test_every_record_within_box():
    records, _ = b12.build_records()
    too_wide = [(i, b13.tile_width(r)) for i, r in enumerate(records)
                if b13.tile_width(r) > MAX_TILES]
    assert too_wide == [], f"records over {MAX_TILES} tiles: {too_wide[:15]}"


def test_record_count_matches_jp_grid():
    """87 classes * 4 records + 1 blank == 349 (the rigid grid)."""
    assert sum(b12.ITEM_RECORD_COUNTS) == TOTAL_RECORDS
    assert len(b12.ITEM_RECORD_COUNTS) == 88
    assert EXPECTED_JP_RECORD_COUNTS[11] == TOTAL_RECORDS


def test_disk_file_matches_build():
    """scripts/en/fntsys12E.txt must be the deterministic build output."""
    records, overflows = b12.build_records()
    assert overflows == [], "source overflows; cannot match disk (tighten prose)"
    expected = "".join(r + "<$FFFF>\n" for r in records)
    assert b12.OUT.read_text(encoding="utf-8") == expected, (
        "fntsys12E.txt is stale — run tools/build_fntsys12.py"
    )


@pytest.mark.skipif(not JP_FNTSYS.exists(), reason="JP FNT_SYS baseline absent")
def test_encode_fntsys_accepts_fntsys12():
    """encode_fntsys builds a FNT_SYS whose pair 11 has 349 records."""
    out = encode_fntsys(JP_FNTSYS.read_bytes(), PROJ / "scripts" / "en")
    fs = parse_fnt_sys(out)
    assert fs.pairs[11].record_count == TOTAL_RECORDS
