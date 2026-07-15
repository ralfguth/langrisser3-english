"""metrics.py — aggregate simulator output into the final JSON shape.

Three responsibilities:
  1. Bucket each entry's issues into one of three status values:
       ERROR    — any issue with severity 'error', or profile=UNKNOWN.
       PLAYABLE — only warnings present, no errors.
       POLISHED — no errors and no warnings (severity 'info' advisories,
                  e.g. fluidity_headroom, are allowed and do not demote).
  2. Compute summary metrics over a list of entries:
       playabilityRate = (PLAYABLE + POLISHED) / total
       polishRate      = POLISHED / total
  3. Render the full report JSON per spec v0.1.0
     (see lang3_local_docs/langrisser-layout-qa-spec-draft/05-metrics-json.md).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal

from layout_qa import SCHEMA_VERSION


Status = Literal['ERROR', 'PLAYABLE', 'POLISHED']


# Lock the issue catalog so the JSON `summary.byIssue` keys are stable.
ISSUE_CODES = (
    'line_budget_exceeded',
    'label_overflow',
    'balloon_line_overflow',
    'broken_word_wrap',
    'unknown_layout_profile',
    # CHOICE-fit errors — player-facing menu options (see layout_qa.choices).
    # A CHOICE entry is one line minus the 1-tile selection cursor; it must
    # not overflow that budget or wrap to a second line (it would spill into
    # the next option's slot).
    'choice_overflow',
    'choice_multiline',
    'implicit_wrap_without_fffc',
    # Spoken-punctuation gate: `:` `;` `—` are forbidden in scen/plot prose
    # (written typography that breaks a localized read; em-dash isn't even in
    # the tile map). Error severity — blocks readiness like any layout error.
    'forbidden_punctuation',
    'low_line_usage',
    'fluidity_headroom',
    'special_token_overflow_risk',
    'encoding_risk',
    'line_padding_space',
)

PROFILE_NAMES = (
    'LABEL_CHARACTER_12X1',
    'LABEL_LOCATION_16X1',
    'OBJECTIVE_16X5',
    'NARRATION_16X5',
    'DIALOGUE_12X4',
    'HEROINE_DIARY',
    'UNKNOWN',
)

STATUS_VALUES = ('ERROR', 'PLAYABLE', 'POLISHED')


@dataclass
class EntryReport:
    """One entry's full report — feeds straight into the JSON 'entries' array."""
    index: int
    terminator: str
    profile: str
    semantic_subtype: str | None
    classification: Dict[str, Any]   # {confidence, reason, state}
    status: Status
    tile_usage: Dict[str, int]       # {maxLine, minLine, linesUsed, budget}
    issues: List[Dict[str, Any]]     # [{code, severity, detail}]


def bucket_status(issues: List[Dict[str, Any]], profile: str) -> Status:
    """Map (issues, profile) → ERROR / PLAYABLE / POLISHED.

    Issues are expected as dicts (serialized form) with 'severity' field.
    """
    if profile == 'UNKNOWN':
        return 'ERROR'
    if any(i.get('severity') == 'error' for i in issues):
        return 'ERROR'
    if any(i.get('severity') == 'warning' for i in issues):
        return 'PLAYABLE'
    return 'POLISHED'


def _zero_counter(keys) -> Dict[str, int]:
    return {k: 0 for k in keys}


def aggregate(
    scenarios: List[Dict[str, Any]],
    *,
    lang: str = 'en',
    now: _dt.datetime | None = None,
    overrides_applied: List[str] | None = None,
    exempt_applied: List[str] | None = None,
) -> Dict[str, Any]:
    """Compose the top-level report JSON from a list of per-scenario dicts.

    Each scenario dict must already contain:
        - 'id': str (e.g. 'scen019')
        - 'path': str (relative to repo root)
        - 'entries': list of EntryReport dicts

    `overrides_applied` is the list of scen ids whose profile was
    overridden via config/layout-overrides.json — recorded in the
    report so a dashboard can show which assumptions are in play.

    Returns the full top-level JSON shape matching schema v0.1.0
    plus additive aggregates (`byProfileStatus`, `byIssueScope`,
    `lineUtilization`, `overridesApplied`) consumed by the readiness
    reporter.
    """
    now = now or _dt.datetime.now(_dt.timezone.utc)

    total_entries = 0
    by_status = _zero_counter(STATUS_VALUES)
    by_profile = _zero_counter(PROFILE_NAMES)
    by_issue = _zero_counter(ISSUE_CODES)

    # Per-profile status split: how does each profile fare on its own?
    by_profile_status: Dict[str, Dict[str, int]] = {
        p: _zero_counter(STATUS_VALUES) for p in PROFILE_NAMES
    }
    # Per-issue scope sets — three granularities so the dashboard can
    # speak in the right unit:
    #   files     — unique scen ids
    #   entries   — unique (scen_id, entry_index) tuples
    #   balloons  — unique (scen_id, entry_index, balloon_index) tuples
    #                (only populated for codes whose detail carries a
    #                `balloon` field — primarily balloon_line_overflow)
    issue_files: Dict[str, set] = {c: set() for c in ISSUE_CODES}
    issue_entries: Dict[str, set] = {c: set() for c in ISSUE_CODES}
    issue_balloons: Dict[str, set] = {c: set() for c in ISSUE_CODES}
    # Per-profile line-utilization aggregator: list of
    # (maxLine, avgLine, avgFillRatio, width) tuples across entries with
    # that profile — feeds avgMaxLine, avgLineTiles, avgFillRatio in
    # the summary.
    line_util_acc: Dict[str, List[tuple]] = {p: [] for p in PROFILE_NAMES}

    out_scenarios: List[Dict[str, Any]] = []
    for sc in scenarios:
        per_status = _zero_counter(STATUS_VALUES)
        per_issue = _zero_counter(ISSUE_CODES)
        scen_id = sc['id']
        for er in sc['entries']:
            total_entries += 1
            status = er['status']
            by_status[status] += 1
            per_status[status] += 1
            prof = er.get('profile', 'UNKNOWN')
            if prof in by_profile:
                by_profile[prof] += 1
            else:
                by_profile['UNKNOWN'] += 1
            # Per-profile status counter — same UNKNOWN fallback.
            target = prof if prof in by_profile_status else 'UNKNOWN'
            by_profile_status[target][status] += 1
            # Line-utilization accumulator. Skip UNKNOWN (no budget) and
            # entries that didn't emit any line (rare, but defensive).
            tu = er.get('tileUsage') or {}
            budget = tu.get('budget') or [0, 0]
            width = int(budget[0]) if budget else 0
            max_line = int(tu.get('maxLine', 0))
            avg_line = float(tu.get('avgLine', 0))
            avg_fill = float(tu.get('avgFillRatio', 0))
            if width > 0 and max_line > 0:
                line_util_acc[target].append(
                    (max_line, avg_line, avg_fill, width)
                )
            entry_idx = er.get('index')
            for issue in er.get('issues', []):
                code = issue.get('code')
                if code in by_issue:
                    by_issue[code] += 1
                    per_issue[code] += 1
                    issue_files[code].add(scen_id)
                    issue_entries[code].add((scen_id, entry_idx))
                    balloon_idx = (issue.get('detail') or {}).get('balloon')
                    if balloon_idx is not None:
                        issue_balloons[code].add(
                            (scen_id, entry_idx, balloon_idx)
                        )
        n = len(sc['entries'])
        if n == 0:
            readiness_rate = 1.0
            polish_rate = 1.0
        else:
            readiness_rate = round(
                (per_status['PLAYABLE'] + per_status['POLISHED']) / n, 4
            )
            polish_rate = round(per_status['POLISHED'] / n, 4)
        out_sc = {
            'id': scen_id,
            'path': sc['path'],
            'entryCount': n,
            'byStatus': per_status,
            'byIssue': per_issue,
            'readinessRate': readiness_rate,
            'polishRate': polish_rate,
            'entries': sc['entries'],
        }
        if sc.get('exempt'):
            out_sc['exempt'] = True
            out_sc['exemptReason'] = sc.get('exemptReason', '')
        if sc.get('hasDiary'):
            out_sc['hasDiary'] = True
        out_scenarios.append(out_sc)

    # ---- Derived aggregates ---------------------------------------------
    by_profile_status_with_rates: Dict[str, Dict[str, Any]] = {}
    for prof, counts in by_profile_status.items():
        n = counts['ERROR'] + counts['PLAYABLE'] + counts['POLISHED']
        if n == 0:
            by_profile_status_with_rates[prof] = {
                **counts, 'total': 0, 'readiness': 1.0, 'polish': 1.0,
            }
            continue
        by_profile_status_with_rates[prof] = {
            **counts,
            'total': n,
            'readiness': round((counts['PLAYABLE'] + counts['POLISHED']) / n, 4),
            'polish': round(counts['POLISHED'] / n, 4),
        }

    by_issue_scope: Dict[str, Dict[str, int]] = {}
    for code in ISSUE_CODES:
        n = by_issue[code]
        by_issue_scope[code] = {
            # `count` kept as a 0.1.0-compatible alias for `occurrences`.
            'count': n,
            'occurrences': n,
            'entriesAffected': len(issue_entries[code]),
            'balloonsAffected': len(issue_balloons[code]),
            'filesAffected': len(issue_files[code]),
        }

    line_utilization: Dict[str, Dict[str, Any]] = {}
    for prof, samples in line_util_acc.items():
        if not samples:
            line_utilization[prof] = {
                'samples': 0,
                'avgMaxLine': 0.0,
                'avgLine': 0.0,
                'avgFillRatio': 0.0,
                'avgFillRatioOfMaxLine': 0.0,
            }
            continue
        # samples: (max_line, avg_line, avg_fill_per_entry, width)
        avg_max = sum(s[0] for s in samples) / len(samples)
        avg_line = sum(s[1] for s in samples) / len(samples)
        # Mean of per-entry avg_fill — the headline "how well used is
        # the budget across all lines, across all entries".
        avg_fill = sum(s[2] for s in samples) / len(samples)
        # Fill of the max line (kept for back-compat; was the old metric).
        avg_fill_max = sum(s[0] / s[3] for s in samples) / len(samples)
        line_utilization[prof] = {
            'samples': len(samples),
            'avgMaxLine': round(avg_max, 2),
            'avgLine': round(avg_line, 2),
            'avgFillRatio': round(avg_fill, 4),
            'avgFillRatioOfMaxLine': round(avg_fill_max, 4),
        }

    if total_entries == 0:
        # Vacuous truth — empty corpus is 100% playable + polished.
        playability_rate = 1.0
        polish_rate = 1.0
    else:
        playability_rate = (by_status['PLAYABLE'] + by_status['POLISHED']) / total_entries
        polish_rate = by_status['POLISHED'] / total_entries

    # Flat project-level headline numbers — same data as `summary` but
    # in a form that's trivial for a human / dashboard / LLM to consume
    # without descending into nested counters. Additive vs `summary`.
    project_summary = {
        'filesAnalyzed': len(out_scenarios),
        'entriesAnalyzed': total_entries,
        'entriesError': by_status['ERROR'],
        'entriesPlayable': by_status['PLAYABLE'],
        'entriesPolished': by_status['POLISHED'],
        'playabilityRate': round(playability_rate, 4),
        'polishRate': round(polish_rate, 4),
    }

    return {
        'schemaVersion': SCHEMA_VERSION,
        'generatedAt': now.isoformat(timespec='seconds'),
        'lang': lang,
        'tool': {'name': 'layout_qa', 'version': SCHEMA_VERSION},
        'projectSummary': project_summary,
        'summary': {
            'scenarioCount': len(out_scenarios),
            'entryCount': total_entries,
            'byStatus': by_status,
            'byProfile': by_profile,
            'byProfileStatus': by_profile_status_with_rates,
            'byIssue': by_issue,
            'byIssueScope': by_issue_scope,
            'lineUtilization': line_utilization,
            'playabilityRate': round(playability_rate, 4),
            'polishRate': round(polish_rate, 4),
            'overridesApplied': list(overrides_applied or []),
            'exemptScenarios': list(exempt_applied or []),
        },
        'scenarios': out_scenarios,
    }


# ---------------------------------------------------------------------------
# Schema validation (used by tests; also handy for ad-hoc CLI sanity)
# ---------------------------------------------------------------------------

def validate_schema(report: Dict[str, Any]) -> List[str]:
    """Return a list of schema-violation strings (empty = valid).

    Pins the v0.1.0 shape — if the dict is missing a required key, has
    a wrong type, or carries an unrecognized profile/status/issue key,
    each problem is one entry in the returned list.
    """
    errs: List[str] = []

    def req(d: Dict, key: str, type_: type, path: str):
        if key not in d:
            errs.append(f'{path}: missing key {key!r}')
            return False
        if not isinstance(d[key], type_):
            errs.append(f'{path}.{key}: expected {type_.__name__}, got {type(d[key]).__name__}')
            return False
        return True

    req(report, 'schemaVersion', str, '$')
    req(report, 'generatedAt', str, '$')
    req(report, 'lang', str, '$')
    if req(report, 'tool', dict, '$'):
        req(report['tool'], 'name', str, '$.tool')
        req(report['tool'], 'version', str, '$.tool')

    if req(report, 'projectSummary', dict, '$'):
        ps = report['projectSummary']
        for k in ('filesAnalyzed', 'entriesAnalyzed',
                  'entriesError', 'entriesPlayable', 'entriesPolished'):
            req(ps, k, int, '$.projectSummary')
        for k in ('playabilityRate', 'polishRate'):
            req(ps, k, (int, float), '$.projectSummary')
            if k in ps and not (0 <= ps[k] <= 1):
                errs.append(f'$.projectSummary.{k}: out of range [0,1]')

    if req(report, 'summary', dict, '$'):
        s = report['summary']
        for k in ('scenarioCount', 'entryCount'):
            req(s, k, int, '$.summary')
        for k in ('playabilityRate', 'polishRate'):
            req(s, k, (int, float), '$.summary')
            if k in s and not (0 <= s[k] <= 1):
                errs.append(f'$.summary.{k}: out of range [0,1]')
        for bucket_name, expected_keys in (
            ('byStatus', STATUS_VALUES),
            ('byProfile', PROFILE_NAMES),
            ('byIssue', ISSUE_CODES),
        ):
            if req(s, bucket_name, dict, '$.summary'):
                for k in expected_keys:
                    if k not in s[bucket_name]:
                        errs.append(f'$.summary.{bucket_name}: missing key {k!r}')

    if req(report, 'scenarios', list, '$'):
        for i, sc in enumerate(report['scenarios']):
            sp = f'$.scenarios[{i}]'
            req(sc, 'id', str, sp)
            req(sc, 'path', str, sp)
            req(sc, 'entryCount', int, sp)
            req(sc, 'byStatus', dict, sp)
            req(sc, 'byIssue', dict, sp)
            for k in ('readinessRate', 'polishRate'):
                req(sc, k, (int, float), sp)
                if k in sc and not (0 <= sc[k] <= 1):
                    errs.append(f'{sp}.{k}: out of range [0,1]')
            if req(sc, 'entries', list, sp):
                for j, er in enumerate(sc['entries']):
                    ep = f'{sp}.entries[{j}]'
                    req(er, 'index', int, ep)
                    req(er, 'terminator', str, ep)
                    req(er, 'profile', str, ep)
                    if 'profile' in er and er['profile'] not in PROFILE_NAMES:
                        errs.append(f'{ep}.profile: unknown {er["profile"]!r}')
                    req(er, 'status', str, ep)
                    if 'status' in er and er['status'] not in STATUS_VALUES:
                        errs.append(f'{ep}.status: unknown {er["status"]!r}')
                    req(er, 'tileUsage', dict, ep)
                    req(er, 'issues', list, ep)

    return errs
