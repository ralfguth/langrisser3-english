"""test_layout_qa_bottom_align.py — empty <$FFFC> lines are bottom-align padding.

The opening-movie narration (scen122/123, voiced by the goddess Lushiris)
renders in a 16-wide, 5-line balloon and is BOTTOM-ALIGNED: when the text is
shorter than the balloon, the missing lines are empty `<$FFFC>` lines placed ON
TOP, so the text sits at the bottom, ending at the `<$FFFD>` (the balloon end).

Those leading empty lines are PADDING, not under-filled prose, so they must NOT
trip `low_line_usage`. A genuinely thin NON-empty line still must.
"""

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.parser import Entry, _tokenize  # noqa: E402
from layout_qa.simulator import simulate_entry  # noqa: E402

SPEC = {'name': 'NARRATION_16X5', 'width': 16, 'max_lines': 5}


def _entry(raw: str) -> Entry:
    return Entry(scen_id='scenTEST', index=0, raw=raw,
                 terminator='FFFE', segments=_tokenize(raw))


def _codes(raw: str):
    issues, _ = simulate_entry(_entry(raw), SPEC)
    return [i.code for i in issues]


def test_empty_leading_line_is_not_low_line_usage():
    # one empty line on top (bottom-align), then two well-filled lines
    raw = ('<$FFFC>This narration line fills well<$FFFC>'
           'and a second full line sits here.<$FFFE>')
    assert 'low_line_usage' not in _codes(raw)


def test_two_empty_leading_lines_exempt():
    raw = ('<$FFFC><$FFFC>This narration line fills well<$FFFC>'
           'and a second full line sits here.<$FFFE>')
    assert 'low_line_usage' not in _codes(raw)


def test_nonempty_thin_line_still_flags():
    # a real thin, non-sentence-final, non-empty line must still be caught
    raw = '<$FFFC>tiny<$FFFC>and a second full line sits here.<$FFFE>'
    assert 'low_line_usage' in _codes(raw)
