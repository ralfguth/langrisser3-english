"""Truth-lock for the equip-screen title repoint (tools/prog4_equip_title.py).

1. The PROG_4 literal pool holds the documented JP record offsets
   (74/147/183 as index*2) — drift fails loudly.
2. The composed EN title fits its slots continuously: 'Commander'
   (slot X=2) must end before X=12, rec96 'Equipment' (slot X=12) before
   X=22 — measured with the real encoder on the live scripts.
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from prog4_equip_title import (  # noqa: E402
    PROG4_EQUIP_TITLE,
    JP_BASELINE_U16,
    SLOT1_OFFSET,
    SLOT1_REC_EN,
)

ISO_PATH = "LANG/PROG_4.BIN"


@pytest.fixture(scope="module")
def jp_prog4():
    jp_dir = os.environ.get("LANG3_JP_DIR")
    if not jp_dir:
        pytest.skip("LANG3_JP_DIR env var not set")
    candidates = (list(Path(jp_dir).glob("*rack*01*.bin"))
                  or list(Path(jp_dir).glob("*.bin")))
    if not candidates:
        pytest.skip(f"no Track 01 .bin in {jp_dir}")
    from iso_tools import build_file_index, extract_file_data
    image = candidates[0].read_bytes()
    entry = build_file_index(image).get(ISO_PATH)
    assert entry is not None
    return extract_file_data(image, entry.extent, entry.size)


def test_jp_pool_baseline(jp_prog4):
    for off, val in JP_BASELINE_U16.items():
        got = int.from_bytes(jp_prog4[off:off + 2], "big")
        assert got == val, (
            f"JP PROG_4.BIN u16[0x{off:04X}] = 0x{got:04X}, expected "
            f"0x{val:04X} — title pool offsets drifted"
        )


def test_patch_is_single_slot1_repoint():
    edits = PROG4_EQUIP_TITLE[ISO_PATH]
    assert edits == [(SLOT1_OFFSET, (SLOT1_REC_EN * 2).to_bytes(2, "big"))]


def _tiles(text):
    from d00_tools import encode_text_to_entry
    from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP
    enc = encode_text_to_entry(text, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
    return sum(1 for i in range(0, len(enc), 2) if enc[i:i + 2] != b"\xff\xff")


def test_composed_title_fits_slots():
    lines = (PROJECT / "scripts/en/fntsys1E.txt").read_text(
        encoding="utf-8").splitlines()
    # slot X=2 piece (rec147) must end before the X=12 slot
    commander = lines[147].replace("<$FFFF>", "")
    assert 2 + _tiles(commander) * 2 - 1 < 12, commander
    # slot X=12 piece (rec96) must end before the X=22 slot
    equipment = lines[SLOT1_REC_EN].replace("<$FFFF>", "")
    assert equipment, "rec96 must carry the title centre piece"
    assert 12 + _tiles(equipment) * 2 - 1 < 22, equipment
