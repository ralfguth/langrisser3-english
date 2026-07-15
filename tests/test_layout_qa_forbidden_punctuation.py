"""test_layout_qa_forbidden_punctuation.py — TDD for the spoken-punctuation gate.

Project-wide hard rule (user 2026-06-16): the colon `:`, semicolon `;`, and
em-dash `—` must NOT appear ANYWHERE in scen/plot content — dialogue OR
narration. They are written-prose typography that breaks a localized,
spoken-feeling read (and the em-dash isn't even in the tile map, so the font
drops it silently). Allowed throughout: `.` `,` `…` `?` `!` `'`. Location
labels use comma (apposition) / hyphen (compound), never `:;—`.

`detect_forbidden_punctuation(entry)` is the source-level pass that flags them.
Everything it finds is a `forbidden_punctuation` ERROR; `detail.reason`
distinguishes the three marks: `colon`, `semicolon`, `em_dash`.

The hard requirement: the three forbidden marks are caught wherever they fall in
real prose, while the legitimate constructs that look similar — the regular
hyphen `-` in a compound, the ellipsis `…`, and anything inside a control code
or the protagonist token — are NOT false-flagged.
"""

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.parser import Entry, _tokenize  # noqa: E402
from layout_qa.simulator import detect_forbidden_punctuation  # noqa: E402


def _entry(raw: str) -> Entry:
    return Entry(scen_id='scenTEST', index=0, raw=raw,
                 terminator='FFFE', segments=_tokenize(raw))


def _reasons(raw: str):
    return sorted(i.detail.get('reason')
                  for i in detect_forbidden_punctuation(_entry(raw)))


def _is_clean(raw: str) -> bool:
    return detect_forbidden_punctuation(_entry(raw)) == []


# ---------------------------------------------------------------------------
# positives — the three forbidden marks MUST be flagged (severity 'error')
# ---------------------------------------------------------------------------

def test_semicolon_flagged():
    assert _reasons('He fought well; he still fell.<$FFFE>') == ['semicolon']


def test_colon_flagged():
    assert _reasons("There's one rule: never retreat.<$FFFE>") == ['colon']


def test_em_dash_flagged():
    assert _reasons('Forgive me—I must go.<$FFFE>') == ['em_dash']


def test_real_corpus_line_semicolon():
    # scen038[35] — the live defect this gate is built to catch.
    raw = ("It can't be helped.<$FFFD>Geier's off chasing the<$FFFC>"
           "deserters; Emerick rode<$FFFC>to take Baron Torrand.<$FFFE>")
    assert _reasons(raw) == ['semicolon']


def test_multiple_marks_all_reported():
    assert _reasons('two modes: Map and Battle; pick one.<$FFFE>') == [
        'colon', 'semicolon']


def test_code_and_severity():
    issues = detect_forbidden_punctuation(_entry('He fell; she lived.<$FFFE>'))
    assert issues and all(i.code == 'forbidden_punctuation'
                          and i.severity == 'error' for i in issues)


# ---------------------------------------------------------------------------
# negatives — legitimate constructs that must NOT be flagged
# ---------------------------------------------------------------------------

def test_clean_dialogue():
    assert _is_clean("I won't yield to sorrow, not yet.<$FFFE>")


def test_regular_hyphen_compound_label_is_clean():
    # location-label hyphen compound (US-Mexico-style) uses a normal hyphen
    assert _is_clean('Rigüler-Barral Border<$FFFF>')


def test_ellipsis_is_clean():
    assert _is_clean('Go on ahead… I will catch up soon…<$FFFE>')


def test_protagonist_token_and_codes_are_clean():
    # the token and control codes never carry text-class chars to scan
    assert _is_clean('<$F600><$0000>, come!<$FFFC>We should hurry too!<$FFFE>')
