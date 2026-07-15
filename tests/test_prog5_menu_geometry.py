"""test_prog5_menu_geometry.py — PROG_5 menu geometry, disembarked.

Carves the 63 PROG_5 layout runs out of the opaque byte_overlays blob into the
self-documenting tools/prog5_menu_geometry.py module. Every run is an A0LANG
display-list coordinate (item X/Y or window w/h) nudged off the JP value to fit
the wider English labels; PROG_5 load base 0x06089000 (see the module header for
the two-way pin). These tests truth-lock the runs vs the live JP ISO and assert
the carve emptied PROG_5 out of byte_overlays.

Red state (pre-carve, 2026-06-14): the 63 runs lived in
byte_overlays.PROG_5_OVERLAY.
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

from iso_tools import build_file_index, extract_file_data       # noqa: E402
from prog5_menu_geometry import PROG5_MENU_GEOMETRY             # noqa: E402
import byte_overlays                                            # noqa: E402

JP_ENV = "LANG3_JP_DIR"
ISO_PATH = "LANG/PROG_5.BIN"
RUNS = PROG5_MENU_GEOMETRY[ISO_PATH]


@pytest.fixture(scope="module")
def jp_prog5():
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


def test_module_owns_63_runs():
    assert len(RUNS) == 63
    # all runs sorted, non-overlapping
    ends = [(off, off + len(b)) for off, b in sorted(RUNS)]
    for (s0, e0), (s1, _e1) in zip(ends, ends[1:]):
        assert e0 <= s1, f"runs overlap near 0x{s0:05X}"


def test_runs_lie_inside_file_and_change_jp(jp_prog5):
    """Truth-lock: every run fits in PROG_5 and differs from the JP baseline
    (a no-op would mean an offset drifted off its node)."""
    for off, chunk in RUNS:
        assert 0 <= off and off + len(chunk) <= len(jp_prog5), (
            f"run 0x{off:05X} out of range"
        )
        assert jp_prog5[off:off + len(chunk)] != chunk, (
            f"run 0x{off:05X} is a no-op vs JP — drifted offset"
        )


def test_prog5_carved_out_of_byte_overlays():
    assert ISO_PATH not in byte_overlays.BYTE_OVERLAYS, (
        "PROG_5 still in byte_overlays — carve incomplete"
    )
