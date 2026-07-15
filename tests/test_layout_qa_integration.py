"""test_layout_qa_integration.py — golden end-to-end run on scen019E.txt.

Asserts subset invariants rather than exact JSON content (avoids
brittleness when translations are edited). Verifies the JSON validates
against the schema and that summary counts are sane.
"""

import json
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.cli import main  # noqa: E402
from layout_qa.metrics import validate_schema  # noqa: E402


SCRIPTS_DIR = PROJ / 'scripts' / 'en'


@pytest.fixture(scope='module')
def scen019_report(tmp_path_factory):
    if not (SCRIPTS_DIR / 'scen019E.txt').exists():
        pytest.skip('scripts/en/scen019E.txt missing')
    out = tmp_path_factory.mktemp('layout_qa') / 'scen019.json'
    rc = main(['analyze', 'scen019', '--output', str(out)])
    assert rc in (0, 2), f'unexpected exit code {rc}'
    return json.loads(out.read_text(encoding='utf-8'))


def test_scen019_passes_schema(scen019_report):
    errs = validate_schema(scen019_report)
    assert errs == [], f'schema violations: {errs[:5]}'


def test_scen019_basic_shape(scen019_report):
    s = scen019_report['summary']
    assert s['scenarioCount'] == 1
    assert s['entryCount'] > 0
    # Rates in [0,1]
    assert 0 <= s['playabilityRate'] <= 1
    assert 0 <= s['polishRate'] <= 1
    # polishRate is always ≤ playabilityRate (POLISHED ⊂ PLAYABLE+POLISHED).
    assert s['polishRate'] <= s['playabilityRate']


def test_scen019_has_character_and_location_labels(scen019_report):
    """scen019 should have multiple CHARACTER nameplates and at least one LOCATION."""
    s = scen019_report['summary']
    assert s['byProfile']['LABEL_CHARACTER_12X1'] > 5
    assert s['byProfile']['LABEL_LOCATION_16X1'] >= 1


def test_scen019_has_dialogue_majority(scen019_report):
    """Most scen019 entries are dialogue."""
    s = scen019_report['summary']
    assert s['byProfile']['DIALOGUE_12X4'] > s['byProfile']['LABEL_CHARACTER_12X1']


def test_scen019_no_unknown_profiles(scen019_report):
    """Classifier covers every entry."""
    s = scen019_report['summary']
    assert s['byProfile']['UNKNOWN'] == 0


def test_scen019_entries_have_required_fields(scen019_report):
    sc = scen019_report['scenarios'][0]
    assert sc['id'] == 'scen019'
    assert 'entries' in sc
    for er in sc['entries']:
        assert er['profile'] in (
            'LABEL_CHARACTER_12X1', 'LABEL_LOCATION_16X1',
            'OBJECTIVE_16X5', 'NARRATION_16X5', 'DIALOGUE_12X4', 'UNKNOWN',
        )
        assert er['status'] in ('ERROR', 'PLAYABLE', 'POLISHED')
        assert er['terminator'] in ('FFFE', 'FFFF', '')


# ---------------------------------------------------------------------------
# Corpus-wide smoke (skipped if too slow / dir missing)
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def corpus_report(tmp_path_factory):
    if not SCRIPTS_DIR.exists():
        pytest.skip('scripts/en/ missing')
    out = tmp_path_factory.mktemp('layout_qa') / 'all.json'
    rc = main(['analyze', '--all', '--output', str(out)])
    assert rc in (0, 2)
    return json.loads(out.read_text(encoding='utf-8'))


def test_exempt_scens_marked_and_not_error_counted(corpus_report):
    """scen122/123 are CN-origin with aesthetic <$FFFD> — exempt from layout
    QA. They must be flagged exempt, contribute zero ERROR, and the only
    real-corpus errors (none) must leave the global count at 0."""
    s = corpus_report['summary']
    assert set(s['exemptScenarios']) >= {'scen122', 'scen123'}
    by_id = {sc['id']: sc for sc in corpus_report['scenarios']}
    for sid in ('scen122', 'scen123'):
        sc = by_id[sid]
        assert sc.get('exempt') is True
        assert sc['byStatus']['ERROR'] == 0
        assert all(e.get('exempt') for e in sc['entries'])
    # Issues must STAY visible — exemption downgrades status, not detail. The
    # opening-movie narration of both scens is now cleanly fitted (the
    # NARRATION_16X5 jp_empty_only override + bottom-align <$FFFC> exemption),
    # so scen122 (pure narration) carries no issues; scen123 — whose JP-paired
    # in-scene dialogues still wrap at 12-wide — demonstrates the downgrade.
    assert any(e.get('issues') for e in by_id['scen123']['entries'])
    # The whole corpus is error-free once the aesthetic FFFD are exempt.
    assert s['byStatus']['ERROR'] == 0


def test_scen005_diaries_classified_as_heroine_diary(corpus_report):
    """The 4 heroine diaries at scen005[246-249] (Tiaris x2, Liffany, Luna)
    are PAGED narration driven by <$FFFD>, not 12x4 dialogue balloons — the
    JP holds up to 56 full-width tiles per page (rules out the 48-tile 12x4
    box). They are registered in config/diary-entries.json and classified as
    semantic_subtype 'diary' with the HEROINE_DIARY profile (12 wide, SCROLLS
    — the 12-tile LINE width is still enforced, but a page may run past any
    fixed line-window without a balloon_line_overflow error). The owning scen
    is flagged hasDiary; the surrounding battle stays DIALOGUE_12X4.

    Red state (2026-07-02): the fresh JP re-translation gave several pages 5-6
    wrapped lines; under the inherited DIALOGUE_12X4 profile those raised
    balloon_line_overflow, putting 3 scen005 entries into ERROR."""
    sc = {s['id']: s for s in corpus_report['scenarios']}['scen005']
    assert sc.get('hasDiary') is True
    by_idx = {e['index']: e for e in sc['entries']}
    for i in (246, 247, 248, 249):
        e = by_idx[i]
        assert e['profile'] == 'HEROINE_DIARY', (i, e['profile'])
        assert e['semantic_subtype'] == 'diary', (i, e['semantic_subtype'])
        assert e['status'] != 'ERROR', (i, e['status'])
        assert not any(
            iss['code'] == 'balloon_line_overflow' for iss in e.get('issues', [])
        ), (i, e.get('issues'))
    # the surrounding battle keeps the normal 12x4 dialogue profile
    assert by_idx[100]['profile'] == 'DIALOGUE_12X4'
    assert by_idx[100]['semantic_subtype'] != 'diary'


def test_all_location_labels_render_within_cap(corpus_report):
    """A <$FFFF> LABEL_LOCATION over 16 tiles silently fails to render
    in-game — and that render cap is INDEPENDENT of the aesthetic-FFFD
    exemption (an exempt scen's label still has to fit). Red state
    (2026-06-19): scen123[27] 'In front of the Royal capital Larcussia'
    was 20 tiles; shortened to 'Larcussia Castle Gate' (11)."""
    offenders = []
    for sc in corpus_report['scenarios']:
        for e in sc['entries']:
            if e['profile'] != 'LABEL_LOCATION_16X1':
                continue
            if any(i['code'] == 'label_overflow' for i in e.get('issues', [])):
                offenders.append(
                    (sc['id'], e['index'], e.get('tileUsage', {}).get('maxLine')))
    assert not offenders, f'location labels over the 16-tile cap: {offenders}'


def test_corpus_full_run_under_5s(tmp_path):
    """Phase 1 checkpoint: full corpus run must complete in < 5s."""
    if not SCRIPTS_DIR.exists():
        pytest.skip('scripts/en/ missing')
    import time
    out = tmp_path / 'all.json'
    start = time.perf_counter()
    rc = main(['analyze', '--all', '--output', str(out)])
    elapsed = time.perf_counter() - start
    assert rc in (0, 2)
    assert elapsed < 5.0, f'full corpus run too slow: {elapsed:.2f}s'
    report = json.loads(out.read_text(encoding='utf-8'))
    # 125 scen*E.txt files + plotE.txt (the 35-block PLOT.DAT recap).
    assert report['summary']['scenarioCount'] == 126
    assert report['summary']['entryCount'] == 13145
    errs = validate_schema(report)
    assert errs == [], f'schema fail on full corpus: {errs[:3]}'
