"""Tests for tools/grammar_audit.py — the deterministic grammar/punctuation gate.

Two layers:
  1. Unit tests pin the analyzer's detection (defect samples flag; the corpus's
     intentional forms — onomatopoeia reduplication, sentence-opening '…',
     comma-before-wrap — do NOT flag). These guard the analyzer itself.
  2. The corpus gate asserts zero error-level findings across scripts/en. This
     is the Red→Green driver for the grammar-fix pass and the permanent
     regression flag thereafter.
"""
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / 'tools'))

import grammar_audit as ga  # noqa: E402


def _rules(raw):
    return {f.rule for f in ga.iter_line_findings(raw, 'x.txt', 1)}


def _sev(raw):
    return {f.rule: f.severity for f in ga.iter_line_findings(raw, 'x.txt', 1)}


# --- positives: real defects must flag -------------------------------------
@pytest.mark.parametrize('raw,rule', [
    ('ATK,DEF-25% /group', 'comma_no_space'),
    ('<$F600><$0000>,please hurry too.', 'comma_no_space'),
    ('U,uhh…<$FFFE>', 'comma_no_space'),
    ('What can some so called thief hope to do?', 'open_compound'),
    ('run of the mill thieves<$FFFE>', 'open_compound'),
    ('the east gate keeper<$FFFE>', 'open_compound'),
    ('Flood gate… flood gate…<$FFFE>', 'open_compound'),
    ('your father in law<$FFFE>', 'open_compound'),
    ('I I am not… dead yet…<$FFFE>', 'dup_func_word'),
    ('gains blessing; casts Turn Undead.<$FFFF>', 'semicolon'),
    ('So they managed to escape …<$FFFE>', 'space_before_ellipsis'),
    ('word , next', 'space_before_punct'),
    # outright misspellings (no valid reading in this corpus)
    ('Surrond them!<$FFFE>', 'misspelling'),
    ('Godess…<$FFFE>', 'misspelling'),
    ('seal your<$FFFC>fate! En Guard!<$FFFE>', 'misspelling'),
    # possessive "its" before a pronoun must be the contraction "it's"
    ('Oh, its you?<$FFFE>', 'its_contraction'),
    ('Wait, its me.<$FFFE>', 'its_contraction'),
])
def test_defect_flags(raw, rule):
    assert rule in _rules(raw), f'{rule!r} not flagged in {raw!r}'


def test_defect_severities_are_error():
    for raw in ('ATK,DEF', 'so called thief', 'I I am', 'escape …', 'word !', 'a; b',
                'Surrond them', 'En Guard!', 'its you'):
        sev = _sev(raw)
        assert sev and all(v == 'error' for v in sev.values()), (raw, sev)


# --- negatives: intentional / legitimate forms must NOT flag ----------------
@pytest.mark.parametrize('raw', [
    'Heh heh heh.<$FFFE>',                 # laugh reduplication
    'Shika shika!<$FFFE>',                 # tribal chant
    'Ow ow, that hurt!<$FFFE>',            # pain reduplication
    'Z<$FE1E>Z<$FE0F>Z<$FE0F>…<$FFFE>',    # snore, codes between (not a dup)
    'Their spirits are high,<$FFFC>and they march.<$FFFE>',  # comma before wrap
    'Guh! …Looks like trouble.<$FFFE>',    # '…' opening a new sentence (after !)
    'arrive.<$FFFC>…We must hurry.<$FFFE>',  # '…' opening after a wrap
    '1,000P reward.<$FFFE>',               # thousands separator (digit, not letter)
    'But its body is still missing!<$FFFE>',  # possessive its + noun (not a pronoun)
    'It found its own way.<$FFFE>',        # possessive its + noun
    'Stand on guard at the gate.<$FFFE>',  # 'guard' alone is a real word
    'The castle guard saw nothing.<$FFFE>',  # ditto
])
def test_intentional_forms_do_not_flag_error(raw):
    errs = [f for f in ga.iter_line_findings(raw, 'x.txt', 1) if f.severity == 'error']
    assert not errs, f'false positive: {[ (f.rule,f.text) for f in errs ]}'


def test_dup_only_function_words():
    # onomatopoeia/emphasis doubling is never an error; a function word is.
    assert 'dup_func_word' not in _rules('Now now, calm down.')
    assert 'dup_func_word' in _rules('the the castle')
    # words that validly double must NOT flag
    assert 'dup_func_word' not in _rules("Now that that's settled, let's go.")
    assert 'dup_func_word' not in _rules('The service was so so.')


# --- corpus gate: the Red→Green driver and permanent flag -------------------
def test_corpus_has_no_grammar_errors():
    findings = ga.audit()
    errors = [f for f in findings if f.severity == 'error']
    if errors:
        lines = '\n'.join(f'  [{f.rule}] {f.file}:{f.line}  {f.text!r}' for f in errors)
        pytest.fail(f'{len(errors)} grammar error(s):\n{lines}')
