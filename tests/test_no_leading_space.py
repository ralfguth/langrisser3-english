#!/usr/bin/env python3
"""
test_no_leading_space.py — No EN entry may begin with a literal ASCII space.

Guardrail against a metric-gaming defect class.

A leading ASCII space at the START of a scenNNNE.txt physical line is NOT
an engine delimiter and is NOT a layout convention — it is padding. The
layout-QA simulator counts that space as +1 tile against line 0, so a
leading space can artificially push a thin line over the `low_line_usage`
threshold and "earn" a POLISHED score the rendered text does not deserve.
(Earlier progress.txt notes wrongly described the leading space as "the
engine's delimiter"; that was a hallucination and is being removed.)

The ONLY legitimate centering is the SCENARIO-title balloon, produced by
tools/center_scenario_titles.py. Those entries begin with a control code
(`<$0000>`), never with a literal space, and their centering spaces live
mid-entry after `<$FFFC>`. So the rule is absolute at line start: a physical
line in scripts/en/scen*E.txt must never begin with ' '.

If a genuinely-centered label is ever needed, add its exact (file, 1-based
line) to ALLOWED below with a justification — do not weaken the check.
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

EN_DIR = PROJ / 'scripts' / 'en'

# Exact (filename, 1-based line number) pairs allowed to start with a space.
# Keep empty: centering is done with the `<$0000>` blank-tile token (which
# does NOT start with a space), never a literal leading space — so a real
# centered label still passes this guard without an exception. A non-empty
# entry here would mean a leading ASCII space we have chosen to tolerate;
# prefer converting it to `<$0000>` padding instead.
ALLOWED: set[tuple[str, int]] = set()


def _scen_files():
    return sorted(EN_DIR.glob('scen*E.txt'))


def test_scen_files_present():
    assert _scen_files(), f'no scen*E.txt under {EN_DIR}'


def test_no_entry_starts_with_space():
    violations = []
    for f in _scen_files():
        lines = f.read_text(encoding='utf-8').split('\n')
        for i, line in enumerate(lines, start=1):
            if line.startswith(' ') and (f.name, i) not in ALLOWED:
                violations.append(f'{f.name}:{i}: {line[:60]!r}')
    assert not violations, (
        f'{len(violations)} EN entries begin with a leading ASCII space '
        f'(padding defect — strip it):\n' + '\n'.join(violations[:40])
        + ('\n...' if len(violations) > 40 else '')
    )
