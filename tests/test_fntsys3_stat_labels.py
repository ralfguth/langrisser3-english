"""fntsys3 level-up stat labels STR / INT must render TIGHT.

Bug (playtest 2026-06-13, screenshots 16:18/16:21): the battle level-up
screen showed "ST R   1 rose!" and "IN T   1 rose!" — the 3-letter labels
split with a visible gap.

Root cause: fntsys3 records 21 ("STR") and 22 ("INT") were plain text, so
the greedy fntsys encoder emitted a 2-char bigram ("ST"/"IN") followed by a
STANDALONE uppercase letter ("R"/"T"). Standalone A-Z map to the CENTERED
full-width tiles 17-42 (deliberately, until the FONT.BIN rebuild — see
tests/test_stat_bigrams.py::test_halfwidth_uppercase_unchanged_for_now), so
the trailing letter renders centered-with-gap: "ST R".

    Red state: records[21] == 'STR<$FFFF>' -> 0148 0022 FFFF (0x22 = R, a
    centered 17-42 tile -> the gap). records[22] -> 0137 0024 FFFF.

Fix: the dedicated TIGHT stat-label glyph tiles already exist in
font_tools._MENU_GLYPHS (1531='ST', 1532='R' left-half; 1526='IN',
1527='T' left-half — drawn precisely for these labels). Pin them via
explicit <$05FB><$05FC> / <$05F6><$05F7> tile codes in the source, which is
exactly what scripts/wip/fntsys3.txt always intended.
"""
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import fnt_sys_tools as fs  # noqa: E402
from d00_tools import encode_text_to_entry  # noqa: E402
from font_tools import FNTSYS_BIGRAM_TILE_MAP  # noqa: E402

FNTSYS3 = PROJ / "scripts/en/fntsys3E.txt"

# Dedicated tight stat-label tiles (font_tools._MENU_GLYPHS).
STR_TILES = bytes([0x05, 0xFB, 0x05, 0xFC, 0xFF, 0xFF])  # [ST][R-left]
INT_TILES = bytes([0x05, 0xF6, 0x05, 0xF7, 0xFF, 0xFF])  # [IN][T-left]

# Record indices in fntsys3E.txt (no blank lines -> index == line-1).
STR_IDX = 21
INT_IDX = 22


def _records():
    return fs._parse_script_records(FNTSYS3)


def _encode(line):
    # fntsys3 is pair_idx 2 in BIGRAM_PAIRS -> bigram map applies.
    return encode_text_to_entry(line, fs._build_fntsys_char_map(),
                                bigram_tile_map=FNTSYS_BIGRAM_TILE_MAP)


def test_indices_stable():
    """The stat-label block sits at 18..23; lock the neighbours so the
    STR/INT index pins below stay meaningful if the file is reordered."""
    recs = _records()
    assert recs[17] == "AT<$FFFF>"
    assert recs[18] == "DF<$FFFF>"
    assert recs[19] == "HP<$FFFF>"
    assert recs[20] == "MP<$FFFF>"


def test_str_label_is_tight_pair():
    assert _encode(_records()[STR_IDX]) == STR_TILES


def test_int_label_is_tight_pair():
    assert _encode(_records()[INT_IDX]) == INT_TILES


def test_no_centered_standalone_in_str_int():
    """The user-visible defect: a centered full-width tile (17-42) in the
    STR/INT label is the gap. Neither label may emit one."""
    for idx in (STR_IDX, INT_IDX):
        raw = _encode(_records()[idx])
        tiles = struct.unpack(f">{len(raw)//2}H", raw)
        centered = [t for t in tiles if 17 <= t <= 42]
        assert not centered, f"record {idx} emits centered tile(s) {centered}"


def test_two_char_labels_still_single_tile():
    """Regression: AT/DF/HP/MP stay one tight tile each (unchanged)."""
    recs = _records()
    for idx in (17, 18, 19, 20):
        raw = _encode(recs[idx])
        assert len(raw) == 4, f"record {idx} should be 1 tile + FFFF"
