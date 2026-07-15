"""test_saveload_stays_zenkaku.py — lock the "keep SAVE/LOAD zenkaku" decision.

User decision (2026-06-13): drop the battle-menu SAVE/LOAD repoint experiment;
SAVE/LOAD stays the universal zenkaku rec84/85 (ＳＡＶＥ/ＬＯＡＤ) everywhere.

This guard pins that the repoint is gone and cannot creep back:
  - fntsys1 rec19/20 hold the zenkaku ＬＯＡＤ/ＳＡＶＥ (the JP-duplicate pair),
    not the "LOAD1"/"SAVE1" consumer-hunt markers;
  - NO wired build patch touches the battle-menu SAVE/LOAD pointer sites:
    PROG_7 0x9E2C/0x9E32 (prep menu) and PROG_3 0x19534/0x1AEC4 (map menu),
    so those bytes stay at the JP baseline.

Red state (pre-revert, commit 8e59137): prog7_prep_menu_saveload.py and
prog3_saveload_canary.py patched exactly these offsets -> this test failed.
"""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

# Battle-menu SAVE/LOAD pointer sites that must stay JP (un-repointed).
FORBIDDEN = {
    "LANG/PROG_7.BIN": {0x9E2C, 0x9E32},
    "LANG/PROG_3.BIN": {0x19534, 0x1AEC4},
}


def _all_wired_edits() -> dict:
    """Merge every (offset, bytes) edit build.py wires, keyed by ISO path."""
    from byte_overlays import BYTE_OVERLAYS
    from prog_text_tools import encoded_overlays
    from prog3_nameplate_new_line import PROG3_NAMEPLATE_NEW_LINE
    from prog3_statup_template import PROG3_STATUP_TEMPLATE
    from prog4_field_box_geometry import PROG4_FIELD_BOX_GEOMETRY
    from prog4_equip_title import PROG4_EQUIP_TITLE
    from a0lang_options_menu_geometry import A0LANG_OPTIONS_MENU_GEOMETRY

    merged: dict[str, list] = {}
    sources = [BYTE_OVERLAYS, encoded_overlays(), PROG3_NAMEPLATE_NEW_LINE,
               PROG3_STATUP_TEMPLATE, PROG4_FIELD_BOX_GEOMETRY,
               PROG4_EQUIP_TITLE, A0LANG_OPTIONS_MENU_GEOMETRY]
    for src in sources:
        for path, edits in src.items():
            merged.setdefault(path, []).extend(edits)
    return merged


def test_no_battle_menu_saveload_repoint():
    merged = _all_wired_edits()
    for path, forbidden_offsets in FORBIDDEN.items():
        offsets = {off for off, _ in merged.get(path, [])}
        clash = offsets & forbidden_offsets
        assert not clash, (
            f"{path}: a wired patch touches battle SAVE/LOAD pointer site(s) "
            f"{[hex(o) for o in clash]} — SAVE/LOAD must stay zenkaku (no repoint)")


def test_rec19_20_are_ascii_saveload():
    """User decision 2026-06-26: the menu labels render HALF-WIDTH — only the
    SCENARIO / TURN title words stay zenkaku. So rec19/20 are ASCII LOAD/SAVE
    (which the bigram encoder pairs half-width), not the full-width forms. The
    battle-menu pointer sites are still un-repointed (test above)."""
    lines = (PROJECT / "scripts" / "en" / "fntsys1E.txt").read_text(
        encoding="utf-8").splitlines()
    # rec N == line N+1 (0-indexed records, 1-indexed lines)
    assert lines[19] == "LOAD<$FFFF>", f"rec19 must be ASCII LOAD, got {lines[19]!r}"
    assert lines[20] == "SAVE<$FFFF>", f"rec20 must be ASCII SAVE, got {lines[20]!r}"
