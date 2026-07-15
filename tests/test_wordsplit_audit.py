#!/usr/bin/env python3
"""test_wordsplit_audit.py — mechanics of the mid-word <$FFFC> audit routine.

The audit is an LLM routine, NOT a gate: a deterministic tool surfaces every
<$FFFC> break with context and flags the concat-suspicious ones; an LLM then
eyeballs each to separate a real mid-word split ("Empi<$FFFC>re" = "Empire")
from a legitimate two-word break whose halves coincidentally concatenate into
a word ("the<$FFFC>sword" -> "thesword", not a word -> clean; "come<$FFFC>back"
-> "comeback" IS a word but "come back" is legit -> the LLM keeps it).

Only the MECHANICS are pinned here (finding breaks + the concat/orphan flag).
The split-vs-legit JUDGMENT is intentionally left to the LLM (it is the
ambiguous part that unit tests cannot decide).
"""

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from wordsplit_audit import (  # noqa: E402
    iter_fffc_breaks, classify_break, audit_file, load_wordset,
)

# A tiny deterministic wordset so the mechanics tests don't depend on the
# bundled dictionary.
WS = {'empire', 'consider', 'your', 'afraid', 'suggestion', 'cooperate',
      'the', 'sword', 'come', 'back', 'comeback'}


def test_iter_breaks_finds_each_fffc_with_fragments():
    raw = 'We saved the<$FFFC>Empi<$FFFC>re now<$FFFE>'
    breaks = iter_fffc_breaks(raw)
    assert len(breaks) == 2
    assert (breaks[0]['left_frag'], breaks[0]['right_frag']) == ('the', 'Empi')
    assert (breaks[1]['left_frag'], breaks[1]['right_frag']) == ('Empi', 're')


def test_iter_breaks_strips_control_codes_from_fragments():
    # The protagonist token / codes must not be mistaken for word characters.
    raw = '<$F600><$0000> I am af<$FFFC>raid now<$FFFE>'
    b = iter_fffc_breaks(raw)[0]
    assert b['left_frag'] == 'af' and b['right_frag'] == 'raid'


def test_classify_concat_is_a_word_flags_split():
    sus, reason = classify_break('Empi', 're', WS)        # -> "empire"
    assert sus and reason == 'concat'
    sus, reason = classify_break('af', 'raid', WS)         # -> "afraid"
    assert sus and reason == 'concat'


def test_classify_two_whole_words_not_flagged_when_join_not_a_word():
    # "the"+"sword" = "thesword" (not a word) -> a clean two-word break.
    sus, _ = classify_break('the', 'sword', WS)
    assert not sus


def test_classify_one_letter_orphan_flagged():
    sus, reason = classify_break('Empir', 'e', WS)
    assert sus and reason == 'orphan'


def test_classify_standalone_a_i_o_not_orphan():
    # "a"/"i"/"o" are legitimately whole words, never split markers.
    assert not classify_break('have', 'a', WS)[0]


def test_audit_file_flags_real_split_not_clean_break(tmp_path):
    f = tmp_path / 'scen999E.txt'
    f.write_text(
        'Name<$FFFF>\n'
        'I need to cons<$FFFC>ider<$FFFE>\n'    # real split -> "consider"
        'Take up the<$FFFC>sword<$FFFE>\n',     # clean two-word break
        encoding='utf-8')
    findings = audit_file(f, WS)
    ctx = {(fd['line'], fd['reason']) for fd in findings}
    # the split line is flagged; the clean break is not
    assert any('cons' in fd['context'] and fd['reason'] == 'concat'
               for fd in findings), findings
    assert not any('the' in fd['context'] and 'sword' in fd['context']
                   for fd in findings), findings


def test_audit_all_breaks_returns_every_fffc(tmp_path):
    f = tmp_path / 'scen999E.txt'
    f.write_text('Name<$FFFF>\nTake up the<$FFFC>sword<$FFFE>\n', encoding='utf-8')
    assert len(audit_file(f, WS, all_breaks=True)) == 1
    assert audit_file(f, WS, all_breaks=False) == []   # not suspicious


def test_bundled_wordlist_loads_and_has_common_words():
    ws = load_wordset()
    assert {'empire', 'consider', 'afraid'} <= ws
