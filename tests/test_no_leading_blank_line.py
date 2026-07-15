#!/usr/bin/env python3
"""
test_no_leading_blank_line.py — No scenNNNE.txt may begin with a blank line.

Guardrail for entry-index hygiene (see feedback_leading_blank_offsets_indexing).

The build parser (`d00_tools.parse_script_file`) and the analysis parser
(`layout_qa.parser.parse_scenario`) BOTH skip blank lines, so a leading blank
line is byte-irrelevant to the built D00.DAT — it produces no entry and shifts
no pointer. But it DOES poison every tool/human that reads the file with
`splitlines()[i]` and treats the physical line number as the entry index: a
leading blank makes physical-line-N point at entry-(N-1). That off-by-one is
exactly the trap that made an earlier JP↔EN width measurement read a
result-dialogue line as if it were a menu option (2026-06-14).

Removing leading blanks is therefore a safe no-op for the game and a real fix
for tooling. This guard keeps them gone.

Red state when introduced: scen005E, scen051E, scen052E led with a blank line
(scen052E with two).
"""

from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
EN_DIR = PROJ / 'scripts' / 'en'


def test_no_scen_file_starts_with_a_blank_line():
    offenders = []
    for path in sorted(EN_DIR.glob('scen*E.txt')):
        lines = path.read_text(encoding='utf-8').splitlines()
        if lines and not lines[0].strip():
            offenders.append(path.name)
    assert not offenders, (
        "scen*E.txt files must not begin with a blank line "
        f"(entry-index hygiene). Offenders: {offenders}"
    )
