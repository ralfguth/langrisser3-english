"""Name-entry keyboard buttons (tiles 1488-1490) carry OUR art.

fntsys14's keyboard rows reference these three tiles as function keys.
2026-06-11 (user): ADV = right arrow, BAK = left arrow (EagleIII
arrowhead, extended shaft), END = condensed "END" in one 16x16 tile —
replacing the 0.2 patch stacked-letter icons.
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import font_tools as ft  # noqa: E402

JP_FONT = PROJ / 'data' / 'jp' / 'font_jp.bin'


@pytest.fixture(scope='module')
def font():
    if not JP_FONT.exists():
        pytest.skip('JP FONT.BIN not present')
    return ft.generate_english_font(JP_FONT.read_bytes())


def test_buttons_are_our_art(font):
    for idx, data in ft._NAME_ENTRY_BUTTON_TILES.items():
        assert font[idx * 32:(idx + 1) * 32] == data, f"tile {idx}"


def test_arrows_mirror_each_other():
    adv = ft._NAME_ENTRY_BUTTON_TILES[1488]
    bak = ft._NAME_ENTRY_BUTTON_TILES[1489]

    def mirror_row(v):
        return int(f'{v:016b}'[::-1], 2)

    for row in range(16):
        a = int.from_bytes(adv[row * 2:row * 2 + 2], 'big')
        b = int.from_bytes(bak[row * 2:row * 2 + 2], 'big')
        assert mirror_row(a) == b, f"row {row}: arrows are not mirrored"


def test_end_tile_has_ink(font):
    end = ft._NAME_ENTRY_BUTTON_TILES[1490]
    assert any(end), "END tile is blank"
