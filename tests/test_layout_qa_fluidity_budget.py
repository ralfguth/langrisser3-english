"""test_layout_qa_fluidity_budget.py — the tightened fluidity gate.

The old gate let ANY short sentence-final non-final line pass as
`fluidity_headroom` (info, POLISHED), which rewarded mechanical JP-mirroring
compression (a thin `Yes.` on the first line "passed"). Two new rules:

1. The FIRST line of a balloon may NOT be short, even sentence-final → it is
   `low_line_usage` (warning, blocks POLISHED). No token, no exception.
2. Every OTHER short sentence-final non-final line spends one token from a
   per-scen bucket of `floor(10% of entries)`. Within budget → `fluidity_headroom`;
   over budget → `low_line_usage`. The agent must spend the scarce budget on the
   cases worth keeping short and FILL the rest (prioritising quality).
"""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.parser import Entry, Segment  # noqa: E402
from layout_qa.simulator import simulate_entry  # noqa: E402
from layout_qa.cli import _apply_fluidity_budget  # noqa: E402

PROF_DIALOGUE = {'name': 'DIALOGUE_12X4', 'width': 12, 'max_lines': 4,
                 'enforce_line_padding': True}


def _e(*parts, terminator='FFFE'):
    segs = []
    for p in parts:
        if p.startswith('<$') and p.endswith('>'):
            segs.append(Segment('ctrl', p))
        else:
            segs.append(Segment('text', p))
    if not (segs and segs[-1].kind == 'ctrl' and segs[-1].value.endswith(f'{terminator}>')):
        segs.append(Segment('ctrl', f'<${terminator}>'))
    return Entry('scenTEST', 0, ''.join(s.value for s in segs), terminator, segs)


def _codes(issues):
    return [i.code for i in issues]


# --- Rule 1: first line short is banned (even sentence-final) -----------------

def test_first_line_short_sentence_final_is_banned():
    # 'Yes.' on line 0 of a multi-line balloon ends a sentence but is tiny.
    e = _e('Yes.', '<$FFFC>', 'never mind me at all here')
    codes = _codes(simulate_entry(e, PROF_DIALOGUE)[0])
    assert 'fluidity_headroom' not in codes, "first short line must NOT get the free pass"
    assert 'low_line_usage' in codes


def test_single_line_short_balloon_still_exempt():
    # A standalone short utterance is the FINAL line of its balloon -> exempt.
    e = _e('Yes.')
    assert 'low_line_usage' not in _codes(simulate_entry(e, PROF_DIALOGUE)[0])


# --- Rule 2: non-first short sentence-final line earns fluidity_headroom ------

def test_nonfirst_short_sentence_final_gets_fluidity():
    # line0 full (11 tiles), line1 short+sentence-final (middle), line2 final.
    e = _e('A B C D E F G H I J K', '<$FFFC>', 'Ok.', '<$FFFC>', 'final words here now')
    codes = _codes(simulate_entry(e, PROF_DIALOGUE)[0])
    assert 'fluidity_headroom' in codes
    assert 'low_line_usage' not in codes


# --- Rule 2: the per-scen budget caps how many may stay short -----------------

def _fh_entry():
    return {'profile': 'DIALOGUE_12X4', 'status': 'POLISHED',
            'issues': [{'code': 'fluidity_headroom', 'severity': 'info', 'detail': {}}]}


def test_budget_is_floor_ten_percent_and_caps_excess():
    # 25 entries -> budget = floor(2.5) = 2. Five fluidity lines: 2 kept, 3 flagged.
    reports = [_fh_entry() for _ in range(5)]
    used, budget = _apply_fluidity_budget(reports, num_entries=25)
    assert budget == 2 and used == 2
    kept = sum(any(i['code'] == 'fluidity_headroom' for i in r['issues']) for r in reports)
    flagged = [r for r in reports if any(i['code'] == 'low_line_usage' for i in r['issues'])]
    assert kept == 2
    assert len(flagged) == 3
    assert all(r['status'] != 'POLISHED' for r in flagged), "over-budget lines must block POLISHED"


def test_budget_within_limit_keeps_all():
    reports = [_fh_entry() for _ in range(2)]
    used, budget = _apply_fluidity_budget(reports, num_entries=50)  # budget 5
    assert used == 2
    assert all(any(i['code'] == 'fluidity_headroom' for i in r['issues']) for r in reports)
