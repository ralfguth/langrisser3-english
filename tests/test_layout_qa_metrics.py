"""test_layout_qa_metrics.py — bucket + aggregate + schema lock."""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa import SCHEMA_VERSION  # noqa: E402
from layout_qa.metrics import (  # noqa: E402
    bucket_status, aggregate, validate_schema,
    ISSUE_CODES, PROFILE_NAMES, STATUS_VALUES,
)


# ---------------------------------------------------------------------------
# bucket_status
# ---------------------------------------------------------------------------

def test_bucket_no_issues_is_polished():
    assert bucket_status([], 'DIALOGUE_12X4') == 'POLISHED'


def test_bucket_only_warnings_is_playable():
    issues = [{'code': 'low_line_usage', 'severity': 'warning'}]
    assert bucket_status(issues, 'DIALOGUE_12X4') == 'PLAYABLE'


def test_bucket_any_error_is_error():
    issues = [
        {'code': 'low_line_usage', 'severity': 'warning'},
        {'code': 'broken_word_wrap', 'severity': 'error'},
    ]
    assert bucket_status(issues, 'DIALOGUE_12X4') == 'ERROR'


def test_bucket_unknown_profile_is_error():
    """Even with zero issues, UNKNOWN profile counts as ERROR."""
    assert bucket_status([], 'UNKNOWN') == 'ERROR'


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------

def _entry(idx, profile, status, issues=()):
    return {
        'index': idx,
        'terminator': 'FFFE',
        'profile': profile,
        'semantic_subtype': None,
        'classification': {'confidence': 0.9, 'reason': 'test', 'state': 'SCENE_12X4'},
        'status': status,
        'tileUsage': {'maxLine': 6, 'minLine': 6, 'linesUsed': 1, 'budget': [12, 4]},
        'issues': list(issues),
    }


def test_aggregate_empty():
    report = aggregate([], lang='en')
    assert report['summary']['entryCount'] == 0
    assert report['summary']['scenarioCount'] == 0
    assert report['summary']['playabilityRate'] == 1.0  # vacuous truth
    assert report['summary']['polishRate'] == 1.0


def test_aggregate_counts_status_profile_issue():
    sc = {
        'id': 'scenT',
        'path': 'scripts/en/scenTE.txt',
        'entries': [
            _entry(0, 'DIALOGUE_12X4', 'POLISHED'),
            _entry(1, 'DIALOGUE_12X4', 'PLAYABLE',
                   [{'code': 'low_line_usage', 'severity': 'warning'}]),
            _entry(2, 'LABEL_CHARACTER_12X1', 'ERROR',
                   [{'code': 'broken_word_wrap', 'severity': 'error'}]),
        ],
    }
    report = aggregate([sc], lang='en')
    s = report['summary']
    assert s['entryCount'] == 3
    assert s['scenarioCount'] == 1
    assert s['byStatus'] == {'ERROR': 1, 'PLAYABLE': 1, 'POLISHED': 1}
    assert s['byProfile']['DIALOGUE_12X4'] == 2
    assert s['byProfile']['LABEL_CHARACTER_12X1'] == 1
    assert s['byIssue']['broken_word_wrap'] == 1
    assert s['byIssue']['low_line_usage'] == 1
    # playabilityRate = (PLAYABLE + POLISHED) / total = 2/3
    assert abs(s['playabilityRate'] - 2 / 3) < 1e-3
    # polishRate = POLISHED / total = 1/3
    assert abs(s['polishRate'] - 1 / 3) < 1e-3


def test_aggregate_includes_schema_metadata():
    report = aggregate([], lang='it')
    assert report['schemaVersion'] == SCHEMA_VERSION
    assert report['lang'] == 'it'
    assert report['tool']['name'] == 'layout_qa'
    assert 'generatedAt' in report


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_schema_validator_passes_on_empty_aggregate():
    report = aggregate([], lang='en')
    errs = validate_schema(report)
    assert errs == [], f'unexpected schema errors: {errs}'


def test_schema_validator_passes_on_realistic_aggregate():
    sc = {
        'id': 'scenT',
        'path': 'scripts/en/scenTE.txt',
        'entries': [
            _entry(0, 'DIALOGUE_12X4', 'POLISHED'),
            _entry(1, 'NARRATION_16X5', 'PLAYABLE',
                   [{'code': 'low_line_usage', 'severity': 'warning'}]),
        ],
    }
    report = aggregate([sc], lang='en')
    errs = validate_schema(report)
    assert errs == [], f'schema errors on realistic report: {errs}'


def test_schema_validator_flags_missing_field():
    bad = {
        'schemaVersion': '0.1.0',
        'generatedAt': 'now',
        # 'lang' missing
        'tool': {'name': 'layout_qa', 'version': '0.1.0'},
        'summary': {
            'scenarioCount': 0, 'entryCount': 0,
            'byStatus': {k: 0 for k in STATUS_VALUES},
            'byProfile': {k: 0 for k in PROFILE_NAMES},
            'byIssue': {k: 0 for k in ISSUE_CODES},
            'playabilityRate': 1.0, 'polishRate': 1.0,
        },
        'scenarios': [],
    }
    errs = validate_schema(bad)
    assert any('lang' in e for e in errs), errs


def test_schema_validator_flags_unknown_profile():
    sc = {
        'id': 'scenT',
        'path': 'scripts/en/scenTE.txt',
        'entries': [_entry(0, 'NOT_A_PROFILE', 'POLISHED')],
    }
    report = aggregate([sc], lang='en')
    errs = validate_schema(report)
    assert any('NOT_A_PROFILE' in e for e in errs), errs


def test_schema_validator_flags_rate_out_of_range():
    report = aggregate([], lang='en')
    report['summary']['playabilityRate'] = 1.5
    errs = validate_schema(report)
    assert any('out of range' in e for e in errs), errs


# ---------------------------------------------------------------------------
# Issue catalog locked
# ---------------------------------------------------------------------------

def test_issue_catalog_exactly_eleven_codes():
    """Per user spec 2026-05-27: 5 error codes + 5 warning codes.
    label_overflow is its own bucket distinct from line_budget_exceeded.
    line_padding_space added 2026-05-27 (schema 0.3.1): flags lines that
    end with " " (non-last) or start with " " (non-first) — the wrap did
    not consume the space. DIALOGUE only; layout-trick profiles exempt
    via 'enforce_line_padding': False.
    fluidity_headroom added 2026-06-01: an 'info' advisory (does NOT
    disqualify polish) for a short non-final line that ends a sentence —
    leftover width is room for fluidity, not an under-fill defect.
    forbidden_punctuation added 2026-06-18: an error for a colon `:`,
    semicolon `;`, or em-dash `—` in scen/plot prose (project-wide
    spoken-punctuation rule, user 2026-06-16)."""
    assert len(ISSUE_CODES) == 14
    assert set(ISSUE_CODES) == {
        # errors
        'line_budget_exceeded', 'label_overflow', 'balloon_line_overflow',
        'broken_word_wrap', 'unknown_layout_profile',
        # CHOICE-fit errors (player-facing menu options; see choices.py)
        'choice_overflow', 'choice_multiline',
        # spoken-punctuation gate (`:` `;` `—` forbidden in prose)
        'forbidden_punctuation',
        # warnings
        'implicit_wrap_without_fffc', 'low_line_usage',
        'special_token_overflow_risk', 'encoding_risk',
        'line_padding_space',
        # info (advisory, non-blocking)
        'fluidity_headroom',
    }


def test_profile_catalog_six_names():
    """6 real profiles + UNKNOWN."""
    assert len(PROFILE_NAMES) == 7
    assert 'HEROINE_DIARY' in PROFILE_NAMES
    assert 'UNKNOWN' in PROFILE_NAMES
