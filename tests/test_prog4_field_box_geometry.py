"""Truth-lock for the field 2x2 command-box geometry patch
(tools/prog4_field_box_geometry.py).

Same contract as tests/test_prog3_statup_template.py, against the LIVE JP
baseline (LANG3_JP_DIR):

1. Every patch site holds the documented JP byte (0x07 = column-2 X) in
   the pristine PROG_4.BIN, and the surrounding display-list node
   structure matches the documented template (type/attr/sentinel) — if
   the offsets drift, fail loudly instead of patching the wrong data.
2. The replacement X (0x0B = 11 cells) really clears the current EN
   column-1 texts: 'Confirm' must end before column 2 starts, with the
   same 1-cell gap JP uses. Measured with the REAL encoder — if a future
   edit makes rec48/rec11 longer, this fails before the box glues again.
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from prog4_field_box_geometry import (  # noqa: E402
    PROG4_FIELD_BOX_GEOMETRY,
    JP_BASELINE,
    COL1_X,
    COL2_X_EN,
    WIDTH_EN,
    WIDTH_JP,
    POSX_EN,
    POSX_JP,
    NODE_OFFSETS,
    WINDOW_NODE_OFFSET,
)

ISO_PATH = "LANG/PROG_4.BIN"


@pytest.fixture(scope="module")
def jp_prog4():
    jp_dir = os.environ.get("LANG3_JP_DIR")
    if not jp_dir:
        pytest.skip("LANG3_JP_DIR env var not set")
    candidates = (list(Path(jp_dir).glob("*rack*01*.bin"))
                  or list(Path(jp_dir).glob("*rack*1*.bin"))
                  or list(Path(jp_dir).glob("*.bin")))
    if not candidates:
        pytest.skip(f"no Track 01 .bin in {jp_dir}")
    from iso_tools import build_file_index, extract_file_data
    image = candidates[0].read_bytes()
    entry = build_file_index(image).get(ISO_PATH)
    assert entry is not None, f"{ISO_PATH} not in JP ISO"
    return extract_file_data(image, entry.extent, entry.size)


def test_jp_baseline_bytes_match(jp_prog4):
    for off, jp_byte in JP_BASELINE.items():
        assert jp_prog4[off] == jp_byte, (
            f"JP PROG_4.BIN[0x{off:06X}] = 0x{jp_prog4[off]:02X}, expected "
            f"0x{jp_byte:02X} — patch offsets drifted"
        )


def test_node_template_structure(jp_prog4):
    """The 4 text nodes + terminator must look exactly as documented:
    [01 00 00 00][X Y 00 00][07 00 00 00][06 03 A4 A2] x4, then type-00."""
    sentinel = bytes.fromhex("0603a4a2")
    expected_xy = [(0x02, 0x01), (0x07, 0x01), (0x02, 0x03), (0x07, 0x03)]
    for node_off, (x, y) in zip(NODE_OFFSETS, expected_xy):
        node = jp_prog4[node_off:node_off + 16]
        assert node[0:4] == bytes.fromhex("01000000"), hex(node_off)
        assert (node[4], node[5]) == (x, y), hex(node_off)
        assert node[8:12] == bytes.fromhex("07000000"), hex(node_off)
        assert node[12:16] == sentinel, hex(node_off)
    term = jp_prog4[NODE_OFFSETS[-1] + 16:NODE_OFFSETS[-1] + 20]
    assert term == bytes.fromhex("00000000"), "terminator node missing"


def test_window_node_structure(jp_prog4):
    """Window node: [01 00 00 00][posX=11 posY=10][W=0x12 H=6][children]."""
    node = jp_prog4[WINDOW_NODE_OFFSET:WINDOW_NODE_OFFSET + 16]
    assert node[0:4] == bytes.fromhex("01000000")
    assert (node[4], node[5]) == (POSX_JP, 0x0A)
    assert (node[8], node[9]) == (WIDTH_JP, 0x06)
    assert node[12:16] == bytes.fromhex("06093ee8")  # children RAM ptr


def test_patch_edits_are_the_documented_bytes():
    edits = PROG4_FIELD_BOX_GEOMETRY[ISO_PATH]
    assert len(edits) == 4
    values = {off: chunk for off, chunk in edits}
    for off in (NODE_OFFSETS[1] + 4, NODE_OFFSETS[3] + 4):
        assert values[off] == bytes([COL2_X_EN])
    assert values[WINDOW_NODE_OFFSET + 4] == bytes([POSX_EN])
    assert values[WINDOW_NODE_OFFSET + 8] == bytes([WIDTH_EN])
    assert set(values) == set(JP_BASELINE)


def test_window_stays_screen_centered():
    """The user-confirmed invariant: the box is centered on the 320px
    screen, so any width change must be compensated by posX (equal growth
    on both sides). JP: 11..28 cells = 88..232px, center 160."""
    center_jp = (POSX_JP * 2 + WIDTH_JP) * 8 / 2
    center_en = (POSX_EN * 2 + WIDTH_EN) * 8 / 2
    assert center_jp == 160.0
    assert center_en == center_jp


def _tiles(text):
    from d00_tools import encode_text_to_entry
    from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP
    enc = encode_text_to_entry(text, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
    return sum(1 for i in range(0, len(enc), 2) if enc[i:i + 2] != b"\xff\xff")


def _rec_text(rec_index):
    lines = (PROJECT / "scripts/en/fntsys1E.txt").read_text(
        encoding="utf-8").splitlines()
    return lines[rec_index].replace("<$FFFF>", "")


def test_en_column1_texts_clear_column2():
    """Column-1 texts must not OVERLAP column 2 (end_cell < COL2_X_EN).
    Cells = half-width 8px units; one 16x16 tile = 2 cells. Measured with
    the real encoder on the live scripts (rec48 Confirm, rec11 Cancel).
    Adjacency is allowed: 'Confirm' (7 chars in 4 tiles) ends with a
    blank half-tile, which IS the visual gap (user-tuned, 2026-06-10)."""
    for rec_index in (48, 11):
        text = _rec_text(rec_index)
        end_cell = COL1_X + _tiles(text) * 2 - 1
        assert end_cell < COL2_X_EN, (
            f"fntsys1 rec{rec_index} {text!r} ends at cell {end_cell}; "
            f"column 2 at {COL2_X_EN} would glue — shorten the text or "
            f"widen the box module"
        )


def test_en_column2_texts_clear_right_border():
    """Column-2 texts must end before the right border tile (last window
    cell, WIDTH_EN-1). 'View Map' overdrawing the border at width 0x12 is
    what the 2026-06-10 playtest caught (rec152 View Map, rec120 Return)."""
    for rec_index in (152, 120):
        text = _rec_text(rec_index)
        end_cell = COL2_X_EN + _tiles(text) * 2 - 1
        assert end_cell < WIDTH_EN - 1, (
            f"fntsys1 rec{rec_index} {text!r} ends at cell {end_cell}, on/"
            f"past the border tile at {WIDTH_EN - 1} — shorten the text or "
            f"widen the window"
        )
