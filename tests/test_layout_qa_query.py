"""test_layout_qa_query.py — TDD for the agent-facing query subcommand.

Each query reads a trimmed snapshot (or the latest under a history
dir) and prints small markdown (< 2k tokens). The goal is to let a
future agent answer "what's the state of the patch?" without parsing
16 MB of JSON or reading the Python source.

Subcommands tested:
  query state                                  → headline numbers
  query top-files --by errors -n N             → ranked file table
  query file <scen>                            → drill-down on one file
  query issue <code>                           → distribution + top files
  query trend <metric> [--since DATE]          → time series (needs ≥2 snapshots)
  query catalog                                → issue codes + profiles ref
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.cli import main  # noqa: E402
from layout_qa.metrics import aggregate  # noqa: E402
from layout_qa.snapshot import write_snapshot  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _entry(idx, status='POLISHED', profile='DIALOGUE_12X4', issues=None):
    return {
        'index': idx, 'terminator': 'FFFE', 'profile': profile,
        'semantic_subtype': None,
        'classification': {'confidence': 1.0, 'reason': 'test', 'state': 'X'},
        'status': status,
        'tileUsage': {
            'budget': [12, 4], 'maxLine': 5, 'minLine': 5,
            'avgLine': 5.0, 'avgFillRatio': 0.4167, 'linesUsed': 1,
        },
        'issues': issues or [],
    }


def _scenario(scen_id, entries):
    return {'id': scen_id, 'path': f'scripts/en/{scen_id}E.txt',
            'entries': entries}


def _overflow(balloon=0):
    return {'code': 'balloon_line_overflow', 'severity': 'error',
            'detail': {'balloon': balloon, 'actualLines': 5, 'maxLines': 4}}


def _write_snap_in(history_dir, *, label, when, scenarios):
    """Build an aggregate from scenarios + write a snapshot."""
    report = aggregate(scenarios)
    return write_snapshot(report, history_dir, label=label, when=when,
                          git_cwd=history_dir)


# ===========================================================================
# query state
# ===========================================================================

def test_query_state_prints_headline_numbers(tmp_path, capsys):
    _write_snap_in(tmp_path, label='now', when=date(2026, 5, 27),
                   scenarios=[_scenario('scen001', [
                       _entry(0, 'POLISHED'),
                       _entry(1, 'ERROR', issues=[_overflow()]),
                   ])])
    rc = main(['query', '--history', str(tmp_path), 'state'])
    assert rc == 0
    out = capsys.readouterr().out
    # Project summary numbers visible.
    assert '50.0%' in out  # readiness/polish 50% in the toy fixture
    assert '2 entries' in out or 'entries: 2' in out.lower() or '**2**' in out
    # Snapshot frontmatter referenced.
    assert 'now' in out  # label
    assert '2026-05-27' in out


def test_query_state_uses_latest_snapshot(tmp_path, capsys):
    """When multiple snapshots exist, query state reads the latest by date."""
    _write_snap_in(tmp_path, label='old', when=date(2026, 5, 20),
                   scenarios=[_scenario('scen001',
                                        [_entry(0, 'ERROR', issues=[_overflow()])])])
    _write_snap_in(tmp_path, label='new', when=date(2026, 5, 27),
                   scenarios=[_scenario('scen001',
                                        [_entry(0, 'POLISHED')])])
    rc = main(['query', '--history', str(tmp_path), 'state'])
    assert rc == 0
    out = capsys.readouterr().out
    # Latest has 100% readiness/polish.
    assert '100.0%' in out
    assert 'new' in out
    assert 'old' not in out or out.count('old') < out.count('new')


def test_query_state_empty_history_fails_gracefully(tmp_path, capsys):
    rc = main(['query', '--history', str(tmp_path), 'state'])
    assert rc == 3
    err = capsys.readouterr().err
    assert 'snapshot' in err.lower()


# ===========================================================================
# query top-files
# ===========================================================================

def test_query_top_files_by_errors(tmp_path, capsys):
    _write_snap_in(tmp_path, label='now', when=date(2026, 5, 27),
                   scenarios=[
                       _scenario('scen001', [
                           _entry(0, 'ERROR', issues=[_overflow()]),
                           _entry(1, 'ERROR', issues=[_overflow()]),
                           _entry(2, 'ERROR', issues=[_overflow()]),
                       ]),
                       _scenario('scen002', [_entry(0, 'POLISHED')]),
                       _scenario('scen003', [
                           _entry(0, 'ERROR', issues=[_overflow()]),
                       ]),
                   ])
    rc = main(['query', '--history', str(tmp_path),
               'top-files', '--by', 'errors', '-n', '2'])
    assert rc == 0
    out = capsys.readouterr().out
    # scen001 (3 errors) first; scen003 (1 error) second; scen002 excluded.
    pos1 = out.find('scen001')
    pos3 = out.find('scen003')
    assert 0 < pos1 < pos3
    assert 'scen002' not in out


def test_query_top_files_by_readiness(tmp_path, capsys):
    """--by readiness sorts ascending — lowest readiness first."""
    _write_snap_in(tmp_path, label='now', when=date(2026, 5, 27),
                   scenarios=[
                       _scenario('scen001', [_entry(0, 'POLISHED')]),
                       _scenario('scen002', [
                           _entry(0, 'ERROR', issues=[_overflow()]),
                       ]),
                   ])
    rc = main(['query', '--history', str(tmp_path),
               'top-files', '--by', 'readiness', '-n', '5'])
    assert rc == 0
    out = capsys.readouterr().out
    # scen002 has 0% readiness — should come first.
    pos2 = out.find('scen002')
    pos1 = out.find('scen001')
    assert pos2 < pos1


def test_query_top_files_invalid_metric_fails(tmp_path, capsys):
    _write_snap_in(tmp_path, label='now', when=date(2026, 5, 27),
                   scenarios=[_scenario('scen001', [_entry(0, 'POLISHED')])])
    rc = main(['query', '--history', str(tmp_path),
               'top-files', '--by', 'banana'])
    assert rc == 3


# ===========================================================================
# query file
# ===========================================================================

def test_query_file_shows_drill_down(tmp_path, capsys):
    _write_snap_in(tmp_path, label='now', when=date(2026, 5, 27),
                   scenarios=[
                       _scenario('scen042', [
                           _entry(0, 'POLISHED'),
                           _entry(1, 'ERROR', issues=[_overflow()]),
                           _entry(2, 'PLAYABLE', issues=[
                               {'code': 'low_line_usage', 'severity': 'warning'}
                           ]),
                       ]),
                       _scenario('scen001', [_entry(0, 'POLISHED')]),
                   ])
    rc = main(['query', '--history', str(tmp_path), 'file', 'scen042'])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'scen042' in out
    # Status breakdown for that file.
    assert 'ERROR' in out and '1' in out
    # Issue breakdown for that file.
    assert 'balloon_line_overflow' in out
    assert 'low_line_usage' in out
    # Other file shouldn't appear.
    assert 'scen001' not in out


def test_query_file_missing_scen_fails(tmp_path, capsys):
    _write_snap_in(tmp_path, label='now', when=date(2026, 5, 27),
                   scenarios=[_scenario('scen001', [_entry(0)])])
    rc = main(['query', '--history', str(tmp_path), 'file', 'scen999'])
    assert rc == 3


# ===========================================================================
# query issue
# ===========================================================================

def test_query_issue_shows_distribution(tmp_path, capsys):
    _write_snap_in(tmp_path, label='now', when=date(2026, 5, 27),
                   scenarios=[
                       _scenario('scen001', [
                           _entry(0, 'ERROR', issues=[_overflow()]),
                           _entry(1, 'ERROR', issues=[_overflow()]),
                       ]),
                       _scenario('scen002', [
                           _entry(0, 'ERROR', issues=[_overflow()]),
                       ]),
                   ])
    rc = main(['query', '--history', str(tmp_path),
               'issue', 'balloon_line_overflow'])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'balloon_line_overflow' in out
    # 3 occurrences across 2 files.
    assert '3' in out
    assert '2' in out
    # Top files affected listed.
    assert 'scen001' in out


def test_query_issue_unknown_code_fails(tmp_path, capsys):
    _write_snap_in(tmp_path, label='now', when=date(2026, 5, 27),
                   scenarios=[_scenario('scen001', [_entry(0)])])
    rc = main(['query', '--history', str(tmp_path), 'issue', 'no_such_code'])
    assert rc == 3


# ===========================================================================
# query trend
# ===========================================================================

def test_query_trend_renders_time_series(tmp_path, capsys):
    # Two snapshots with different rates.
    _write_snap_in(tmp_path, label='a', when=date(2026, 5, 20),
                   scenarios=[_scenario('scen001', [
                       _entry(0, 'ERROR', issues=[_overflow()]),
                   ])])
    _write_snap_in(tmp_path, label='b', when=date(2026, 5, 27),
                   scenarios=[_scenario('scen001', [_entry(0, 'POLISHED')])])
    rc = main(['query', '--history', str(tmp_path),
               'trend', 'playabilityRate'])
    assert rc == 0
    out = capsys.readouterr().out
    # Series shows both dates and their rates.
    assert '2026-05-20' in out
    assert '2026-05-27' in out
    assert '0.0%' in out
    assert '100.0%' in out


def test_query_trend_needs_at_least_one_snapshot(tmp_path, capsys):
    rc = main(['query', '--history', str(tmp_path),
               'trend', 'playabilityRate'])
    assert rc == 3


# ===========================================================================
# query catalog
# ===========================================================================

def test_query_catalog_lists_issues_and_profiles(tmp_path, capsys):
    """catalog doesn't need a snapshot — it's static reference."""
    rc = main(['query', '--history', str(tmp_path), 'catalog'])
    assert rc == 0
    out = capsys.readouterr().out
    # All 9 issue codes mentioned.
    for code in ('line_budget_exceeded', 'label_overflow',
                 'balloon_line_overflow', 'broken_word_wrap',
                 'unknown_layout_profile', 'implicit_wrap_without_fffc',
                 'low_line_usage', 'special_token_overflow_risk',
                 'encoding_risk'):
        assert code in out, f'missing: {code}'
    # All 5+1 profiles mentioned.
    for prof in ('LABEL_CHARACTER_12X1', 'LABEL_LOCATION_16X1',
                 'OBJECTIVE_16X5', 'NARRATION_16X5', 'DIALOGUE_12X4',
                 'UNKNOWN'):
        assert prof in out, f'missing: {prof}'
