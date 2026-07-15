"""Guard: dialogue ellipsis is the single glyph "…", never ASCII "...".

House punctuation canon (see test_no_em_dash / feedback 2026-06-14): spoken
text uses ". , … ? !" — the ellipsis is the one-glyph "…". Various passes
drifted 93 ASCII three-dot runs into the scen scripts; they render with
different spacing than the "…" tile and read inconsistently next to it.

Red state (2026-07-06): 93 "..." runs across 20 scen files (e.g. scen003
"I know what you mean...", scen010 box narrations, scen005 "Heh heh heh...").

Scope: scen*.txt dialogue/narration only. fntsys*/syswin* string tables keep
their own budgets + disk-match invariants (same exclusion as the other canon
guards); fntsys13's lone "On use...?" is out of scope here.
"""
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts' / 'en'

DOTS = re.compile(r'\.{3,}')


def test_no_ascii_ellipsis_in_scen_scripts():
    bad = []
    for path in sorted(SCRIPTS.glob('scen*.txt')):
        for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if DOTS.search(line.replace('<$FFFC>', '')):
                bad.append(f'{path.name}:{lineno}')
    assert not bad, f'ASCII "..." must be the "…" glyph ({len(bad)} lines): {bad[:10]}'
