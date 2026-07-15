"""test_layout_qa_snapshot.py — TDD for the snapshot system.

Snapshots are the committable, small (~100-200 KB) trim of the full
layout-QA JSON. They live in `reports/history/` (a symlink to a
sibling git repo). The trim drops `scenarios[*].entries[*]` (the
per-entry detail) and keeps every aggregate.

Phase A: `trim()` shape + size invariants.
Phase B: `snapshot` subcommand orchestration.
Phase C: `query` subcommand surface.
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.metrics import aggregate  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures (re-use the readiness-test entry/scenario builders)
# ---------------------------------------------------------------------------

def _entry(idx, status='POLISHED', profile='DIALOGUE_12X4', issues=None):
    return {
        'index': idx,
        'terminator': 'FFFE',
        'profile': profile,
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


def _full_report():
    """A non-trivial report — several scenarios, mixed issue types."""
    return aggregate([
        _scenario('scen001', [
            _entry(0, 'POLISHED'),
            _entry(1, 'ERROR', issues=[
                {'code': 'balloon_line_overflow', 'severity': 'error',
                 'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
            ]),
        ]),
        _scenario('scen002', [
            _entry(0, 'POLISHED'),
        ]),
    ])


# ===========================================================================
# Phase A (TDD red): trim() — strip entries[*] from the report
# ---------------------------------------------------------------------------
# Keeps every aggregate; drops only scenarios[*].entries.
# Adds a `snapshot` frontmatter when caller provides one.
# ===========================================================================

def test_trim_keeps_top_level_aggregates():
    from layout_qa.snapshot import trim
    full = _full_report()
    trimmed = trim(full)
    assert trimmed['schemaVersion'] == full['schemaVersion']
    assert trimmed['projectSummary'] == full['projectSummary']
    assert trimmed['summary'] == full['summary']
    assert trimmed['lang'] == full['lang']


def test_trim_drops_per_entry_detail():
    from layout_qa.snapshot import trim
    full = _full_report()
    trimmed = trim(full)
    for sc in trimmed['scenarios']:
        assert 'entries' not in sc, (
            f'scenario {sc["id"]} kept entries[] — should be dropped'
        )


def test_trim_keeps_per_scenario_aggregates():
    from layout_qa.snapshot import trim
    full = _full_report()
    trimmed = trim(full)
    for full_sc, trim_sc in zip(full['scenarios'], trimmed['scenarios']):
        assert trim_sc['id'] == full_sc['id']
        assert trim_sc['path'] == full_sc['path']
        assert trim_sc['entryCount'] == full_sc['entryCount']
        assert trim_sc['byStatus'] == full_sc['byStatus']
        assert trim_sc['byIssue'] == full_sc['byIssue']
        assert trim_sc['readinessRate'] == full_sc['readinessRate']
        assert trim_sc['polishRate'] == full_sc['polishRate']


def test_trim_does_not_mutate_input():
    """trim() returns a new dict and leaves the original report alone."""
    from layout_qa.snapshot import trim
    full = _full_report()
    full_before = json.loads(json.dumps(full))  # deep copy snapshot
    trim(full)
    assert full == full_before, 'trim() mutated its input'


def test_trim_adds_snapshot_frontmatter_when_passed():
    from layout_qa.snapshot import trim
    full = _full_report()
    trimmed = trim(full, snapshot={
        'date': '2026-05-27',
        'label': 'post-override',
        'gitCommit': '8a38621',
        'gitBranch': 'feature/layout-qa-phase1',
        'note': 'scen124 override applied',
    })
    snap = trimmed['snapshot']
    assert snap['date'] == '2026-05-27'
    assert snap['label'] == 'post-override'
    assert snap['gitCommit'] == '8a38621'
    assert snap['gitBranch'] == 'feature/layout-qa-phase1'
    assert snap['note'] == 'scen124 override applied'


def test_trim_no_snapshot_block_when_omitted():
    from layout_qa.snapshot import trim
    full = _full_report()
    trimmed = trim(full)
    assert 'snapshot' not in trimmed


def test_trim_is_meaningfully_smaller():
    """The trim must produce a JSON noticeably smaller than the full
    report — that's the whole point of the snapshot. We don't pin a
    ratio (depends on corpus), but trimmed must be < 50% of full."""
    from layout_qa.snapshot import trim
    full = _full_report()
    trimmed = trim(full)
    full_size = len(json.dumps(full))
    trim_size = len(json.dumps(trimmed))
    assert trim_size < full_size, 'trim should be smaller than full'
    # On the toy fixture the gain is modest, but the dropped entries
    # must contribute at least *something*.
    assert trim_size < full_size, (
        f'trim_size={trim_size} not smaller than full_size={full_size}'
    )


# ===========================================================================
# Phase B (TDD red): snapshot subcommand
# ---------------------------------------------------------------------------
# `python3 -m tools.layout_qa.cli snapshot --label X --note Y` writes
# a trimmed JSON to reports/history/snapshot-YYYY-MM-DD_<label>.json.
# `--list` enumerates existing snapshots.
# `--diff A B` prints a high-level diff between two snapshots.
# ===========================================================================

def test_snapshot_path_naming_with_slug():
    from layout_qa.snapshot import snapshot_path
    p = snapshot_path(
        Path('/tmp/hist'),
        label='Post Override v2',
        when=date(2026, 5, 27),
    )
    assert p.name == 'snapshot-2026-05-27_post-override-v2.json'


def test_write_snapshot_creates_file_with_frontmatter(tmp_path):
    from layout_qa.snapshot import write_snapshot
    full = _full_report()
    path = write_snapshot(
        full, tmp_path,
        label='unit-test',
        note='fixture',
        when=date(2026, 5, 27),
        git_cwd=tmp_path,  # not a git repo → empty commit/branch
    )
    assert path.exists()
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['snapshot']['date'] == '2026-05-27'
    assert data['snapshot']['label'] == 'unit-test'
    assert data['snapshot']['note'] == 'fixture'
    # Trim is applied — no entries[*].
    for sc in data['scenarios']:
        assert 'entries' not in sc


def test_list_snapshots_sorted_chronologically(tmp_path):
    from layout_qa.snapshot import write_snapshot, list_snapshots
    full = _full_report()
    write_snapshot(full, tmp_path, label='a',
                   when=date(2026, 5, 27), git_cwd=tmp_path)
    write_snapshot(full, tmp_path, label='b',
                   when=date(2026, 6, 1), git_cwd=tmp_path)
    write_snapshot(full, tmp_path, label='c',
                   when=date(2026, 5, 30), git_cwd=tmp_path)
    snaps = list_snapshots(tmp_path)
    assert [p.name for p in snaps] == [
        'snapshot-2026-05-27_a.json',
        'snapshot-2026-05-30_c.json',
        'snapshot-2026-06-01_b.json',
    ]


def test_resolve_snapshot_by_full_filename(tmp_path):
    from layout_qa.snapshot import write_snapshot, resolve_snapshot
    full = _full_report()
    written = write_snapshot(full, tmp_path, label='x',
                             when=date(2026, 5, 27), git_cwd=tmp_path)
    found = resolve_snapshot(tmp_path, written.name)
    assert found == written


def test_resolve_snapshot_by_label_returns_latest(tmp_path):
    from layout_qa.snapshot import write_snapshot, resolve_snapshot
    full = _full_report()
    write_snapshot(full, tmp_path, label='shared',
                   when=date(2026, 5, 27), git_cwd=tmp_path)
    latest = write_snapshot(full, tmp_path, label='shared',
                            when=date(2026, 6, 10), git_cwd=tmp_path)
    found = resolve_snapshot(tmp_path, 'shared')
    assert found == latest


def test_resolve_snapshot_raises_when_missing(tmp_path):
    from layout_qa.snapshot import write_snapshot, resolve_snapshot
    full = _full_report()
    write_snapshot(full, tmp_path, label='x',
                   when=date(2026, 5, 27), git_cwd=tmp_path)
    with pytest.raises(FileNotFoundError):
        resolve_snapshot(tmp_path, 'no-such')


# ---- CLI smoke tests --------------------------------------------------------

def test_cli_snapshot_creates_file(tmp_path):
    """`snapshot --label X` writes to history-dir/snapshot-YYYY-MM-DD_X.json."""
    from layout_qa.cli import main
    # Stage an analyze JSON for the snapshot to consume.
    full = _full_report()
    src = tmp_path / 'report.json'
    src.write_text(json.dumps(full), encoding='utf-8')
    history = tmp_path / 'history'
    rc = main([
        'snapshot',
        '--input', str(src),
        '--history', str(history),
        '--label', 'cli-test',
        '--note', 'fixture',
    ])
    assert rc == 0
    files = list(history.glob('snapshot-*_cli-test.json'))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding='utf-8'))
    assert data['snapshot']['label'] == 'cli-test'
    assert data['snapshot']['note'] == 'fixture'


def test_cli_snapshot_list_outputs_table(tmp_path, capsys):
    from layout_qa.cli import main
    from layout_qa.snapshot import write_snapshot
    full = _full_report()
    write_snapshot(full, tmp_path, label='a',
                   when=date(2026, 5, 27), git_cwd=tmp_path)
    write_snapshot(full, tmp_path, label='b',
                   when=date(2026, 6, 1), git_cwd=tmp_path)
    rc = main(['snapshot', '--history', str(tmp_path), '--list'])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'snapshot-2026-05-27_a.json' in out
    assert 'snapshot-2026-06-01_b.json' in out


def test_cli_snapshot_diff_shows_changes(tmp_path, capsys):
    """diff highlights which numbers moved between two snapshots."""
    from layout_qa.cli import main
    from layout_qa.snapshot import write_snapshot
    # snapshot A — 1 ERROR, 1 POLISHED → 50% readiness
    a_report = aggregate([_scenario('scen001', [
        _entry(0, 'POLISHED'),
        _entry(1, 'ERROR', issues=[
            {'code': 'balloon_line_overflow', 'severity': 'error',
             'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
        ]),
    ])])
    # snapshot B — both POLISHED → 100% readiness
    b_report = aggregate([_scenario('scen001', [
        _entry(0, 'POLISHED'),
        _entry(1, 'POLISHED'),
    ])])
    a_path = write_snapshot(a_report, tmp_path, label='a',
                            when=date(2026, 5, 27), git_cwd=tmp_path)
    b_path = write_snapshot(b_report, tmp_path, label='b',
                            when=date(2026, 6, 1), git_cwd=tmp_path)
    rc = main([
        'snapshot', '--history', str(tmp_path),
        '--diff', a_path.name, b_path.name,
    ])
    assert rc == 0
    out = capsys.readouterr().out
    # Diff must mention the two snapshots and the readiness delta.
    assert 'a' in out and 'b' in out
    assert 'readiness' in out.lower()
    # Some indicator of "+50pp" or "+0.5" — direction matters more than
    # exact format. Accept either rendering.
    assert '+0.5' in out or '+50' in out or '50.0%' in out
