"""query.py — agent-friendly read surface over the snapshot history.

Each function returns a small markdown string (< 2k tokens worst-case)
suitable for an LLM agent to consume in one tool call. Callers must
not have to parse the full layout-QA JSON to answer common questions.

All queries read trimmed snapshots from `reports/history/`. Trim
already drops per-entry detail, so they're cheap. `catalog` is
static and needs no snapshot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from layout_qa.metrics import ISSUE_CODES, PROFILE_NAMES
from layout_qa.readiness import READINESS_BLOCKERS, POLISH_BLOCKERS
from layout_qa.snapshot import (
    list_snapshots, load_snapshot,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _latest_snapshot(history_dir: Path) -> Dict[str, Any]:
    snaps = list_snapshots(history_dir)
    if not snaps:
        raise FileNotFoundError(
            f'no snapshot in {history_dir} — capture one first with '
            f'`snapshot --label <name>`'
        )
    return load_snapshot(snaps[-1])


def _fmt_pct(rate) -> str:
    if rate is None:
        return '—'
    return f'{rate * 100:.1f}%'


def _signed(n) -> str:
    return f'+{n}' if isinstance(n, int) and n >= 0 else str(n)


def _project_summary(snap: Dict[str, Any]) -> Dict[str, Any]:
    return snap.get('projectSummary') or {}


def _snap_meta_line(snap: Dict[str, Any]) -> str:
    m = snap.get('snapshot') or {}
    if not m:
        return ''
    date = m.get('date', '?')
    label = m.get('label', '?')
    commit = m.get('gitCommit', '')
    note = m.get('note', '')
    line = f'_Snapshot: **{date}** `{label}`'
    if commit:
        line += f' (commit `{commit}`)'
    if note:
        line += f' — {note}'
    line += '_'
    return line


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

def state(history_dir: Path) -> str:
    snap = _latest_snapshot(history_dir)
    ps = _project_summary(snap)
    lines: List[str] = []
    lines.append('# State of the patch')
    lines.append('')
    meta = _snap_meta_line(snap)
    if meta:
        lines.append(meta)
        lines.append('')
    lines.append(f'- Files analyzed: **{ps.get("filesAnalyzed", 0)} files**')
    lines.append(f'- Entries analyzed: **{ps.get("entriesAnalyzed", 0)} entries**')
    lines.append(f'- Readiness: **{_fmt_pct(ps.get("playabilityRate"))}** '
                 f'({ps.get("entriesPlayable", 0) + ps.get("entriesPolished", 0)} '
                 f'/ {ps.get("entriesAnalyzed", 0)} entries)')
    lines.append(f'- Polish: **{_fmt_pct(ps.get("polishRate"))}** '
                 f'({ps.get("entriesPolished", 0)} '
                 f'/ {ps.get("entriesAnalyzed", 0)} entries)')
    lines.append(f'- Entries with errors: **{ps.get("entriesError", 0)} entries**')
    lines.append(f'- Entries playable (warnings only): '
                 f'**{ps.get("entriesPlayable", 0)} entries**')
    lines.append(f'- Entries polished (no issues): '
                 f'**{ps.get("entriesPolished", 0)} entries**')
    lines.append('')

    summary = snap.get('summary') or {}
    by_issue = summary.get('byIssue') or {}
    issue_rows = [(c, n) for c, n in by_issue.items() if n > 0]
    if issue_rows:
        issue_rows.sort(key=lambda kv: -kv[1])
        lines.append('## Top issue occurrences')
        lines.append('')
        for code, n in issue_rows[:5]:
            sev = 'error' if code in READINESS_BLOCKERS else 'warning'
            lines.append(f'- `{code}` ({sev}): {n}')
        lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# top-files
# ---------------------------------------------------------------------------

_TOP_BY = {
    'errors': lambda sc: (-sc['byStatus'].get('ERROR', 0), sc['id']),
    'readiness': lambda sc: (sc.get('readinessRate', 1.0), sc['id']),
    'polish': lambda sc: (sc.get('polishRate', 1.0), sc['id']),
    'overflow': lambda sc: (-sc.get('byIssue', {}).get('balloon_line_overflow', 0),
                            sc['id']),
}


def top_files(history_dir: Path, *, by: str, n: int = 10) -> str:
    if by not in _TOP_BY:
        raise ValueError(
            f'unknown --by {by!r}; choose from {sorted(_TOP_BY)}'
        )
    snap = _latest_snapshot(history_dir)
    scenarios = snap.get('scenarios', [])
    # Filter out trivially-clean files when ranking by errors / overflow.
    if by in ('errors', 'overflow'):
        key = 'ERROR' if by == 'errors' else 'balloon_line_overflow'
        if by == 'errors':
            scenarios = [s for s in scenarios
                         if s.get('byStatus', {}).get('ERROR', 0) > 0]
        else:
            scenarios = [s for s in scenarios
                         if s.get('byIssue', {}).get(key, 0) > 0]
    scenarios = sorted(scenarios, key=_TOP_BY[by])[:n]
    lines: List[str] = []
    lines.append(f'# Top {len(scenarios)} files by `{by}`')
    lines.append('')
    meta = _snap_meta_line(snap)
    if meta:
        lines.append(meta)
        lines.append('')
    if not scenarios:
        lines.append('_No files matched._')
        return '\n'.join(lines)
    lines.append('| scen | entries | error | readiness | polish '
                 '| balloon_line_overflow |')
    lines.append('|---|---|---|---|---|---|')
    for sc in scenarios:
        bs = sc.get('byStatus', {}) or {}
        bi = sc.get('byIssue', {}) or {}
        lines.append(
            f'| `{sc["id"]}` | {sc.get("entryCount", 0)} '
            f'| {bs.get("ERROR", 0)} '
            f'| {_fmt_pct(sc.get("readinessRate"))} '
            f'| {_fmt_pct(sc.get("polishRate"))} '
            f'| {bi.get("balloon_line_overflow", 0)} |'
        )
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# file
# ---------------------------------------------------------------------------

def file(history_dir: Path, scen_id: str) -> str:
    snap = _latest_snapshot(history_dir)
    found = next(
        (sc for sc in snap.get('scenarios', []) if sc['id'] == scen_id),
        None,
    )
    if found is None:
        raise FileNotFoundError(f'scenario {scen_id!r} not in snapshot')
    bs = found.get('byStatus', {}) or {}
    bi = found.get('byIssue', {}) or {}
    lines: List[str] = []
    lines.append(f'# `{scen_id}`')
    lines.append('')
    meta = _snap_meta_line(snap)
    if meta:
        lines.append(meta)
        lines.append('')
    lines.append(f'- Entries: **{found.get("entryCount", 0)}**')
    lines.append(f'- Readiness: **{_fmt_pct(found.get("readinessRate"))}**')
    lines.append(f'- Polish: **{_fmt_pct(found.get("polishRate"))}**')
    lines.append('')
    lines.append('## Status breakdown')
    lines.append('')
    lines.append('| status | entries |')
    lines.append('|---|---|')
    for status in ('ERROR', 'PLAYABLE', 'POLISHED'):
        lines.append(f'| {status} | {bs.get(status, 0)} |')
    lines.append('')
    issue_rows = [(c, n) for c, n in bi.items() if n > 0]
    if issue_rows:
        issue_rows.sort(key=lambda kv: -kv[1])
        lines.append('## Issues')
        lines.append('')
        lines.append('| code | severity | occurrences |')
        lines.append('|---|---|---|')
        for code, n in issue_rows:
            sev = 'error' if code in READINESS_BLOCKERS else 'warning'
            lines.append(f'| `{code}` | {sev} | {n} |')
        lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# issue
# ---------------------------------------------------------------------------

def issue(history_dir: Path, code: str) -> str:
    if code not in ISSUE_CODES:
        raise ValueError(f'unknown issue code {code!r}; '
                         f'use `query catalog` to list')
    snap = _latest_snapshot(history_dir)
    summary = snap.get('summary') or {}
    scope = (summary.get('byIssueScope') or {}).get(code) or {}
    sev = 'error' if code in READINESS_BLOCKERS else 'warning'
    lines: List[str] = []
    lines.append(f'# `{code}`')
    lines.append('')
    meta = _snap_meta_line(snap)
    if meta:
        lines.append(meta)
        lines.append('')
    lines.append(f'- Severity: **{sev}**')
    lines.append(f'- Occurrences: **{scope.get("occurrences", 0)}**')
    lines.append(f'- Entries affected: **{scope.get("entriesAffected", 0)}**')
    lines.append(f'- Balloons affected: **{scope.get("balloonsAffected", 0)}**')
    lines.append(f'- Files affected: **{scope.get("filesAffected", 0)}**')
    lines.append('')
    # Top files by this code's occurrences.
    file_rows = [
        (sc['id'], (sc.get('byIssue') or {}).get(code, 0))
        for sc in snap.get('scenarios', [])
    ]
    file_rows = [(s, n) for s, n in file_rows if n > 0]
    file_rows.sort(key=lambda kv: -kv[1])
    if file_rows:
        lines.append('## Top files')
        lines.append('')
        lines.append('| scen | occurrences |')
        lines.append('|---|---|')
        for s, n in file_rows[:10]:
            lines.append(f'| `{s}` | {n} |')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# trend
# ---------------------------------------------------------------------------

_TREND_METRICS = {
    'playabilityRate', 'polishRate',
    'entriesError', 'entriesPlayable', 'entriesPolished',
    'entriesAnalyzed', 'filesAnalyzed',
}


def trend(history_dir: Path, metric: str, since: Optional[str] = None) -> str:
    if metric not in _TREND_METRICS:
        raise ValueError(f'unknown metric {metric!r}; '
                         f'available: {sorted(_TREND_METRICS)}')
    snaps_paths = list_snapshots(history_dir)
    if not snaps_paths:
        raise FileNotFoundError(f'no snapshots in {history_dir}')
    if since is not None:
        snaps_paths = [p for p in snaps_paths
                       if (load_snapshot(p).get('snapshot') or {})
                           .get('date', '') >= since]
        if not snaps_paths:
            raise FileNotFoundError(
                f'no snapshots in {history_dir} dated >= {since}'
            )
    is_pct = metric in ('playabilityRate', 'polishRate')
    lines: List[str] = []
    lines.append(f'# Trend: `{metric}`')
    lines.append('')
    if since:
        lines.append(f'_Since {since}_')
        lines.append('')
    lines.append('| date | label | value |')
    lines.append('|---|---|---|')
    prev = None
    for p in snaps_paths:
        snap = load_snapshot(p)
        m = snap.get('snapshot') or {}
        ps = _project_summary(snap)
        v = ps.get(metric)
        cell = _fmt_pct(v) if is_pct else str(v)
        if prev is not None and isinstance(v, (int, float)) and isinstance(prev, (int, float)):
            delta = v - prev
            if is_pct:
                cell += f' ({"+" if delta >= 0 else ""}{delta * 100:.1f}pp)'
            else:
                cell += f' ({"+" if delta >= 0 else ""}{delta})'
        lines.append(f'| {m.get("date", "?")} | `{m.get("label", "?")}` | {cell} |')
        prev = v
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# catalog (static reference — needs no snapshot)
# ---------------------------------------------------------------------------

_ISSUE_DESCRIPTIONS = {
    'line_budget_exceeded': 'explicit FFFC-bounded segment > per-line tile budget (reserved; not currently emitted because multi-line profiles wrap before this triggers)',
    'label_overflow': 'single-line LABEL_*X1 content > width (the label cannot wrap, so it overflows the visible region)',
    'balloon_line_overflow': 'more rendered lines than the balloon allows for the profile',
    'broken_word_wrap': 'a word is split or two tokens are glued: engine wrap would split a word mid-word; a final line is punctuation-only (orphan); an explicit <$FFFC> was dropped inside a word; or a space was lost after punctuation. detail.reason distinguishes (orphan_punctuation_on_final_line / fffc_splits_word / fffc_splits_contraction / missing_space_after_punctuation)',
    'unknown_layout_profile': 'classifier could not assign a profile to the entry',
    'choice_overflow': 'ERROR: a player-facing menu option (annotated class=CHOICE in entry-annotations.json) is wider than its budget (resolved balloon width − 1 selection cursor) on its single line; it spills into the next option slot',
    'choice_multiline': 'ERROR: a player-facing menu option wraps to >1 line (has a <$FFFC>); a choice is single-line, so the overflow lands in the next option slot',
    'implicit_wrap_without_fffc': 'ERROR: line wraps without an explicit <$FFFC>. Convention is an explicit cut on every visual break — engine auto-wrap drags a leading space onto the next line (ghost indent), so it is never clean',
    'forbidden_punctuation': 'ERROR: a colon, semicolon, or em-dash in scen/plot prose. These are written-prose typography that breaks a localized, spoken-feeling read (the em-dash is not even in the tile map). Recast: colon -> sentence/comma; semicolon -> two sentences; em-dash -> ellipsis/comma/new sentence. Allowed: . , ... ? ! and the regular hyphen in compounds. detail.reason = colon / semicolon / em_dash',
    'low_line_usage': 'non-final line uses < 85% of the per-line tile budget (poor utilization)',
    'fluidity_headroom': 'INFO (does NOT block polish): a short non-final line that ENDS A SENTENCE (.!?…) — leftover width is room for fluidity (expand this sentence, or start the next one on this line), not an under-fill defect',
    'special_token_overflow_risk': 'F600/0000 protagonist token would push the line past budget',
    'encoding_risk': 'text contains a character not in the tile map (would be silently dropped)',
    'line_padding_space': 'wrap did not consume the space: non-last line ends with " " or non-first line starts with " " (DIALOGUE only; layout-trick profiles exempt)',
}

# Codes emitted at severity 'info' — advisory only, never block POLISHED.
_INFO_CODES = frozenset({'fluidity_headroom'})

_PROFILE_DESCRIPTIONS = {
    'LABEL_CHARACTER_12X1': 'nameplate, single line, strict 12 tiles',
    'LABEL_LOCATION_16X1': 'location title, single line, max 16 tiles (no minimum)',
    'OBJECTIVE_16X5': 'mission objective bullets, 16 × 5 lines',
    'NARRATION_16X5': 'scenario intros + scen124 epilogues (override), 16 × 5 lines',
    'DIALOGUE_12X4': 'in-balloon dialogue, 12 × 4 lines',
    'UNKNOWN': 'profile could not be classified — always ERROR',
}


def catalog() -> str:
    lines: List[str] = []
    lines.append('# Layout QA — catalog')
    lines.append('')
    lines.append('## Issue codes')
    lines.append('')
    lines.append('| code | severity | meaning |')
    lines.append('|---|---|---|')
    for code in ISSUE_CODES:
        if code in READINESS_BLOCKERS:
            sev = 'error'
        elif code in _INFO_CODES:
            sev = 'info'
        else:
            sev = 'warning'
        desc = _ISSUE_DESCRIPTIONS.get(code, '')
        lines.append(f'| `{code}` | {sev} | {desc} |')
    lines.append('')
    lines.append('## Layout profiles')
    lines.append('')
    lines.append('| profile | meaning |')
    lines.append('|---|---|')
    for prof in PROFILE_NAMES:
        desc = _PROFILE_DESCRIPTIONS.get(prof, '')
        lines.append(f'| `{prof}` | {desc} |')
    lines.append('')
    lines.append('## Status bucket')
    lines.append('')
    lines.append('```')
    lines.append('ERROR    → any error issue (or UNKNOWN profile)')
    lines.append('PLAYABLE → only warnings (low_line_usage, special_token, etc.)')
    lines.append('POLISHED → no errors, no warnings (info advisories like '
                 'fluidity_headroom are allowed)')
    lines.append('```')
    lines.append('')
    lines.append('Invariant: POLISHED ⊆ PLAYABLE ⊆ all_entries.')
    return '\n'.join(lines)
