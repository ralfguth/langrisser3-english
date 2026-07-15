"""test_layout_qa_readiness.py — projectSummary in aggregate + report
subcommand markdown rendering."""

import json
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.cli import main  # noqa: E402
from layout_qa.metrics import aggregate, validate_schema  # noqa: E402
from layout_qa.readiness import (  # noqa: E402
    render_markdown, write_markdown, READINESS_BLOCKERS, POLISH_BLOCKERS,
)


# ---------------------------------------------------------------------------
# helpers
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
            'budget': [12, 4],
            'maxLine': 5, 'minLine': 5,
            'avgLine': 5.0, 'avgFillRatio': 0.4167,
            'linesUsed': 1,
        },
        'issues': issues or [],
    }


def _scenario(scen_id, entries):
    return {'id': scen_id, 'path': f'scripts/en/{scen_id}E.txt', 'entries': entries}


# ---------------------------------------------------------------------------
# projectSummary block (aggregate emits it)
# ---------------------------------------------------------------------------

def test_aggregate_emits_project_summary_block():
    scenarios = [
        _scenario('scen001', [
            _entry(0, 'POLISHED'),
            _entry(1, 'PLAYABLE',
                   issues=[{'code': 'low_line_usage', 'severity': 'warning'}]),
            _entry(2, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        ]),
        _scenario('scen002', [
            _entry(0, 'POLISHED'),
            _entry(1, 'POLISHED'),
        ]),
    ]
    report = aggregate(scenarios)
    ps = report['projectSummary']
    assert ps['filesAnalyzed'] == 2
    assert ps['entriesAnalyzed'] == 5
    assert ps['entriesError'] == 1
    assert ps['entriesPlayable'] == 1
    assert ps['entriesPolished'] == 3
    # readiness = (1 playable + 3 polished) / 5 = 0.8
    assert ps['playabilityRate'] == 0.8
    # polish = 3 / 5 = 0.6
    assert ps['polishRate'] == 0.6


def test_aggregate_empty_corpus_project_summary_is_vacuous():
    report = aggregate([])
    ps = report['projectSummary']
    assert ps['filesAnalyzed'] == 0
    assert ps['entriesAnalyzed'] == 0
    assert ps['playabilityRate'] == 1.0
    assert ps['polishRate'] == 1.0


def test_aggregate_project_summary_passes_schema():
    report = aggregate([_scenario('scen001', [_entry(0)])])
    errs = validate_schema(report)
    assert errs == [], errs


def test_validate_schema_catches_missing_project_summary():
    report = aggregate([_scenario('scen001', [_entry(0)])])
    del report['projectSummary']
    errs = validate_schema(report)
    assert any('projectSummary' in e for e in errs)


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------

def test_render_markdown_includes_headlines_and_metrics():
    report = aggregate([
        _scenario('scen001', [
            _entry(0, 'POLISHED'),
            _entry(1, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        ]),
    ])
    md = render_markdown(report)
    assert '# Layout QA — Readiness Report' in md
    assert '## Project summary' in md
    assert '## Readiness vs Polish' in md
    assert '## Status breakdown' in md
    assert '## By profile' in md
    assert '## Issues' in md
    # Headline numbers visible — every count carries its unit.
    assert 'Files analyzed: **1 files**' in md
    assert 'Entries analyzed: **2 entries**' in md
    # Readiness % must round to 50.0%; polish to 50.0%.
    assert '50.0%' in md


def test_render_markdown_calls_out_readiness_vs_polish_blockers():
    """Every blocker code must appear in its respective section so a
    human can see which issues gate readiness vs polish."""
    report = aggregate([_scenario('scen001', [_entry(0)])])
    md = render_markdown(report)
    for code in READINESS_BLOCKERS:
        assert code in md, f'readiness blocker {code} missing'
    for code in POLISH_BLOCKERS:
        assert code in md, f'polish blocker {code} missing'


def test_render_markdown_worst_files_section():
    report = aggregate([
        _scenario('scen001', [_entry(0, 'POLISHED')] * 10),
        _scenario('scen002', [
            _entry(0, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        ]),
    ])
    md = render_markdown(report, top_n_files=5)
    assert 'Worst' in md
    # scen002 (100% error) ranks worse than scen001 → must appear in the
    # readiness ranking table; scen001 is 100% playable so it appears in
    # the polish ranking (but it's 100% polish too, so excluded).
    assert 'scen002' in md


def test_render_markdown_back_compat_no_project_summary():
    """If a caller has an older JSON without projectSummary, the renderer
    must derive it from the summary block instead of crashing."""
    report = aggregate([_scenario('scen001', [_entry(0)])])
    del report['projectSummary']
    md = render_markdown(report)
    assert 'Files analyzed: **1 files**' in md


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def test_cli_report_end_to_end(tmp_path):
    report = aggregate([
        _scenario('scen001', [_entry(0, 'POLISHED'), _entry(1, 'POLISHED')]),
    ])
    in_path = tmp_path / 'report.json'
    in_path.write_text(json.dumps(report), encoding='utf-8')
    out_path = tmp_path / 'readiness.md'
    rc = main([
        'report',
        '--input', str(in_path),
        '--output', str(out_path),
        '--top', '5',
    ])
    assert rc == 0
    assert out_path.exists()
    body = out_path.read_text(encoding='utf-8')
    assert '# Layout QA — Readiness Report' in body
    assert 'scen001' not in body or 'Worst' in body  # scen001 is 100% polished


def test_cli_report_missing_input(tmp_path):
    rc = main(['report', '--input', str(tmp_path / 'nope.json')])
    assert rc == 3


# ===========================================================================
# CLI report orchestration (single honest source report)
# ===========================================================================

def test_cli_report_source_only(tmp_path):
    """--source given → single-state dashboard."""
    source = aggregate([_scenario('scen001', [_entry(0, 'POLISHED')])])
    src_path = tmp_path / 'source.json'
    out_path = tmp_path / 'out.md'
    src_path.write_text(json.dumps(source), encoding='utf-8')
    rc = main([
        'report',
        '--source', str(src_path),
        '--output', str(out_path),
    ])
    assert rc == 0
    body = out_path.read_text(encoding='utf-8')
    assert '## Project summary' in body


# ===========================================================================
# Phase 1 (TDD red): per-issue scope at three granularities
# ---------------------------------------------------------------------------
# Per user spec 2026-05-27: every metric must declare its unit.
# `byIssueScope` for each issue code carries:
#   - occurrences      (raw count — was `count` in 0.1.0)
#   - entriesAffected  (unique (scen, entry_index) tuples)
#   - filesAffected    (unique scen ids)
#   - balloonsAffected (unique (scen, entry, balloon) tuples — only
#                       meaningful for codes whose detail carries a
#                       `balloon` field, e.g. balloon_line_overflow)
# ===========================================================================

def test_by_issue_scope_has_entries_affected():
    """A single entry with two balloon_line_overflow issues counts as
    1 entryAffected, not 2 (entries are unique by (scen, idx))."""
    issues = [
        {'code': 'balloon_line_overflow', 'severity': 'error',
         'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
        {'code': 'balloon_line_overflow', 'severity': 'error',
         'detail': {'balloon': 0, 'actualLines': 6, 'maxLines': 4}},
    ]
    report = aggregate([_scenario('scen001', [_entry(0, 'ERROR', issues=issues)])])
    scope = report['summary']['byIssueScope']['balloon_line_overflow']
    assert scope['occurrences'] == 2
    assert scope['entriesAffected'] == 1
    assert scope['filesAffected'] == 1


def test_by_issue_scope_counts_distinct_entries():
    """Two entries in same scen, each with one overflow → entriesAffected = 2."""
    report = aggregate([_scenario('scen001', [
        _entry(0, 'ERROR', issues=[
            {'code': 'balloon_line_overflow', 'severity': 'error',
             'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
        ]),
        _entry(1, 'ERROR', issues=[
            {'code': 'balloon_line_overflow', 'severity': 'error',
             'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
        ]),
    ])])
    scope = report['summary']['byIssueScope']['balloon_line_overflow']
    assert scope['occurrences'] == 2
    assert scope['entriesAffected'] == 2
    assert scope['filesAffected'] == 1


def test_by_issue_scope_balloons_affected_for_overflow():
    """Two overflow issues in the same balloon = 1 balloonAffected.
    Two overflow issues in distinct balloons of the same entry = 2."""
    issues = [
        # Same balloon (0), two spilled lines → same balloonAffected.
        {'code': 'balloon_line_overflow', 'severity': 'error',
         'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
        {'code': 'balloon_line_overflow', 'severity': 'error',
         'detail': {'balloon': 0, 'actualLines': 6, 'maxLines': 4}},
        # Different balloon (1) → another balloonAffected.
        {'code': 'balloon_line_overflow', 'severity': 'error',
         'detail': {'balloon': 1, 'actualLines': 5, 'maxLines': 4}},
    ]
    report = aggregate([_scenario('scen001', [_entry(0, 'ERROR', issues=issues)])])
    scope = report['summary']['byIssueScope']['balloon_line_overflow']
    assert scope['occurrences'] == 3
    assert scope['entriesAffected'] == 1
    assert scope['balloonsAffected'] == 2


def test_by_issue_scope_balloons_affected_zero_for_non_balloon_codes():
    """Codes without a balloon field in detail report balloonsAffected=0."""
    issues = [
        {'code': 'label_overflow', 'severity': 'error',
         'detail': {'tilesUsed': 14, 'budget': 12}},
    ]
    report = aggregate([_scenario('scen001', [
        _entry(0, 'ERROR', profile='LABEL_CHARACTER_12X1', issues=issues),
    ])])
    scope = report['summary']['byIssueScope']['label_overflow']
    assert scope['occurrences'] == 1
    assert scope['entriesAffected'] == 1
    assert scope['balloonsAffected'] == 0


def test_by_issue_scope_back_compat_count_alias():
    """`count` field stays for callers from schema 0.1.0; equal to occurrences."""
    issues = [
        {'code': 'balloon_line_overflow', 'severity': 'error',
         'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
    ]
    report = aggregate([_scenario('scen001', [_entry(0, 'ERROR', issues=issues)])])
    scope = report['summary']['byIssueScope']['balloon_line_overflow']
    assert scope['count'] == scope['occurrences']


def test_schema_version_is_0_3_1():
    """0.3.1: adds the `line_padding_space` issue code (warning) to the
    closed IssueCode enum. Emitted for DIALOGUE-style profiles whose text
    is meant to flow naturally — flags trailing space on non-last lines
    and leading space on non-first lines (i.e. a wrap that did not
    consume the space). Profiles that use bigram-trick spacing for layout
    (NARRATION, OBJECTIVE, LABEL_*) opt out via 'enforce_line_padding'.
    Earlier additive bumps: 0.2.0 added entriesAffected/balloonsAffected
    + projectSummary; 0.3.0 added balloons[*].lines[*] + the optional
    `jp` field per entry."""
    report = aggregate([_scenario('scen001', [_entry(0)])])
    assert report['schemaVersion'] == '0.3.1'


# ===========================================================================
# Single-source readiness dashboard (the wrapped/tripartite projection was
# removed — it was computed on space-corrupting shadow copies).
# ===========================================================================

def _err_overflow_issue(balloon=0):
    return {'code': 'balloon_line_overflow', 'severity': 'error',
            'detail': {'balloon': balloon, 'actualLines': 5, 'maxLines': 4}}


def test_render_markdown_single_report():
    """render_markdown(source) renders the project summary and no longer
    emits any wrap-potential / tripartite chatter."""
    source = aggregate([_scenario('scen001', [_entry(0, 'POLISHED')])])
    md = render_markdown(source)
    assert '## Project summary' in md
    assert 'WRAP POTENTIAL' not in md
    assert 'IRREDUCIBLE' not in md
    assert '## State of the patch' not in md


# ===========================================================================
# Phase 3 (TDD red): per-file aggregates inside scenarios[*]
# ---------------------------------------------------------------------------
# A React/ECharts dashboard should be able to render any per-file view
# without recomputing rates from byStatus. Each scenario carries:
#   - readinessRate, polishRate (derived once, in metrics.aggregate)
#   - byIssue: {code: occurrences} so per-file drill-down is one
#     indexed lookup instead of a full entries[].issues[] scan.
# ===========================================================================

def test_scenario_carries_readiness_polish_rates():
    """One ERROR + one POLISHED entry in scen001 → readiness 50%, polish 50%."""
    report = aggregate([_scenario('scen001', [
        _entry(0, 'ERROR', issues=[
            {'code': 'balloon_line_overflow', 'severity': 'error',
             'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
        ]),
        _entry(1, 'POLISHED'),
    ])])
    sc = report['scenarios'][0]
    assert sc['readinessRate'] == 0.5
    assert sc['polishRate'] == 0.5


def test_scenario_rates_empty_file_is_vacuous_one():
    """A file with zero entries — vacuous truth 100% on both."""
    report = aggregate([_scenario('scen001', [])])
    sc = report['scenarios'][0]
    assert sc['readinessRate'] == 1.0
    assert sc['polishRate'] == 1.0


def test_scenario_carries_by_issue_breakdown():
    """Each scenario records occurrences per code so a per-file drill-down
    doesn't have to walk entries[].issues[]."""
    report = aggregate([_scenario('scen001', [
        _entry(0, 'ERROR', issues=[
            {'code': 'balloon_line_overflow', 'severity': 'error',
             'detail': {'balloon': 0, 'actualLines': 5, 'maxLines': 4}},
        ]),
        _entry(1, 'PLAYABLE', issues=[
            {'code': 'low_line_usage', 'severity': 'warning'},
            {'code': 'low_line_usage', 'severity': 'warning'},
        ]),
    ])])
    sc = report['scenarios'][0]
    assert sc['byIssue']['balloon_line_overflow'] == 1
    assert sc['byIssue']['low_line_usage'] == 2
    # Codes with zero occurrences are still present (stable shape).
    assert sc['byIssue']['broken_word_wrap'] == 0


def test_scenario_byissue_covers_all_codes():
    """Every ISSUE_CODES key appears in per-scenario byIssue, even when 0,
    so the React dashboard doesn't have to defensive-default."""
    from layout_qa.metrics import ISSUE_CODES
    report = aggregate([_scenario('scen001', [_entry(0)])])
    sc = report['scenarios'][0]
    for code in ISSUE_CODES:
        assert code in sc['byIssue']


def test_render_markdown_unit_labels_in_table_headers():
    """Every count column header must declare its unit explicitly so a
    reader knows whether the number is entries / balloons / lines /
    occurrences / files."""
    source = aggregate([_scenario('scen001', [
        _entry(0, 'ERROR', issues=[_err_overflow_issue()]),
    ])])
    md = render_markdown(source)
    # Status breakdown must label its 'count' column as entries.
    # By-profile table must label tile/line columns.
    # Issues table must distinguish occurrences vs entriesAffected.
    assert 'entries' in md
    # Distinguish occurrences from entriesAffected somewhere in the
    # issues table.
    assert 'occurrences' in md.lower() or 'entriesAffected' in md
    assert 'entriesAffected' in md or 'entries affected' in md.lower()


# ---------------------------------------------------------------------------
# Expanded aggregates: byProfileStatus, byIssueScope, lineUtilization,
# overridesApplied
# ---------------------------------------------------------------------------

def test_aggregate_by_profile_status_split():
    """Each profile must carry its own ERROR/PLAYABLE/POLISHED counts +
    readiness/polish rates derived from those counts."""
    scenarios = [_scenario('scen001', [
        _entry(0, 'POLISHED', profile='DIALOGUE_12X4'),
        _entry(1, 'ERROR', profile='DIALOGUE_12X4',
               issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        _entry(2, 'POLISHED', profile='NARRATION_16X5'),
        _entry(3, 'POLISHED', profile='NARRATION_16X5'),
    ])]
    report = aggregate(scenarios)
    bps = report['summary']['byProfileStatus']
    assert bps['DIALOGUE_12X4']['total'] == 2
    assert bps['DIALOGUE_12X4']['ERROR'] == 1
    assert bps['DIALOGUE_12X4']['POLISHED'] == 1
    assert bps['DIALOGUE_12X4']['readiness'] == 0.5
    assert bps['DIALOGUE_12X4']['polish'] == 0.5
    assert bps['NARRATION_16X5']['total'] == 2
    assert bps['NARRATION_16X5']['readiness'] == 1.0
    assert bps['NARRATION_16X5']['polish'] == 1.0
    # Profiles with zero entries get vacuous-truth 100%.
    assert bps['OBJECTIVE_16X5']['total'] == 0
    assert bps['OBJECTIVE_16X5']['readiness'] == 1.0


def test_aggregate_by_issue_scope_counts_files():
    """filesAffected = unique scen ids touched by each issue code."""
    report = aggregate([
        _scenario('scen001', [
            _entry(0, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
            _entry(1, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        ]),
        _scenario('scen002', [
            _entry(0, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        ]),
        _scenario('scen003', [_entry(0, 'POLISHED')]),
    ])
    scope = report['summary']['byIssueScope']
    assert scope['balloon_line_overflow']['count'] == 3
    assert scope['balloon_line_overflow']['filesAffected'] == 2  # scen001, scen002
    assert scope['broken_word_wrap']['count'] == 0
    assert scope['broken_word_wrap']['filesAffected'] == 0


def test_aggregate_line_utilization_per_profile():
    """avgLine + avgFillRatio derived from each entry's tileUsage.
    avgFillRatio is the corpus mean of per-entry avg fill (mean of
    means), and avgFillRatioOfMaxLine keeps the legacy worst-line view.
    """
    e1 = _entry(0, profile='DIALOGUE_12X4')
    e1['tileUsage'] = {
        'budget': [12, 4], 'maxLine': 6, 'minLine': 6,
        'avgLine': 6.0, 'avgFillRatio': 0.5, 'linesUsed': 1,
    }
    e2 = _entry(1, profile='DIALOGUE_12X4')
    e2['tileUsage'] = {
        'budget': [12, 4], 'maxLine': 12, 'minLine': 12,
        'avgLine': 12.0, 'avgFillRatio': 1.0, 'linesUsed': 1,
    }
    report = aggregate([_scenario('scen001', [e1, e2])])
    lu = report['summary']['lineUtilization']['DIALOGUE_12X4']
    assert lu['samples'] == 2
    assert lu['avgMaxLine'] == 9.0          # mean of max lines
    assert lu['avgLine'] == 9.0             # mean of avg per-entry lines
    assert lu['avgFillRatio'] == 0.75       # mean of per-entry avg fills
    assert lu['avgFillRatioOfMaxLine'] == 0.75  # mean of (maxLine / width)


def test_aggregate_overrides_applied_threaded():
    report = aggregate(
        [_scenario('scen124', [_entry(0)])],
        overrides_applied=['scen124'],
    )
    assert report['summary']['overridesApplied'] == ['scen124']


def test_aggregate_overrides_applied_default_empty():
    report = aggregate([_scenario('scen001', [_entry(0)])])
    assert report['summary']['overridesApplied'] == []


# ---------------------------------------------------------------------------
# Expanded markdown sections
# ---------------------------------------------------------------------------

def test_render_markdown_next_actions_lists_top_blockers():
    report = aggregate([_scenario('scen001', [
        _entry(0, 'ERROR',
               issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        _entry(1, 'ERROR',
               issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        _entry(2, 'PLAYABLE',
               issues=[{'code': 'low_line_usage', 'severity': 'warning'}]),
    ])])
    md = render_markdown(report)
    assert '## Next actions' in md
    assert 'Top readiness blockers' in md
    assert '`balloon_line_overflow` × 2' in md
    assert 'Top polish blockers' in md
    assert '`low_line_usage` × 1' in md


def test_render_markdown_next_actions_lists_top_files_by_absolute_errors():
    report = aggregate([
        _scenario('scen001', [
            _entry(i, 'ERROR' if i < 10 else 'POLISHED',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]
                   if i < 10 else [])
            for i in range(20)
        ]),
        _scenario('scen002', [
            _entry(0, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        ]),
    ])
    md = render_markdown(report)
    assert 'Top files by absolute errors' in md
    assert 'scen001' in md
    # scen001 has 10 errors → appears before scen002 (1 error) in this list.
    pos1 = md.find('`scen001`')
    pos2 = md.find('`scen002`')
    assert 0 < pos1 < pos2


def test_render_markdown_per_profile_status_table():
    report = aggregate([_scenario('scen001', [
        _entry(0, 'ERROR', profile='DIALOGUE_12X4',
               issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        _entry(1, 'POLISHED', profile='NARRATION_16X5'),
    ])])
    md = render_markdown(report)
    assert '## By profile' in md
    # Per-entry avg line, plus the legacy worst-line view.
    assert 'avgLine' in md
    assert 'avgFill' in md
    assert 'avgMaxLine' in md
    assert 'avgMaxFill' in md
    # Both profiles render in the table.
    assert 'DIALOGUE_12X4' in md
    assert 'NARRATION_16X5' in md


def test_render_markdown_issue_table_has_file_coverage():
    report = aggregate([
        _scenario('scen001', [
            _entry(0, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        ]),
        _scenario('scen002', [
            _entry(0, 'ERROR',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        ]),
    ])
    md = render_markdown(report)
    # Find the Issues table line for balloon_line_overflow.
    issues_section = md.split('## Issues')[1].split('##')[0]
    # Should contain the count (2) and filesAffected (2).
    assert 'balloon_line_overflow' in issues_section
    assert 'filesAffected' in issues_section


def test_render_markdown_worst_by_absolute_errors_section():
    report = aggregate([
        _scenario('scen001', [
            _entry(i, 'ERROR' if i < 3 else 'POLISHED',
                   issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]
                   if i < 3 else [])
            for i in range(20)
        ]),
    ])
    md = render_markdown(report)
    assert 'Worst' in md and 'by absolute errors' in md


def test_render_markdown_active_overrides_section():
    report = aggregate(
        [_scenario('scen124', [_entry(0)])],
        overrides_applied=['scen124'],
    )
    md = render_markdown(report)
    assert '## Active layout overrides' in md
    assert '`scen124`' in md


def test_render_markdown_no_overrides_no_section():
    report = aggregate([_scenario('scen001', [_entry(0)])])
    md = render_markdown(report)
    assert '## Active layout overrides' not in md


def test_render_markdown_distance_to_100_pct():
    report = aggregate([_scenario('scen001', [
        _entry(0, 'ERROR',
               issues=[{'code': 'balloon_line_overflow', 'severity': 'error'}]),
        _entry(1, 'PLAYABLE',
               issues=[{'code': 'low_line_usage', 'severity': 'warning'}]),
        _entry(2, 'POLISHED'),
    ])])
    md = render_markdown(report)
    assert 'Distance to 100% readiness: **1 entries**' in md
    # polish gap = error + playable = 2
    assert 'Distance to 100% polish: **2 entries**' in md
