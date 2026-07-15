"""test_layout_qa_classifier.py — unit + corpus coverage.

Checkpoint per implementation plan: zero `UNKNOWN` profiles when run
over the full corpus of 125 scen files.
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.parser import Entry, Segment, parse_all  # noqa: E402
from layout_qa.classifier import (  # noqa: E402
    classify_entries, ClassifierState,
    LABEL_CHARACTER_12X1, LABEL_LOCATION_16X1,
    OBJECTIVE_16X5, NARRATION_16X5, DIALOGUE_12X4, UNKNOWN,
    BULLET_PATTERN, visible_text,
)


SCRIPTS_DIR = PROJ / 'scripts' / 'en'


def _make_entry(idx: int, raw: str, terminator: str = '') -> Entry:
    """Build a minimal Entry with naive single-text-segment, used for
    classifier transition tests where the tokenization details don't
    matter."""
    return Entry(
        scen_id='scenTEST', index=idx, raw=raw,
        terminator=terminator,
        segments=[Segment('text', raw)],
    )


# ---------------------------------------------------------------------------
# Bullet detector
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('text', [
    '•Defeat all enemies',
    ' •Death of someone',
    '*Victory Conditions',
    '* Conditions',
])
def test_bullet_pattern_matches_real_prefixes(text):
    assert BULLET_PATTERN.match(text) is not None


@pytest.mark.parametrize('text', [
    'Hello world',
    'Tiaris',
    'No bullet here',
    '',
])
def test_bullet_pattern_does_not_match_non_bullet(text):
    assert BULLET_PATTERN.match(text) is None


# ---------------------------------------------------------------------------
# visible_text helper
# ---------------------------------------------------------------------------

def test_visible_text_excludes_ctrl_and_token():
    e = Entry(
        scen_id='scenTEST', index=0,
        raw=' • Defeat enemies<$FFFE>',
        terminator='FFFE',
        segments=[
            Segment('text', ' • Defeat enemies'),
            Segment('ctrl', '<$FFFE>'),
        ],
    )
    assert visible_text(e) == ' • Defeat enemies'


# ---------------------------------------------------------------------------
# State machine transitions
# ---------------------------------------------------------------------------

def test_initial_labels_distinguish_character_vs_location():
    """Initial FFFF chain followed by FFFE: all-but-last are CHARACTER
    nameplates (12-tile budget), last is the LOCATION title (16-tile budget)."""
    entries = [
        _make_entry(0, 'Tiaris<$FFFF>', 'FFFF'),
        _make_entry(1, 'Liffany<$FFFF>', 'FFFF'),
        _make_entry(2, 'Castle<$FFFF>', 'FFFF'),     # last in chain — LOCATION
        _make_entry(3, ' Hello.<$FFFE>', 'FFFE'),   # first dialogue
    ]
    classes = classify_entries(entries)
    assert classes[0].profile == LABEL_CHARACTER_12X1
    assert classes[0].semantic_subtype == 'CHARACTER_NAME'
    assert classes[1].profile == LABEL_CHARACTER_12X1
    assert classes[2].profile == LABEL_LOCATION_16X1
    assert classes[2].semantic_subtype == 'LOCATION'
    assert classes[3].profile == DIALOGUE_12X4
    # `state` is the state DURING classification — entry 3 is classified
    # while still in INITIAL_LABELS; the transition to SCENE_12X4 fires
    # as it is classified, so subsequent entries see SCENE_12X4.


def test_trailing_ffff_at_eof_is_location():
    """A file that ends with FFFF (no following entry) — treat the
    last as LOCATION since there's nothing after to keep it 'roster'."""
    entries = [
        _make_entry(0, 'Tiaris<$FFFF>', 'FFFF'),
        _make_entry(1, 'Castle<$FFFF>', 'FFFF'),
    ]
    classes = classify_entries(entries)
    assert classes[0].profile == LABEL_CHARACTER_12X1
    assert classes[1].profile == LABEL_LOCATION_16X1


def test_initial_scenario_marker_transitions_to_intro():
    """First FFFE entry that matches SCENARIO_PATTERN drives NARRATION.
    Roster of multiple character names before the SCENARIO header
    (matches the real corpus structure)."""
    entries = [
        _make_entry(0, 'Tiaris<$FFFF>', 'FFFF'),
        _make_entry(1, 'Liffany<$FFFF>', 'FFFF'),
        _make_entry(2, 'Lewin<$FFFF>', 'FFFF'),
        Entry(
            scen_id='scenTEST', index=3,
            raw='<$0000><$FFFC>  <$0000>SCENARIO-19<$FFFC>Subtitle<$FFFE>',
            terminator='FFFE',
            segments=[
                Segment('ctrl', '<$0000>'),
                Segment('ctrl', '<$FFFC>'),
                Segment('text', '  '),
                Segment('ctrl', '<$0000>'),
                Segment('text', 'SCENARIO-19'),
                Segment('ctrl', '<$FFFC>'),
                Segment('text', 'Subtitle'),
                Segment('ctrl', '<$FFFE>'),
            ],
        ),
        _make_entry(4, 'More narration here<$FFFE>', 'FFFE'),
    ]
    classes = classify_entries(entries)
    assert classes[0].profile == LABEL_CHARACTER_12X1
    assert classes[1].profile == LABEL_CHARACTER_12X1
    assert classes[2].profile == LABEL_CHARACTER_12X1
    assert classes[3].profile == NARRATION_16X5
    assert classes[4].profile == NARRATION_16X5


def test_initial_bullet_transitions_to_objectives():
    """First FFFE with bullet drives OBJECTIVE."""
    entries = [
        _make_entry(0, 'Tiaris<$FFFF>', 'FFFF'),
        _make_entry(1, '•Defeat all enemies<$FFFE>', 'FFFE'),
        _make_entry(2, ' •Death of someone<$FFFE>', 'FFFE'),
    ]
    classes = classify_entries(entries)
    assert classes[0].profile == LABEL_CHARACTER_12X1
    assert classes[1].profile == OBJECTIVE_16X5
    assert classes[2].profile == OBJECTIVE_16X5


def test_initial_to_scene_dialogue_when_no_marker():
    """FFFE with no SCENARIO and no bullet → assume dialogue (continuation)."""
    entries = [
        _make_entry(0, 'Tiaris<$FFFF>', 'FFFF'),
        _make_entry(1, 'Location<$FFFF>', 'FFFF'),
        _make_entry(2, ' Hello there.<$FFFE>', 'FFFE'),
    ]
    classes = classify_entries(entries)
    assert classes[0].profile == LABEL_CHARACTER_12X1
    assert classes[1].profile == LABEL_LOCATION_16X1
    assert classes[2].profile == DIALOGUE_12X4


def test_objectives_ffff_triggers_scene():
    entries = [
        _make_entry(0, 'Char<$FFFF>', 'FFFF'),
        _make_entry(1, '•Goal<$FFFE>', 'FFFE'),
        _make_entry(2, 'Location<$FFFF>', 'FFFF'),  # location label
        _make_entry(3, 'Dialog!<$FFFE>', 'FFFE'),
    ]
    classes = classify_entries(entries)
    assert classes[2].profile == LABEL_LOCATION_16X1
    assert classes[3].profile == DIALOGUE_12X4


def test_scenario_intro_ffff_triggers_scene():
    entries = [
        _make_entry(0, 'Char<$FFFF>', 'FFFF'),
        Entry(
            scen_id='scenTEST', index=1,
            raw='<$0000><$FFFC>  <$0000>SCENARIO-19<$FFFC>X<$FFFE>',
            terminator='FFFE',
            segments=[Segment('text', '<$0000><$FFFC>  <$0000>SCENARIO-19<$FFFC>X')],
        ),
        _make_entry(2, 'more intro<$FFFE>', 'FFFE'),
        _make_entry(3, 'Location<$FFFF>', 'FFFF'),
        _make_entry(4, 'Dialog!<$FFFE>', 'FFFE'),
    ]
    # The SCENARIO entry needs the regex to actually match against its raw.
    # We construct the raw explicitly above to satisfy SCENARIO_PATTERN.
    classes = classify_entries(entries)
    assert classes[1].profile == NARRATION_16X5
    assert classes[2].profile == NARRATION_16X5
    assert classes[3].profile == LABEL_LOCATION_16X1
    assert classes[4].profile == DIALOGUE_12X4


def test_scene_state_ffff_stays_label():
    """Mid-file FFFF (e.g. location change) keeps SCENE_12X4 state."""
    entries = [
        _make_entry(0, 'A<$FFFF>', 'FFFF'),
        _make_entry(1, ' Dialog 1<$FFFE>', 'FFFE'),
        _make_entry(2, 'New Location<$FFFF>', 'FFFF'),
        _make_entry(3, ' Dialog 2<$FFFE>', 'FFFE'),
    ]
    classes = classify_entries(entries)
    assert classes[2].profile == LABEL_LOCATION_16X1
    assert classes[3].profile == DIALOGUE_12X4
    assert classes[3].state == ClassifierState.SCENE_12X4.value


def test_unknown_when_no_terminator():
    entries = [_make_entry(0, 'orphan text', '')]
    classes = classify_entries(entries)
    assert classes[0].profile == UNKNOWN


# ---------------------------------------------------------------------------
# Corpus coverage — CHECKPOINT
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def corpus_classifications():
    if not SCRIPTS_DIR.exists():
        pytest.skip(f'scripts/en/ missing at {SCRIPTS_DIR}')
    all_entries = parse_all(SCRIPTS_DIR)
    # Group by scen_id and classify each scen separately (state resets).
    by_scen: dict[str, list] = {}
    for e in all_entries:
        by_scen.setdefault(e.scen_id, []).append(e)
    out = []
    for scen_id in sorted(by_scen):
        out.extend(classify_entries(by_scen[scen_id]))
    return out


def test_corpus_zero_unknown(corpus_classifications):
    """Phase 1 checkpoint: the classifier must cover the entire corpus."""
    unknowns = [c for c in corpus_classifications if c.profile == UNKNOWN]
    assert not unknowns, f'{len(unknowns)} UNKNOWN classifications in corpus'


def test_corpus_profile_distribution(corpus_classifications):
    """Locked snapshot — alerts if classifier rules drift on the corpus.

    Sum across profiles must equal the 13110 corpus entries. The split
    between LABEL_CHARACTER_12X1 and LABEL_LOCATION_16X1 is checked
    separately because the lookahead heuristic is meaningful.
    """
    from collections import Counter
    counts = Counter(c.profile for c in corpus_classifications)
    label_chars = counts[LABEL_CHARACTER_12X1]
    label_locs = counts[LABEL_LOCATION_16X1]
    # 2947 = the pure-FFFF (label) entries. NOT 3008: the 60 dialogue last
    # entries that got a restored trailing <$FFFF> (2026-06-14) stay FFFE-
    # terminated dialogue, not labels (see parser._terminator_of). The -1 vs the
    # old 2948 is scen042, previously MISclassified as a label, now dialogue.
    assert label_chars + label_locs == 2947, (
        f'total LABELs must equal 2947 pure-FFFF entries; got '
        f'CHARACTER={label_chars} + LOCATION={label_locs}'
    )
    # The two mid-scene SCENARIO briefings (scen068 idx85-89, scen110
    # idx109-112) classify as NARRATION_16X5 — title + recap body + the
    # objective list all render in the 16-wide briefing region, not the
    # 12x4 dialog balloon. 7 entries thus shift DIALOGUE_12X4 → NARRATION.
    # The layout-fitting sweep (2026-06-05) reformatted two victory/defeat
    # condition entries into the canonical `*Victory Conditions` + `•`-bullet
    # structure, so the classifier now reads them as OBJECTIVE_16X5 rather than
    # DIALOGUE_12X4 (2 entries shift DIALOGUE → OBJECTIVE; corpus total
    # unchanged). Counts updated from 9888/64 to 9886/66.
    # 2026-06-14: +1 (9886->9887) — scen042's last entry, previously
    # MISclassified as a LABEL (it carried a trailing <$FFFF>), is now correctly
    # DIALOGUE_12X4 after _terminator_of treats <$FFFE><$FFFF> as dialogue.
    # 2026-06-19: -2 (9887->9885) — scen006's victory objective [26] and
    # defeat condition [27] had lost their `•` bullets (rendering as plain
    # dialogue); restoring the bullets (matching JP `・` + the scen004 pattern)
    # reclassifies both as OBJECTIVE_16X5 (66->68). Corpus total unchanged.
    assert counts[DIALOGUE_12X4] == 9885, counts
    assert counts[NARRATION_16X5] == 210, counts
    assert counts[OBJECTIVE_16X5] == 68, counts
    # Each scen has at most one location label per cutscene transition,
    # so location count must be a small fraction of character count.
    assert label_locs > 0, 'expected some LOCATION labels'
    assert label_locs < label_chars, (
        f'expected fewer LOCATION than CHARACTER; got {label_locs} vs {label_chars}'
    )


# ---------------------------------------------------------------------------
# scen_overrides — per-scen profile remap (one-off scens like epilogues)
# ---------------------------------------------------------------------------

def _override_entries():
    """Roster of FFFF labels followed by FFFE narration — the scen124 shape."""
    return [
        Entry(scen_id='scen124', index=0, raw='Tiaris<$FFFF>',
              terminator='FFFF',
              segments=[Segment('text', 'Tiaris'), Segment('ctrl', '<$FFFF>')]),
        Entry(scen_id='scen124', index=1, raw='Liffany<$FFFF>',
              terminator='FFFF',
              segments=[Segment('text', 'Liffany'), Segment('ctrl', '<$FFFF>')]),
        Entry(scen_id='scen124', index=2, raw='Long bio body<$FFFE>',
              terminator='FFFE',
              segments=[Segment('text', 'Long bio body'),
                        Segment('ctrl', '<$FFFE>')]),
        Entry(scen_id='scen124', index=3, raw='Another bio<$FFFE>',
              terminator='FFFE',
              segments=[Segment('text', 'Another bio'),
                        Segment('ctrl', '<$FFFE>')]),
    ]


def test_scen_override_remaps_dialogue_only():
    """Overrides swap DIALOGUE_12X4 for the configured profile, leaving
    FFFF labels alone."""
    entries = _override_entries()
    overrides = {'scen124': {'dialogue_profile': NARRATION_16X5}}
    results = classify_entries(entries, scen_overrides=overrides)
    # FFFF labels — first two — keep their LABEL_CHARACTER classification
    # (lookahead: idx 0 sees idx 1 also FFFF → CHARACTER; idx 1 sees
    # idx 2 FFFE no marker → LOCATION in the default state machine).
    assert results[0].profile == LABEL_CHARACTER_12X1
    assert results[1].profile in (LABEL_CHARACTER_12X1, LABEL_LOCATION_16X1)
    # FFFE narrations — overridden from DIALOGUE_12X4 to NARRATION_16X5.
    assert results[2].profile == NARRATION_16X5
    assert results[3].profile == NARRATION_16X5
    # Provenance carries the override marker.
    assert 'overridden' in results[2].reason
    assert 'scen124' in results[2].reason


def test_scen_override_default_is_noop():
    """No override map → classifier unchanged."""
    entries = _override_entries()
    baseline = classify_entries(entries)
    with_empty = classify_entries(entries, scen_overrides={})
    assert [c.profile for c in baseline] == [c.profile for c in with_empty]


def test_scen_override_unknown_scen_is_noop():
    """Override targeting a different scen leaves this scen alone."""
    entries = _override_entries()
    overrides = {'scen999': {'dialogue_profile': NARRATION_16X5}}
    baseline = classify_entries(entries)
    with_unrelated = classify_entries(entries, scen_overrides=overrides)
    assert [c.profile for c in baseline] == \
        [c.profile for c in with_unrelated]


def test_scen_override_label_profile_forces_all_labels_character():
    """scen001 is unique: an 18-name CHARACTER roster runs straight into
    goddess narration, with NO trailing LOCATION label. The default state
    machine mis-types the last FFFF as LOCATION (it peeks a FFFE-no-marker
    next). A `label_profile` override pins every FFFF label to the given
    profile, fixing the roster boundary without touching the generic rule."""
    entries = [
        Entry(scen_id='scen001', index=0, raw='Tiaris<$FFFF>',
              terminator='FFFF',
              segments=[Segment('text', 'Tiaris'), Segment('ctrl', '<$FFFF>')]),
        Entry(scen_id='scen001', index=1, raw='Emerick<$FFFF>',
              terminator='FFFF',
              segments=[Segment('text', 'Emerick'),
                        Segment('ctrl', '<$FFFF>')]),
        Entry(scen_id='scen001', index=2, raw='Open your eyes.<$FFFE>',
              terminator='FFFE',
              segments=[Segment('text', 'Open your eyes.'),
                        Segment('ctrl', '<$FFFE>')]),
    ]
    overrides = {'scen001': {
        'dialogue_profile': NARRATION_16X5,
        'label_profile': LABEL_CHARACTER_12X1,
    }}
    # Without the label_profile override the last roster name is LOCATION.
    baseline = classify_entries(entries)
    assert baseline[1].profile == LABEL_LOCATION_16X1
    # With it, every FFFF label is a CHARACTER nameplate.
    results = classify_entries(entries, scen_overrides=overrides)
    assert results[0].profile == LABEL_CHARACTER_12X1
    assert results[1].profile == LABEL_CHARACTER_12X1
    assert results[1].semantic_subtype == 'CHARACTER_NAME'
    assert 'label remapped' in results[1].reason
    assert 'scen001' in results[1].reason
    # The FFFE body is still remapped to narration.
    assert results[2].profile == NARRATION_16X5


def test_scen_override_label_profile_noop_when_already_character():
    """A label already classified CHARACTER is not re-stamped (no spurious
    'label remapped' provenance)."""
    entries = [
        Entry(scen_id='scen001', index=0, raw='Tiaris<$FFFF>',
              terminator='FFFF',
              segments=[Segment('text', 'Tiaris'), Segment('ctrl', '<$FFFF>')]),
        Entry(scen_id='scen001', index=1, raw='Liffany<$FFFF>',
              terminator='FFFF',
              segments=[Segment('text', 'Liffany'),
                        Segment('ctrl', '<$FFFF>')]),
        Entry(scen_id='scen001', index=2, raw='body<$FFFE>',
              terminator='FFFE',
              segments=[Segment('text', 'body'), Segment('ctrl', '<$FFFE>')]),
    ]
    overrides = {'scen001': {'label_profile': LABEL_CHARACTER_12X1}}
    results = classify_entries(entries, scen_overrides=overrides)
    assert results[0].profile == LABEL_CHARACTER_12X1
    assert 'label remapped' not in results[0].reason


def test_scen_override_does_not_touch_other_profiles():
    """Override only fires when current profile is DIALOGUE_12X4.
    LABEL/OBJECTIVE/etc. pass through untouched even when the scen is
    listed."""
    entries = [
        # Initial scenario marker → NARRATION_16X5 (not DIALOGUE).
        Entry(scen_id='scen124', index=0,
              raw='<$0000><$FFFC>title<$0000>SCENARIO-1<$FFFC>body<$FFFE>',
              terminator='FFFE',
              segments=[Segment('ctrl', '<$0000>'),
                        Segment('ctrl', '<$FFFC>'),
                        Segment('text', 'title'),
                        Segment('ctrl', '<$0000>'),
                        Segment('text', 'SCENARIO-1'),
                        Segment('ctrl', '<$FFFC>'),
                        Segment('text', 'body'),
                        Segment('ctrl', '<$FFFE>')]),
    ]
    overrides = {'scen124': {'dialogue_profile': 'SOMETHING_ELSE'}}
    results = classify_entries(entries, scen_overrides=overrides)
    # NARRATION came in as NARRATION already — override must NOT touch it.
    assert results[0].profile == NARRATION_16X5
    assert 'overridden' not in results[0].reason


def test_midscene_scenario_opens_a_briefing():
    """A SCENARIO title recurring mid-scene (in SCENE_12X4 state, e.g.
    scen068/scen110) opens a fresh scenario briefing: the title and the
    recap-narration body that follows are all 16-wide NARRATION_16X5, not
    12-wide dialogue. A following FFFF location label returns to dialogue."""
    entries = [
        _make_entry(0, 'A line of dialogue.<$FFFE>', terminator='FFFE'),
        _make_entry(1, '<$0000><$FFFC>　　　ＳＣＥＮＡＲＩＯ‐１４<$FFFC>'
                       'Dios on the Run<$FFFE>', terminator='FFFE'),
        _make_entry(2, 'The party hastened onward...<$FFFE>', terminator='FFFE'),
        _make_entry(3, 'Battlefield<$FFFF>', terminator='FFFF'),
        _make_entry(4, ' Back to dialogue.<$FFFE>', terminator='FFFE'),
    ]
    results = classify_entries(entries)
    assert results[0].profile == DIALOGUE_12X4
    assert results[1].profile == NARRATION_16X5   # the recurring SCENARIO title
    assert results[2].profile == NARRATION_16X5   # the briefing recap body
    assert results[3].profile == LABEL_LOCATION_16X1
    assert results[4].profile == DIALOGUE_12X4    # location label returned to SCENE
