"""TDD gate for fntsys8 (spell/summon name labels) — FNT_SYS pair 7.

Locks the Heal/Force Heal level ladder (records 26-31) against the JP
source. The disembark-era EN had dropped the level numbers and the
'Heal' word (rec28 'Heal', rec29/30 'Force 1 '/'Force 2 ' with trailing
space cruft, rec31 'Force'), which collapses six distinct spells into
ambiguous labels. JP (fntsys8J.txt):

    26 ヒール１        Heal 1
    27 ヒール２        Heal 2
    28 ヒール３        Heal 3
    29 フォースヒール１  Force Heal 1
    30 フォースヒール２  Force Heal 2
    31 フォースヒール３  Force Heal 3

Budget: per-record JP tile width (full-width chars, 1 tile each) is the
on-screen box floor — the longest of these is 8 tiles; the EN encodes to
7, verified by the width test below with the REAL encoder.
"""

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from fnt_sys_tools import _build_fntsys_char_map  # noqa: E402
from d00_tools import encode_text_to_entry        # noqa: E402
from font_tools import BIGRAM_TILE_MAP            # noqa: E402

FNTSYS8 = PROJ / "scripts" / "en" / "fntsys8E.txt"

EXPECTED_HEAL_LADDER = {
    26: "Heal 1",
    27: "Heal 2",
    28: "Heal 3",
    29: "Force Heal 1",
    30: "Force Heal 2",
    31: "Force Heal 3",
}
JP_BUDGET_TILES = 8   # フォースヒール１ = 8 full-width tiles


def _records():
    return [l.rstrip("\n") for l in FNTSYS8.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def test_heal_ladder_matches_jp():
    recs = _records()
    bad = {}
    for ri, want in EXPECTED_HEAL_LADDER.items():
        got = recs[ri].replace("<$FFFF>", "")
        if got != want:
            bad[ri] = (got, want)
    assert not bad, f"fntsys8 Heal/Force Heal ladder diverges (rec: got, want): {bad}"


def test_heal_ladder_fits_jp_budget():
    char_map = _build_fntsys_char_map()
    for ri, text in EXPECTED_HEAL_LADDER.items():
        rec = encode_text_to_entry(text, char_map, bigram_tile_map=BIGRAM_TILE_MAP)
        width = len(rec) // 2
        assert width <= JP_BUDGET_TILES, (
            f"rec {ri} {text!r} encodes to {width} tiles > JP budget "
            f"{JP_BUDGET_TILES}"
        )


def test_no_trailing_space_before_terminator():
    """' <$FFFF>' is 0.2 patch trailing-space cruft (stripped repo-wide in
    143e79a); it must not come back."""
    bad = [i for i, rec in enumerate(_records()) if " <$FFFF>" in rec]
    assert not bad, f"fntsys8 records with trailing space cruft: {bad}"
