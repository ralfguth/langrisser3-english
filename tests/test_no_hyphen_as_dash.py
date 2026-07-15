#!/usr/bin/env python3
"""
test_no_hyphen_as_dash.py — No spaced hyphen in scen/plot prose.

A hyphen `-` is ONLY for compound words (`well-known`, `re-arm`) and proper-noun
joins (the location-label convention `Rigüler-Barral Border`). In all of those it
is **tight** — letters on both sides, no adjacent space.

A hyphen with a space on either side (` - `, ` -word`, `word- `) is a **spaced
hyphen used as an em-dash** — the trick someone used to dodge the no-em-dash rule
(the em-dash `—` isn't in the tile map and the font drops it, so a hyphen was
substituted). That is forbidden: dialogue and narration use **spoken punctuation
only** (`.` `,` `…` `?` `!`). Recast every spaced hyphen as a period, comma, or
ellipsis — and while you're there, don't mechanically mirror the JP line breaks.

Guards the canon in feedback_no_em_dash + the layout-fitting skill's
"spoken punctuation only" rule. Deterministic counterpart to the LLM word-split
audit (skill `langrisser3-script-audit`).

If a genuine tight compound ever trips a false positive, fix the regex — do not
add a spaced-hyphen exception (there is no legitimate spaced hyphen in prose).
"""
import re
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
EN_DIR = PROJ / "scripts" / "en"

_CTRL = re.compile(r"<\$[0-9A-Fa-f]{4}>")
# a hyphen-minus with whitespace immediately before OR after it
_SPACED_HYPHEN = re.compile(r"(?:\s-|-\s)")

# Exact (filename, 1-based line) pairs tolerated. Keep EMPTY — there is no
# legitimate spaced hyphen in spoken prose; recast it instead of allow-listing.
ALLOWED: set[tuple[str, int]] = set()


def _prose_files():
    files = sorted(EN_DIR.glob("scen*E.txt"))
    plot = EN_DIR / "plotE.txt"
    if plot.exists():
        files.append(plot)
    return files


def test_scen_files_present():
    assert _prose_files(), f"no scen*E.txt under {EN_DIR}"


def test_no_spaced_hyphen_in_prose():
    offenders = []
    for f in _prose_files():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            visible = _CTRL.sub("", line)
            if _SPACED_HYPHEN.search(visible) and (f.name, i) not in ALLOWED:
                offenders.append(f"  {f.name}:{i}: {line.strip()}")
    assert not offenders, (
        "spaced hyphen used as an em-dash (hyphen is only for tight compounds; "
        "recast with . , or …):\n" + "\n".join(offenders)
    )
