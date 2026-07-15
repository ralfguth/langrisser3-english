"""scen005 hole-choice menu must fit the choice box (no clipped tail).

Bug (playtest 2026-06-13, screenshot 16:01): the third option rendered as
"Stamp it with your fee" — the final 't' was clipped. The choice box is a
fixed single-line, no-wrap window.

Empirical box budget (from the same screenshot): "Cover it with earth"
(10 encoder tiles) renders in full; "Stamp it with your feet" (12 tiles)
loses its last half-tile. So the box holds ~11 tiles; guard the proven-safe
10-tile width.

    Red state: the 3rd choice "Stamp it with your feet" = 12 tiles > 10.

The fix shortens it to "Stomp your feet" (8 tiles) — also closer to the JP
足をふみならす ("stamp one's feet"), which references no object, unlike the
invented "it with".
"""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from d00_tools import encode_text_to_entry  # noqa: E402
import font_tools as ft  # noqa: E402

SCEN005 = PROJ / "scripts/en/scen005E.txt"
BOX_TILES = 10  # proven-fitting width ("Cover it with earth")


def _tile_width(text):
    raw = encode_text_to_entry(text, ft.CHAR_TILE_MAP, ft.BIGRAM_TILE_MAP)
    return sum(1 for i in range(0, len(raw) - 1, 2)
               if ((raw[i] << 8) | raw[i + 1]) < 0xFFFC)


def _choice_entries():
    """The 3 choices are the entries right after the 'What do you do?'
    prompt (matched by content, not line number)."""
    lines = [l for l in SCEN005.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    for i, line in enumerate(lines):
        if line.startswith("What do you do?"):
            return lines[i + 1:i + 4]
    raise AssertionError("'What do you do?' prompt not found in scen005E")


def test_all_hole_choices_fit_box():
    choices = _choice_entries()
    assert len(choices) == 3
    for entry in choices:
        text = entry.split("<$")[0]  # strip trailing control code(s)
        w = _tile_width(entry)
        assert w <= BOX_TILES, (
            f"choice {text!r} is {w} tiles, clips the {BOX_TILES}-tile box"
        )
