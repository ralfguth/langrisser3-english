"""test_prog6_battle_cmd_width.py — in-battle command-box width, disembarked.

Carves the 3 PROG_6 width bumps out of the opaque byte_overlays blob into a
self-documenting RE'd module (feedback_patch_per_module_closed_scope).

RE provenance (see tools/prog6_battle_cmd_width.py + archive/docs/
20260608_menu_box_geometry_re.md): the in-battle unit command menu is drawn
from three A0LANG-style window descriptor nodes inside LANG/PROG_6.BIN
(load base 0x0609A800, pinned by internal pointer self-consistency — each
node's child ptr 0x060C7xxx resolves to a valid in-file text node). Each
16-byte node is [posX u8][posY u8][00 00][width u8][height u8][00 00]
[child ptr u32][term u32]; the width field (node+4) is JP 0x0D and is widened
so the English command labels fit. The width field is the same one the box
dispatcher PROG_3 FUN_0607d168 reads (0x0d/0x11 by flag).

Red state (pre-carve, 2026-06-14): the 3 width runs lived in
byte_overlays.BYTE_OVERLAYS["LANG/PROG_6.BIN"]; this module did not exist.
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

from iso_tools import build_file_index, extract_file_data   # noqa: E402
from prog6_battle_cmd_width import PROG6_BATTLE_CMD_WIDTH    # noqa: E402
import byte_overlays                                         # noqa: E402

JP_ENV = "LANG3_JP_DIR"
ISO_PATH = "LANG/PROG_6.BIN"
JP_WIDTH = 0x0D   # JP baseline width field of all three command-box nodes

# The three width fields (file offset → widened EN value), at node+4.
EXPECTED = {0x0002CBA4: 0x12, 0x0002CC84: 0x0F, 0x0002CDDC: 0x0F}


@pytest.fixture(scope="module")
def jp_prog6():
    jp_dir = os.environ.get(JP_ENV)
    if not jp_dir:
        pytest.skip(f"{JP_ENV} env var not set")
    cands = list(Path(jp_dir).glob("*rack*01*.bin")) or \
            list(Path(jp_dir).glob("*rack*1*.bin")) or list(Path(jp_dir).glob("*.bin"))
    if not cands:
        pytest.skip(f"no Track 01 .bin in {jp_dir}")
    image = cands[0].read_bytes()
    index = build_file_index(image)
    entry = index.get(ISO_PATH)
    assert entry is not None, f"{ISO_PATH} not in JP ISO"
    return extract_file_data(image, entry.extent, entry.size)


def test_module_declares_three_width_widens():
    """The module owns exactly the 3 command-box width fields, widening each
    past the JP 0x0D so the English labels fit."""
    edits = dict(PROG6_BATTLE_CMD_WIDTH[ISO_PATH])
    got = {off: chunk[0] for off, chunk in edits.items()}
    assert got == EXPECTED
    for off, val in got.items():
        assert val > JP_WIDTH, f"0x{off:05X}: width {val:#x} not wider than JP 0x0D"


def test_truth_lock_jp_baseline(jp_prog6):
    """Truth-lock against the LIVE JP ISO: every patched offset is 0x0D in JP
    and the module changes it (a no-op would mean the offsets drifted)."""
    for off, val in EXPECTED.items():
        assert jp_prog6[off] == JP_WIDTH, (
            f"0x{off:05X}: JP baseline is {jp_prog6[off]:#x}, expected 0x0D — "
            f"offset drifted"
        )
        assert val != jp_prog6[off]


def test_prog6_fully_disembarked_from_byte_overlays():
    """Ownership moved: PROG_6 must no longer appear in the opaque overlay."""
    assert ISO_PATH not in byte_overlays.BYTE_OVERLAYS, (
        "PROG_6 width bumps still in byte_overlays — carve incomplete"
    )
