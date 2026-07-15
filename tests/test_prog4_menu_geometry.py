"""test_prog4_menu_geometry.py — PROG_4 menu geometry, disembarked.

Carves the 234 PROG_4 layout runs (item X/Y, window w/h, the 187-run menu grid
@0x0B82D) out of the opaque byte_overlays blob into tools/prog4_menu_geometry.py.
(235 were carved 2026-06-14; the Battle-Preparations box over-widening @0x0AD10
was later reverted to the JP width 2026-06-23, leaving 234.)
This is the LAST byte_overlays content — after it, byte_overlays is empty and the
disembark score reaches 0.

PROG_4 load base 0x06089000. Truth-locks the runs vs the live JP ISO and asserts
the carve emptied PROG_4 (and therefore all of byte_overlays).

Red state (pre-carve, 2026-06-14): the 235 runs lived in
byte_overlays.PROG_4_OVERLAY.
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

from iso_tools import build_file_index, extract_file_data       # noqa: E402
from prog4_menu_geometry import PROG4_MENU_GEOMETRY             # noqa: E402
import byte_overlays                                            # noqa: E402

JP_ENV = "LANG3_JP_DIR"
ISO_PATH = "LANG/PROG_4.BIN"
RUNS = PROG4_MENU_GEOMETRY[ISO_PATH]


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
    return extract_file_data(image, entry.extent, entry.size)


def test_module_owns_234_runs_no_overlap():
    assert len(RUNS) == 234
    # Battle-Preparations box width (@0x0AD10) ships the JP width 0x11(17): the
    # inherited over-widening to 0x18(24) made the box too wide and was reverted
    # 2026-06-23. Guard that it stays unpatched (must not be re-widened).
    assert 0x0000AD10 not in {off for off, _ in RUNS}, (
        "Battle-Prep box width @0x0AD10 must stay unpatched (JP 17, not re-widened)"
    )
    ends = [(off, off + len(b)) for off, b in sorted(RUNS)]
    for (s0, e0), (s1, _e1) in zip(ends, ends[1:]):
        assert e0 <= s1, f"runs overlap near 0x{s0:05X}"


def test_no_spell_name_text_runs():
    """The magic-name TEXT table (offsets < 0x8100) belongs to
    prog4_spell_name_table.py — this module is geometry only."""
    assert all(off >= 0x8100 for off, _ in RUNS)


def test_runs_lie_inside_file_and_change_jp(jp_prog4):
    for off, chunk in RUNS:
        assert 0 <= off and off + len(chunk) <= len(jp_prog4), (
            f"run 0x{off:05X} out of range"
        )
        assert jp_prog4[off:off + len(chunk)] != chunk, (
            f"run 0x{off:05X} is a no-op vs JP — drifted offset"
        )


def test_prog4_carved_and_byte_overlays_empty():
    """PROG_4 was the last entry — byte_overlays must now be completely empty,
    i.e. the disembark of inherited byte runs is COMPLETE."""
    assert ISO_PATH not in byte_overlays.BYTE_OVERLAYS
    assert byte_overlays.BYTE_OVERLAYS == {}, (
        f"byte_overlays not empty: {list(byte_overlays.BYTE_OVERLAYS)}"
    )
