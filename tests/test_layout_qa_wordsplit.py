"""test_layout_qa_wordsplit.py — TDD for source-text wrap-defect detection.

A mechanical fixed-column hard-wrap (the scen025 codex regression)
drops an explicit `<$FFFC>` inside a word ("Excelle<$FFFC>ncy") and
eats the space after punctuation ("order,Varna"). Both render broken
in-game, yet the width-based wrap simulator passes them because it
trusts every explicit `<$FFFC>` as deliberate.

`detect_source_wrap_defects(entry)` is the source-level pass that
catches them. Everything it finds is a `broken_word_wrap` ERROR;
`detail.reason` distinguishes the three fingerprints:

  - fffc_splits_word
  - fffc_splits_contraction
  - missing_space_after_punctuation

The hard requirement of these tests: real defects are caught, and the
legitimate constructs that LOOK similar (contractions at a line end,
accented names, single-letter stutters/initials, ordinals, leading
ellipsis) are NOT false-flagged.
"""

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.parser import Entry, _tokenize  # noqa: E402
from layout_qa.simulator import detect_source_wrap_defects  # noqa: E402


def _entry(raw: str) -> Entry:
    return Entry(scen_id='scenTEST', index=0, raw=raw,
                 terminator='FFFE', segments=_tokenize(raw))


def _reasons(raw: str):
    return sorted(i.detail.get('reason') for i in detect_source_wrap_defects(_entry(raw)))


def _is_clean(raw: str) -> bool:
    return detect_source_wrap_defects(_entry(raw)) == []


# ---------------------------------------------------------------------------
# positives — real defects that MUST be flagged (all severity 'error')
# ---------------------------------------------------------------------------

def test_fffc_splits_word_one_letter_suffix():
    # "Empire" cut as "Empir" / "e"
    assert _reasons('Cooperate with the<$FFFC>Empir<$FFFC>e!?<$FFFE>') == ['fffc_splits_word']


def test_fffc_splits_word_one_letter_prefix():
    # "the" cut as "th" / "e"
    assert 'fffc_splits_word' in _reasons('reducing th<$FFFC>e number<$FFFE>')


def test_fffc_splits_contraction():
    # "can't" cut as "can" / "'t"
    assert _reasons("you can<$FFFC>'t win<$FFFE>") == ['fffc_splits_contraction']


def test_missing_space_after_comma():
    assert _reasons('This is an order,Varna.<$FFFE>') == ['missing_space_after_punctuation']


def test_missing_space_after_period():
    assert _reasons('I underestimated them.It seems so.<$FFFE>') == ['missing_space_after_punctuation']


def test_missing_space_after_bang():
    assert _reasons('All wiped out!I see.<$FFFE>') == ['missing_space_after_punctuation']


def test_severity_is_error():
    issues = detect_source_wrap_defects(_entry('order,Varna here<$FFFE>'))
    assert issues and all(i.code == 'broken_word_wrap' and i.severity == 'error'
                          for i in issues)


# ---------------------------------------------------------------------------
# negatives — legitimate constructs that must NOT be flagged
# ---------------------------------------------------------------------------

def test_clean_break_between_two_words():
    assert _is_clean('I will protect<$FFFC>the kingdom now.<$FFFE>')


def test_clean_break_after_contraction_word():
    # left token "you're" ends in a contraction but is a whole word
    assert _is_clean("you're<$FFFC>safe now.<$FFFE>")


def test_clean_break_before_accented_name():
    # "Böser" — the accent must not make "B" look like a 1-letter fragment
    assert _is_clean('report to Master<$FFFC>Böser at once.<$FFFE>')


def test_clean_single_letter_stutter_not_glue():
    # "T-That" rendered "T.That" — single letter before the mark is a
    # stutter/initial, not a lost space
    assert _is_clean('T.That cannot be!<$FFFE>')


def test_clean_acronym_with_periods():
    assert _is_clean('the N.C.E! is here<$FFFE>')


def test_clean_leading_ellipsis():
    assert _is_clean('...Father, your foe is beaten.<$FFFE>')


def test_clean_decimal_number():
    assert _is_clean('the ratio is 3.14 exactly<$FFFE>')


def test_clean_single_letter_words_a_i_o():
    assert _is_clean('it is a<$FFFC>kingdom, and I<$FFFC>see it<$FFFE>')


def test_clean_break_before_opening_quote():
    # <$FFFC> before a quoted phrase opens with ' + lowercase, but it is an
    # opening quote, NOT a split contraction
    assert _is_clean("you live up to the name<$FFFC>'genius strategist'.<$FFFE>")


def test_protagonist_token_adjacent_is_clean():
    # the <$F600><$0000> token is its own segment; a break beside it is fine
    assert _is_clean('Sir <$F600><$0000>,<$FFFC>well done.<$FFFE>')
