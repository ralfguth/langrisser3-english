"""test_layout_qa_parser.py — unit + corpus round-trip for parser.

Phase 1 of the Layout QA. The parser must cover every scen*E.txt
in the corpus without exceptions and produce terminator counts
consistent with the investigation:

    Total <$FFFE> occurrences : 10163
    Total <$FFFF> occurrences : 2948

Note: one entry in `scen042E.txt` has BOTH `<$FFFE>` and `<$FFFF>` at
its tail. Per our convention (terminator = last FFFE/FFFF ctrl in
order), that entry is classified as FFFF-terminated. So the count of
entries-with-FFFE-terminator is 10162, but the count of FFFE
occurrences in raw text equals the investigation's 10163.
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.parser import (  # noqa: E402
    parse_scenario, parse_all, _tokenize, Entry, Segment, PROTAGONIST_TOKEN,
)


SCRIPTS_DIR = PROJ / 'scripts' / 'en'


# ---------------------------------------------------------------------------
# Unit tests — _tokenize
# ---------------------------------------------------------------------------

def test_plain_text_only():
    segs = _tokenize('Hello world')
    assert segs == [Segment('text', 'Hello world')]


def test_terminator_only():
    segs = _tokenize('<$FFFE>')
    assert segs == [Segment('ctrl', '<$FFFE>')]


def test_text_then_terminator():
    segs = _tokenize('Tiaris<$FFFF>')
    assert segs == [
        Segment('text', 'Tiaris'),
        Segment('ctrl', '<$FFFF>'),
    ]


def test_protagonist_token_literal():
    """<$F600><$0000> normalized to PROTAGONIST_TOKEN as one 'token' segment."""
    segs = _tokenize('Sir <$F600><$0000>!')
    assert segs == [
        Segment('text', 'Sir '),
        Segment('token', PROTAGONIST_TOKEN),
        Segment('text', '!'),
    ]


def test_diehardt_marker_normalized_to_protagonist_token():
    """[diehardt's name] → token PROTAGONIST_TOKEN (case-insensitive)."""
    for marker in ("[diehardt's name]", "[Diehardt's Name]", "[DIEHARDT'S NAME]"):
        segs = _tokenize(f'Hi {marker}.')
        assert any(s.kind == 'token' and s.value == PROTAGONIST_TOKEN
                   for s in segs), f'failed on {marker!r}'


def test_multi_word_ctrl_code():
    """<$XXXXYYYY> single bracketed token kept as one ctrl segment."""
    segs = _tokenize('<$F600F702>')
    assert segs == [Segment('ctrl', '<$F600F702>')]


def test_fffc_and_fffd_inside_entry():
    """`<$FFFC>` (line break) and `<$FFFD>` (balloon break) preserved as ctrl."""
    segs = _tokenize('Line 1<$FFFC>Line 2<$FFFD>Balloon 2<$FFFE>')
    kinds = [s.kind for s in segs]
    assert kinds == ['text', 'ctrl', 'text', 'ctrl', 'text', 'ctrl']
    assert [s.value for s in segs if s.kind == 'ctrl'] == [
        '<$FFFC>', '<$FFFD>', '<$FFFE>',
    ]


# ---------------------------------------------------------------------------
# Unit tests — Entry / parse_scenario
# ---------------------------------------------------------------------------

def test_parse_scenario_indexing(tmp_path: Path):
    """Entry indexes are zero-based and only count non-blank lines."""
    f = tmp_path / 'scen999E.txt'
    f.write_text('A<$FFFF>\n\nB<$FFFE>\n', encoding='utf-8')
    entries = parse_scenario(f)
    assert len(entries) == 2
    assert entries[0].index == 0
    assert entries[0].scen_id == 'scen999'
    assert entries[1].index == 1


def test_terminator_with_trailing_whitespace(tmp_path: Path):
    """`<$FFFE> ` (trailing space) still detected as FFFE-terminated."""
    f = tmp_path / 'scen999E.txt'
    f.write_text('Urggh!<$FFFE> \n', encoding='utf-8')
    entries = parse_scenario(f)
    assert len(entries) == 1
    assert entries[0].terminator == 'FFFE'


def test_terminator_fffe_then_ffff_is_dialogue(tmp_path: Path):
    """`<$FFFE><$FFFF>` at the tail = dialogue (FFFE is the message terminator;
    the trailing FFFF is just the string terminator, the JP last-entry pattern).
    A pure label is FFFF with NO preceding FFFE."""
    f = tmp_path / 'scen999E.txt'
    f.write_text(
        'Right!<$FFFE><$FFFF>\n'   # dialogue + trailing string terminator
        'Dieharte<$FFFF>\n',       # pure nameplate label
        encoding='utf-8',
    )
    entries = parse_scenario(f)
    assert entries[0].terminator == 'FFFE'   # dialogue, not a label
    assert entries[1].terminator == 'FFFF'   # pure label


def test_entry_without_terminator(tmp_path: Path):
    """Lines that lack any FFFE/FFFF get empty terminator (rare in corpus)."""
    f = tmp_path / 'scen999E.txt'
    f.write_text('text with no terminator\n', encoding='utf-8')
    entries = parse_scenario(f)
    assert entries[0].terminator == ''


# ---------------------------------------------------------------------------
# Corpus round-trip — checkpoint per implementation plan
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def corpus_entries():
    if not SCRIPTS_DIR.exists():
        pytest.skip(f'scripts/en/ missing at {SCRIPTS_DIR}')
    return parse_all(SCRIPTS_DIR)


def test_corpus_entry_count(corpus_entries):
    """Investigation observed 2948 FFFF + 10163 FFFE = 13111 raw occurrences.
    One entry (scen042E:107) has both FFFE and FFFF at tail; we count it
    as a single FFFF-terminated entry. So entry count = 13110.
    """
    assert len(corpus_entries) == 13110


def test_corpus_terminator_distribution(corpus_entries):
    """Semantic terminator (FFFE wins when an entry ends `<$FFFE><$FFFF>`):
        FFFE-terminated entries = 10163  (dialogue/narration)
        FFFF-terminated entries = 2947   (pure labels: nameplate / location)
        no-terminator entries   = 0

    Updated 2026-06-14: restoring the trailing <$FFFF> to 60 dialogue last
    entries did NOT move them to FFFF — they keep FFFE (the message terminator).
    The +1 FFFE / -1 FFFF vs the old 10162/2948 is scen042, whose last entry
    already carried the trailing FFFF and was previously MISclassified as a
    label; it is now correctly FFFE (dialogue).
    """
    counts = {'FFFE': 0, 'FFFF': 0, '': 0}
    for e in corpus_entries:
        counts[e.terminator] = counts.get(e.terminator, 0) + 1
    assert counts['FFFE'] == 10163
    assert counts['FFFF'] == 2947
    assert counts[''] == 0


def test_corpus_raw_terminator_occurrences(corpus_entries):
    """Raw-text occurrence counts must match the investigation exactly."""
    total_fffe = sum(e.raw.count('<$FFFE>') for e in corpus_entries)
    total_ffff = sum(e.raw.count('<$FFFF>') for e in corpus_entries)
    assert total_fffe == 10163
    # 2948 + 60: trailing <$FFFF> restored to the last entry of 60 sections
    # (2026-06-14, JP parity) — raw substring occurrences. The SEMANTIC
    # terminator of those entries stays FFFE (see parser._terminator_of), so the
    # terminator/profile distributions below are unchanged.
    assert total_ffff == 3008


def test_corpus_scen_id_format(corpus_entries):
    """Every entry's scen_id matches 'scen' + 3-digit number."""
    import re
    pat = re.compile(r'^scen\d{3}$')
    bad = [e.scen_id for e in corpus_entries if not pat.match(e.scen_id)]
    assert not bad, f'unexpected scen_ids: {set(bad)}'


def test_corpus_segments_nonempty(corpus_entries):
    """Every entry produces at least one segment (no blank-line slips through)."""
    bad = [e for e in corpus_entries if not e.segments]
    assert not bad, f'{len(bad)} entries with empty segments'
