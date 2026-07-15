#!/usr/bin/env python3
"""
test_choice_fit.py — CHOICE entries (player-facing menu options) must fit one
line of their balloon minus the 1-tile selection cursor.

Choices are structurally invisible in the script (plain <$FFFE> entries), so the
guide-derived `config/entry-annotations.json` (class=CHOICE, JP-anchored) is the
oracle that marks them. Budget = (resolved balloon width) - 1 cursor tile,
single line, no <$FFFC>. Width uses the simulator's real tile-cost model.

Two layers:
- DETECTOR mechanics are pinned on a synthetic fixture (stable, independent of
  any script content): overflow + multiline are flagged, a fitting option is not,
  and the budget derives from the resolved (override-aware) balloon width.
- A RATCHET asserts the LIVE annotated choices all fit. Its red state introduced
  scen005 idx 99 ("No sense of direction…" = 12t > 11) and idx 100 (the secret
  scenario ?1 trigger, wrapped to 2 lines); both fixed in scripts/en/scen005E.txt.
  scen001 (the only 100%-narration scen, NARRATION_16X5 -> budget 15) is the
  no-false-positive anchor: its correct quiz options reach exactly 15 and pass.
"""

import json
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))
EN = PROJ / 'scripts' / 'en'
JP = PROJ / 'scripts' / 'jp'

OVERRIDES = json.loads(
    (PROJ / 'config' / 'layout-overrides.json').read_text(encoding='utf-8')
).get('scen_overrides', {})
ANNOTATIONS = {
    k: v for k, v in
    json.loads((PROJ / 'config' / 'entry-annotations.json').read_text(
        encoding='utf-8')).items()
    if not k.startswith('$')
}


def _analyze(scen_id, en_dir=EN, jp_dir=JP, overrides=None, annotations=None):
    from layout_qa.choices import analyze_choice_fit
    return analyze_choice_fit(
        scen_id=scen_id, en_dir=en_dir, jp_dir=jp_dir,
        overrides=OVERRIDES if overrides is None else overrides,
        annotations=ANNOTATIONS if annotations is None else annotations,
    )


# --------------------------------------------------------------------------
# DETECTOR mechanics — synthetic fixture (stable, no dependence on scripts)
# --------------------------------------------------------------------------

def _write_synth(tmp_path):
    # A name label (FFFF) then dialogue (FFFE) → the body classifies DIALOGUE_12X4
    # (field, budget 12-1 = 11). Three CHOICE options: overflow / multiline / fits.
    (tmp_path / 'scen999E.txt').write_text(
        "Hero<$FFFF>\n"
        "This option is far too long to fit<$FFFE>\n"           # idx1 overflow
        "Two-line option here<$FFFC>spilling over<$FFFE>\n"     # idx2 multiline
        "Stay here<$FFFE>\n",                                   # idx3 fits
        encoding='utf-8')
    ann = {'scen999': {
        '1': {'class': 'CHOICE'},
        '2': {'class': 'CHOICE', 'notes': 'keep meaning'},
        '3': {'class': 'CHOICE'},
    }}
    return ann


def test_detector_flags_overflow_and_multiline(tmp_path):
    ann = _write_synth(tmp_path)
    issues = _analyze('scen999', en_dir=tmp_path, jp_dir=tmp_path,
                      overrides={}, annotations=ann)
    pairs = {(i['index'], i['code']) for i in issues}
    assert (1, 'choice_overflow') in pairs, pairs
    assert (2, 'choice_multiline') in pairs, pairs


def test_detector_passes_a_fitting_option(tmp_path):
    ann = _write_synth(tmp_path)
    flagged = {i['index'] for i in _analyze(
        'scen999', en_dir=tmp_path, jp_dir=tmp_path, overrides={}, annotations=ann)}
    assert 3 not in flagged, flagged


def test_detector_budget_is_field_eleven(tmp_path):
    ann = _write_synth(tmp_path)
    over = next(i for i in _analyze(
        'scen999', en_dir=tmp_path, jp_dir=tmp_path, overrides={}, annotations=ann)
        if i['index'] == 1)
    assert over['budget'] == 11        # DIALOGUE_12X4 → 12 - 1 cursor
    assert over['width'] > 11


def test_detector_carries_notes(tmp_path):
    ann = _write_synth(tmp_path)
    ml = next(i for i in _analyze(
        'scen999', en_dir=tmp_path, jp_dir=tmp_path, overrides={}, annotations=ann)
        if i['index'] == 2)
    assert ml.get('notes') == 'keep meaning'


# --------------------------------------------------------------------------
# Budget derives from the RESOLVED (override-aware) balloon — live anchor
# --------------------------------------------------------------------------

def test_scen001_narration_choices_pass_at_fifteen():
    # scen001 is overridden to NARRATION_16X5 → budget 15. Its correct quiz
    # options reach exactly 15 and must NOT flag. (If budget were hardcoded to
    # the field 11, these would fail — so this proves override-aware derivation.)
    assert _analyze('scen001') == []


# --------------------------------------------------------------------------
# COVERAGE — guide-listed choice blocks must be registered (else the detector
# never checks them). Red state: the Sc31 post-battle Liffany consolation block
# (攻略データ リファニー 7, fires only if Freya is dead) had 0 CHOICE entries in
# scen103, so its three options went unchecked. Anchored on the literal JP
# option text (balizador), not the parsed index, so it survives line drift.
# --------------------------------------------------------------------------

def test_residual_story_trigger_blocks_registered():
    """The story-trigger reply blocks the love-index sweep left open (HANDOFF
    'STILL OPEN'): scen011's Do Kahni reply block and the time-crossing stone
    block (欲しいと言う = the ?2 secret-stage trigger), and scen035's post-battle
    reply block. All are plain <$FFFE> 何と答えますか options with no marker, so the
    registry is the only oracle. Red state: 0 of these registered.

    Asserted per option *text*, not per occurrence: in a branching tree the chosen
    option's short text is also echoed as the spoken line a few entries later
    (e.g. scen011 '無理をするなよ。' is the menu option AND the hero's spoken line),
    and only the menu occurrence is a CHOICE. So require each option text to be the
    live-JP anchor of *some* registered CHOICE entry (coverage + anti-drift), not
    every textual match."""
    from layout_qa.parser import parse_scenario
    residual = {
        'scen011': {'一緒に戦おう！', '傷は治ったのか？', '無理をするなよ。',
                    '納得する', '欲しいと言う', '疑ってかかる'},
        'scen035': {'楽勝だったので平気だ', '気にしないでくれ'},
    }
    for scen, wanted in residual.items():
        jp = parse_scenario(JP / f'{scen}J.txt')
        ann = ANNOTATIONS.get(scen, {})
        registered = {
            jp[int(idx)].raw.replace('<$FFFE>', '').strip()
            for idx, meta in ann.items()
            if isinstance(meta, dict) and meta.get('class') == 'CHOICE'
            and int(idx) < len(jp)
        }
        missing = wanted - registered
        assert not missing, f'{scen}: option(s) not registered class=CHOICE: {missing}'


def test_every_menu_prompt_block_is_registered():
    """Durable completeness net: every explicit menu prompt (何と答えますか /
    どう答えますか / 何と話しかけますか / 何と言いますか) is immediately followed by its
    first selectable option, which MUST be registered class=CHOICE — choices are
    structurally invisible, so a missing registration means the CHOICE-fit gate
    silently skips that block. Catches any dialogue-choice block a future edit
    adds or a sweep missed. Red state: scen040[160] (the ?3 Dios posing reply)
    was unregistered."""
    import glob
    import os
    from layout_qa.parser import parse_scenario
    prompts = ('何と答えますか', 'どう答えますか', '何と話しかけますか', '何と言いますか')
    missing = []
    for f in sorted(glob.glob(str(JP / 'scen*J.txt'))):
        scen = os.path.basename(f)[:-5]
        jp = parse_scenario(Path(f))
        ann = ANNOTATIONS.get(scen, {})
        for i, e in enumerate(jp):
            if any(p in e.raw for p in prompts) and i + 1 < len(jp):
                meta = ann.get(str(i + 1))
                if not (isinstance(meta, dict) and meta.get('class') == 'CHOICE'):
                    missing.append(f'{scen}[{i + 1}] (after prompt @{i}): {jp[i + 1].raw!r}')
    assert not missing, ('menu-prompt blocks whose first option is unregistered:\n'
                         + '\n'.join(missing))


def test_scen103_sc31_consolation_block_registered():
    from layout_qa.parser import parse_scenario
    options = {'大丈夫だよ。', '‥‥ごめん。', '放っておいて。'}
    jp = parse_scenario(JP / 'scen103J.txt')
    ann = ANNOTATIONS.get('scen103', {})
    found = []
    for idx, entry in enumerate(jp):
        if entry.raw.replace('<$FFFE>', '').strip() in options:
            found.append(idx)
            meta = ann.get(str(idx))
            assert isinstance(meta, dict) and meta.get('class') == 'CHOICE', (
                f'scen103[{idx}] is a Sc31 menu option but is not registered '
                f'class=CHOICE: {entry.raw!r}')
    assert len(found) == 3, f'expected the 3 bare options, found {found}'


# --------------------------------------------------------------------------
# RATCHET — every LIVE annotated CHOICE fits (was red: scen005 idx 99/100)
# --------------------------------------------------------------------------

def test_live_annotated_choices_all_fit():
    violations = []
    for scen_id in ANNOTATIONS:
        violations.extend(_analyze(scen_id))
    assert violations == [], [
        (v['scen'], v['index'], v['code'], v['width'], v['budget'])
        for v in violations
    ]


# --------------------------------------------------------------------------
# WIRING — `cli analyze` surfaces CHOICE issues per entry + corpus tally
# (was red: choices.py existed but was only wired into this test file, not
#  into the analyzer, so `cli analyze` never reported choice_* issues)
# --------------------------------------------------------------------------

def _run_cli_analyze(tmp_path, scen_file_text, annotations_obj, scen_id):
    """Drive the real `cli analyze` on a synthetic scen + annotation file.

    Returns the parsed report JSON. Isolated from the live config by pointing
    every config flag at tmp_path (missing approved/exempt → no-op loaders).
    """
    from layout_qa import cli
    en = tmp_path / 'en'
    en.mkdir(exist_ok=True)
    (en / f'{scen_id}E.txt').write_text(scen_file_text, encoding='utf-8')
    ann = tmp_path / 'ann.json'
    ann.write_text(json.dumps(annotations_obj), encoding='utf-8')
    over = tmp_path / 'over.json'
    over.write_text(json.dumps({'scen_overrides': {}}), encoding='utf-8')
    out = tmp_path / 'out.json'
    rc = cli.main([
        'analyze', scen_id,
        '--scripts', str(en),
        '--annotations', str(ann),
        '--overrides', str(over),
        '--approved', str(tmp_path / 'no-approved.json'),
        '--exempt', str(tmp_path / 'no-exempt.json'),
        '--output', str(out),
    ])
    return rc, json.loads(out.read_text(encoding='utf-8'))


def test_cli_analyze_surfaces_choice_multiline(tmp_path):
    # A two-line option whose lines each fit the dialogue budget (so the normal
    # simulator does NOT error) — only the CHOICE detector flags it. This
    # isolates the wiring: the sole error-severity issue must be choice_multiline,
    # and that alone must flip the entry to ERROR.
    rc, report = _run_cli_analyze(
        tmp_path,
        "Hero<$FFFF>\n"
        "Take the sword<$FFFC>or leave it<$FFFE>\n",
        {'$c': 'test', 'scen777': {'1': {'class': 'CHOICE', 'notes': 'keep it'}}},
        'scen777',
    )
    scen = next(s for s in report['scenarios'] if s['id'] == 'scen777')
    e1 = next(e for e in scen['entries'] if e['index'] == 1)
    err_codes = {i['code'] for i in e1['issues'] if i['severity'] == 'error'}
    assert err_codes == {'choice_multiline'}, e1['issues']
    assert e1['status'] == 'ERROR'
    # carried through to the entry's detail and the corpus tally
    detail = next(i for i in e1['issues'] if i['code'] == 'choice_multiline')['detail']
    assert detail['budget'] == 11 and detail['notes'] == 'keep it'
    assert report['summary']['byIssue']['choice_multiline'] == 1
    assert rc == 2  # an ERROR entry exists


def test_cli_analyze_surfaces_choice_overflow(tmp_path):
    rc, report = _run_cli_analyze(
        tmp_path,
        "Hero<$FFFF>\n"
        "This option is far too long to fit<$FFFE>\n",
        {'scen778': {'1': {'class': 'CHOICE'}}},
        'scen778',
    )
    scen = next(s for s in report['scenarios'] if s['id'] == 'scen778')
    e1 = next(e for e in scen['entries'] if e['index'] == 1)
    codes = {i['code'] for i in e1['issues']}
    assert 'choice_overflow' in codes, e1['issues']
    assert report['summary']['byIssue']['choice_overflow'] == 1


def test_cli_analyze_clean_when_choice_fits(tmp_path):
    # An annotated option that fits the field budget (11) produces no choice
    # issue and no false ERROR from the wiring.
    rc, report = _run_cli_analyze(
        tmp_path,
        "Hero<$FFFF>\n"
        "Stay here<$FFFE>\n",
        {'scen779': {'1': {'class': 'CHOICE'}}},
        'scen779',
    )
    scen = next(s for s in report['scenarios'] if s['id'] == 'scen779')
    e1 = next(e for e in scen['entries'] if e['index'] == 1)
    codes = {i['code'] for i in e1['issues']}
    assert 'choice_overflow' not in codes and 'choice_multiline' not in codes
    assert report['summary']['byIssue']['choice_overflow'] == 0
