"""test_layout_qa_worklist.py — worklist row build + CSV/MD writers."""

import csv
import json
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.cli import main  # noqa: E402
from layout_qa.worklist import (  # noqa: E402
    build_worklist, write_csv, write_markdown, load_report,
    _normalize_snippet, CSV_FIELDS,
)


# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------

def _make_report(scenarios):
    return {
        'schemaVersion': '0.1.0',
        'scenarios': scenarios,
    }


def _entry(index, profile='DIALOGUE_12X4', issues=None, usage=None):
    return {
        'index': index,
        'profile': profile,
        'tileUsage': usage or {
            'budget': [12, 4], 'linesUsed': 5, 'maxLine': 11, 'minLine': 5,
        },
        'issues': issues or [],
    }


def _overflow_issue(balloon, actual, max_lines):
    return {
        'code': 'balloon_line_overflow',
        'severity': 'error',
        'detail': {'balloon': balloon, 'actualLines': actual, 'maxLines': max_lines},
    }


@pytest.fixture
def fake_scripts(tmp_path):
    """Build a minimal scripts dir with three entries we can snippet from."""
    d = tmp_path / 'scripts_en'
    d.mkdir()
    (d / 'scen042E.txt').write_text(
        'Hello world<$FFFE>\n'
        'Second entry has more content here<$FFFE>\n'
        'Third<$FFFE>\n',
        encoding='utf-8',
    )
    return d


# ---------------------------------------------------------------------------
# _normalize_snippet
# ---------------------------------------------------------------------------

def test_normalize_snippet_collapses_whitespace():
    assert _normalize_snippet('hello   world\nfoo') == 'hello world foo'


def test_normalize_snippet_truncates():
    s = _normalize_snippet('x' * 200, max_len=20)
    assert len(s) <= 20
    assert s.endswith('…')


# ---------------------------------------------------------------------------
# build_worklist
# ---------------------------------------------------------------------------

def test_build_worklist_empty_report(tmp_path):
    rows = build_worklist(_make_report([]), tmp_path)
    assert rows == []


def test_build_worklist_filters_to_overflow_only(fake_scripts):
    report = _make_report([{
        'id': 'scen042',
        'entries': [
            _entry(0, issues=[
                {'code': 'low_line_usage', 'severity': 'warning', 'detail': {}},
            ]),
            _entry(1, issues=[_overflow_issue(0, 5, 4)]),
        ],
    }])
    rows = build_worklist(report, fake_scripts)
    assert len(rows) == 1
    assert rows[0].entry == 1
    assert rows[0].lines_over == 1


def test_build_worklist_one_row_per_overflow_balloon(fake_scripts):
    """An entry with two overflowing balloons yields two rows."""
    report = _make_report([{
        'id': 'scen042',
        'entries': [_entry(1, issues=[
            _overflow_issue(0, 5, 4),
            _overflow_issue(1, 6, 4),
        ])],
    }])
    rows = build_worklist(report, fake_scripts)
    assert len(rows) == 2
    assert sorted(r.balloon for r in rows) == [0, 1]


def test_build_worklist_dedups_per_balloon_keeping_worst(fake_scripts):
    """The simulator emits one overflow issue per line that spills past
    the cap, all referencing the same balloon. The worklist collapses
    those into one row and keeps the worst actualLines."""
    report = _make_report([{
        'id': 'scen042',
        'entries': [_entry(0, issues=[
            _overflow_issue(0, 5, 4),
            _overflow_issue(0, 6, 4),
            _overflow_issue(0, 7, 4),
        ])],
    }])
    rows = build_worklist(report, fake_scripts)
    assert len(rows) == 1
    assert rows[0].actual_lines == 7
    assert rows[0].lines_over == 3


def test_build_worklist_ranking(fake_scripts):
    """Bigger linesOver wins; tie broken by linesUsed desc."""
    report = _make_report([{
        'id': 'scen042',
        'entries': [
            _entry(0, issues=[_overflow_issue(0, 5, 4)],   # over=1, used=5
                   usage={'budget': [12, 4], 'linesUsed': 5, 'maxLine': 12, 'minLine': 5}),
            _entry(1, issues=[_overflow_issue(0, 7, 4)],   # over=3, used=7
                   usage={'budget': [12, 4], 'linesUsed': 7, 'maxLine': 12, 'minLine': 5}),
            _entry(2, issues=[_overflow_issue(0, 6, 4)],   # over=2, used=8
                   usage={'budget': [12, 4], 'linesUsed': 8, 'maxLine': 12, 'minLine': 5}),
        ],
    }])
    rows = build_worklist(report, fake_scripts)
    assert [r.entry for r in rows] == [1, 2, 0]


def test_build_worklist_snippet_from_source(fake_scripts):
    """Snippet comes from visible-text of the matching scen/entry."""
    report = _make_report([{
        'id': 'scen042',
        'entries': [_entry(1, issues=[_overflow_issue(0, 5, 4)])],
    }])
    rows = build_worklist(report, fake_scripts)
    assert rows[0].snippet.startswith('Second entry has')


# ---------------------------------------------------------------------------
# write_csv / write_markdown
# ---------------------------------------------------------------------------

def test_write_csv_header_and_rows(fake_scripts, tmp_path):
    report = _make_report([{
        'id': 'scen042',
        'entries': [_entry(0, issues=[_overflow_issue(0, 5, 4)])],
    }])
    rows = build_worklist(report, fake_scripts)
    out = tmp_path / 'work.csv'
    n = write_csv(rows, out)
    assert n == 1
    with out.open(encoding='utf-8') as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == CSV_FIELDS
        data = list(reader)
    assert data[0]['scen'] == 'scen042'
    assert data[0]['actualLines'] == '5'
    assert data[0]['linesOver'] == '1'


def test_write_markdown_top_n_and_header(fake_scripts, tmp_path):
    report = _make_report([{
        'id': 'scen042',
        'entries': [
            _entry(i, issues=[_overflow_issue(0, 5 + i, 4)])
            for i in range(5)
        ],
    }])
    rows = build_worklist(report, fake_scripts)
    out = tmp_path / 'work.md'
    n = write_markdown(rows, out, top_n=2)
    assert n == 2
    body = out.read_text(encoding='utf-8')
    assert '# Layout QA — Rewrite Worklist' in body
    assert 'Total `balloon_line_overflow` rows after optimal wrap: **5**' in body
    assert 'Showing top **2**' in body
    # Exactly 2 data rows in the table (lines starting '| 1 ' / '| 2 ').
    assert body.count('\n| 1 |') == 1
    assert body.count('\n| 2 |') == 1
    assert '\n| 3 |' not in body


def test_write_markdown_escapes_pipe(fake_scripts, tmp_path):
    report = _make_report([{
        'id': 'scen042',
        'entries': [_entry(0, issues=[_overflow_issue(0, 5, 4)])],
    }])
    rows = build_worklist(report, fake_scripts)
    rows[0].snippet = 'a | b'
    out = tmp_path / 'work.md'
    write_markdown(rows, out)
    body = out.read_text(encoding='utf-8')
    assert 'a \\| b' in body


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def test_cli_worklist_end_to_end(fake_scripts, tmp_path):
    """Run `worklist` against a minimal report fixture file."""
    report = _make_report([{
        'id': 'scen042',
        'entries': [
            _entry(0, issues=[_overflow_issue(0, 5, 4)]),
            _entry(1, issues=[_overflow_issue(0, 6, 4)]),
        ],
    }])
    in_path = tmp_path / 'report.json'
    in_path.write_text(json.dumps(report), encoding='utf-8')
    csv_out = tmp_path / 'out.csv'
    md_out = tmp_path / 'out.md'
    rc = main([
        'worklist',
        '--input', str(in_path),
        '--scripts', str(fake_scripts),
        '--csv', str(csv_out),
        '--md', str(md_out),
        '--top', '10',
    ])
    assert rc == 0
    assert csv_out.exists()
    assert md_out.exists()
    with csv_out.open(encoding='utf-8') as f:
        data = list(csv.DictReader(f))
    assert len(data) == 2


def test_cli_worklist_missing_input(tmp_path):
    rc = main(['worklist', '--input', str(tmp_path / 'no-such.json'),
               '--scripts', str(tmp_path)])
    assert rc == 3
