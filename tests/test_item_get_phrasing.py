"""Item-get phrasing is standardized to the house idiom.

Red state (before the 2026-06-30 normalization pass): the corpus rendered the
JP pickup announcement `〜を手に入れた！` / `〜を見つけた！` in five different EN
shapes — "Got the X!", "Got X!", "X was obtained!", "X obtained!",
"You obtained the X!" — and even mismatched the verb (one `手に入れた` rendered
"Found ..."). 49 entries used the passive "obtained" translationese.

This guard locks the one deterministic invariant: for every standard single-item
pickup line, the passive "obtained" translationese is banned.

Everything else is editorial and intentionally NOT asserted here:
  * the active phrasing may vary — "Got the X!", "Found X!", "Received X!",
    "The X is yours!" are all fine flavor;
  * the "the" article is a per-item choice (e.g. "Got Excalibur!" vs
    "Got the Crystal Ankh!").
The official Langrisser I&II remake uses a short standardized pickup message
("You acquired the item X!"); our house idiom is the punchier "Got the X!". JP
verb nuance is preserved by hand (`見つけた` -> "Found"), not locked here.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.layout_qa.parser import parse_scenario

EN_DIR = Path(__file__).resolve().parents[1] / "scripts" / "en"
JP_DIR = Path(__file__).resolve().parents[1] / "scripts" / "jp"

_CODE = re.compile(r"<\$[0-9A-Fa-f]{4}>")


def _strip_codes(s: str) -> str:
    return _CODE.sub("", s)


def _iter_item_gets():
    """Yield (scen, index, en_raw, jp_verb) for every standard pickup line.

    A standard pickup line is one whose JP, with control codes removed, ENDS in
    `を手に入れた！`, `を手にいれた！`, or `を見つけた！`. This excludes dialogue
    that merely uses find/get verbs ("I've found you, Böser!", "Got it.") and
    multi-sentence narrative beats.
    """
    for en_path in sorted(EN_DIR.glob("scen*E.txt")):
        scen = en_path.stem[:-1]
        jp_path = JP_DIR / f"{scen}J.txt"
        if not jp_path.exists():
            continue
        jp_by_index = {e.index: _strip_codes(e.raw) for e in parse_scenario(jp_path)}
        for e in parse_scenario(en_path):
            jp = jp_by_index.get(e.index, "")
            if jp.endswith("を手に入れた！") or jp.endswith("を手にいれた！"):
                yield scen, e.index, e.raw, "got"
            elif jp.endswith("を見つけた！"):
                yield scen, e.index, e.raw, "found"


def test_no_obtained_translationese():
    """No standard pickup line uses the passive 'obtained' translationese."""
    offenders = [
        f"{scen}[{idx}] {en!r}"
        for scen, idx, en, _verb in _iter_item_gets()
        if "obtained" in en.lower()
    ]
    assert not offenders, "passive 'obtained' item-get translationese:\n" + "\n".join(
        offenders
    )
