"""snapshot.py — committable trims of the full layout-QA report.

The full JSON is ~10-20 MB per pipeline run, dominated by per-entry
detail (`scenarios[*].entries[*]`). A snapshot drops that detail and
keeps only the aggregates needed for trend tracking and decision
dashboards. Result: ~100-200 KB per snapshot, fine for git history.

Snapshots live in a sibling git repo, symlinked at
`langrisser3-english/reports`. See `reports/README.md` for the schema
and the agent-facing `query` surface.
"""

from __future__ import annotations

import copy
import json
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# Keys to copy verbatim from the full report into the trimmed snapshot.
_TOP_LEVEL_KEPT = (
    'schemaVersion', 'generatedAt', 'lang', 'tool',
    'projectSummary', 'summary',
)

# Keys to keep per scenario. `entries` is the only intentional drop —
# everything else is a small aggregate.
_SCENARIO_KEPT = (
    'id', 'path', 'entryCount',
    'byStatus', 'byIssue',
    'readinessRate', 'polishRate',
)


def trim(report: Dict[str, Any],
         snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a small, committable copy of `report`.

    Drops `scenarios[*].entries`. Optionally injects a `snapshot`
    frontmatter block (date, label, gitCommit, etc.). Pure function —
    `report` is not mutated.
    """
    out: Dict[str, Any] = {}
    for k in _TOP_LEVEL_KEPT:
        if k in report:
            out[k] = copy.deepcopy(report[k])
    if snapshot is not None:
        out['snapshot'] = copy.deepcopy(snapshot)
    scenarios_out: List[Dict[str, Any]] = []
    for sc in report.get('scenarios', []):
        sc_out: Dict[str, Any] = {}
        for k in _SCENARIO_KEPT:
            if k in sc:
                sc_out[k] = copy.deepcopy(sc[k])
        scenarios_out.append(sc_out)
    out['scenarios'] = scenarios_out
    return out


# ---------------------------------------------------------------------------
# git context — gitCommit + gitBranch for snapshot frontmatter
# ---------------------------------------------------------------------------

def git_context(cwd: Optional[Path] = None) -> Dict[str, str]:
    """Best-effort: return current git short-commit + branch.

    If the cwd isn't a git repo, or git isn't installed, returns
    empty strings rather than raising. This keeps snapshot creation
    working on clones that didn't init git.
    """
    def _capture(args: List[str]) -> str:
        try:
            r = subprocess.run(
                args, capture_output=True, text=True, cwd=cwd, check=False,
            )
            return r.stdout.strip() if r.returncode == 0 else ''
        except (FileNotFoundError, OSError):
            return ''
    return {
        'gitCommit': _capture(['git', 'rev-parse', '--short', 'HEAD']),
        'gitBranch': _capture(['git', 'rev-parse', '--abbrev-ref', 'HEAD']),
    }


# ---------------------------------------------------------------------------
# Snapshot orchestration: produce + persist
# ---------------------------------------------------------------------------

def _slug(label: str) -> str:
    """Filesystem-safe label segment. Lowercase, hyphenated, alphanum + dash."""
    safe = ''.join(c if (c.isalnum() or c in '-_') else '-'
                   for c in label.strip().lower())
    # Collapse runs of dashes.
    while '--' in safe:
        safe = safe.replace('--', '-')
    return safe.strip('-') or 'unnamed'


def snapshot_path(
    history_dir: Path,
    *,
    label: str,
    when: Optional[date] = None,
    suffix: str = '.json',
) -> Path:
    """Compose the canonical snapshot path under `history_dir`."""
    when = when or date.today()
    return history_dir / f'snapshot-{when.isoformat()}_{_slug(label)}{suffix}'


def write_snapshot(
    report: Dict[str, Any],
    history_dir: Path,
    *,
    label: str,
    note: str = '',
    when: Optional[date] = None,
    git_cwd: Optional[Path] = None,
) -> Path:
    """Trim + persist a snapshot JSON under `history_dir`. Returns the path."""
    when = when or date.today()
    gctx = git_context(cwd=git_cwd)
    snap_meta = {
        'date': when.isoformat(),
        'label': label,
        'gitCommit': gctx['gitCommit'],
        'gitBranch': gctx['gitBranch'],
        'note': note,
    }
    trimmed = trim(report, snapshot=snap_meta)
    history_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(history_dir, label=label, when=when, suffix='.json')
    path.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2),
                    encoding='utf-8')
    return path


def list_snapshots(history_dir: Path) -> List[Path]:
    """Return all snapshot-*.json files in `history_dir`, sorted by name
    (which is chronological because the date is in the filename)."""
    if not history_dir.exists():
        return []
    return sorted(history_dir.glob('snapshot-*.json'))


def load_snapshot(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def diff_snapshots(
    a: Dict[str, Any], b: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute a high-level diff between two snapshot JSONs.

    Returns a dict with:
        a, b: snapshot frontmatter (date+label) for each side
        readiness, polish: per-metric {a, b, delta} (delta in
            absolute points, e.g. +0.5 means +50pp)
        byStatus: {status: {a, b, delta}}
        byIssue: {code: {a, b, delta}}  — only codes that changed
        files: {scen_id: {readinessDelta, polishDelta}}  — top 10 movers
    """
    def _meta(s):
        m = s.get('snapshot') or {}
        return {
            'date': m.get('date', '?'),
            'label': m.get('label', '?'),
            'gitCommit': m.get('gitCommit', ''),
        }

    def _ps(s):
        return s.get('projectSummary') or {}

    ps_a, ps_b = _ps(a), _ps(b)

    def _delta(key):
        va = ps_a.get(key)
        vb = ps_b.get(key)
        if va is None or vb is None:
            return None
        return {'a': va, 'b': vb, 'delta': round(vb - va, 4)}

    # By-status counts (entries).
    bsa = (a.get('summary') or {}).get('byStatus') or {}
    bsb = (b.get('summary') or {}).get('byStatus') or {}
    by_status: Dict[str, Dict[str, int]] = {}
    for status in sorted(set(bsa) | set(bsb)):
        by_status[status] = {
            'a': bsa.get(status, 0),
            'b': bsb.get(status, 0),
            'delta': bsb.get(status, 0) - bsa.get(status, 0),
        }

    # By-issue counts — only codes whose count changed.
    bia = (a.get('summary') or {}).get('byIssue') or {}
    bib = (b.get('summary') or {}).get('byIssue') or {}
    by_issue: Dict[str, Dict[str, int]] = {}
    for code in sorted(set(bia) | set(bib)):
        delta = bib.get(code, 0) - bia.get(code, 0)
        if delta != 0:
            by_issue[code] = {
                'a': bia.get(code, 0),
                'b': bib.get(code, 0),
                'delta': delta,
            }

    # Top file movers (|polishDelta| + |readinessDelta|).
    files_a = {sc['id']: sc for sc in a.get('scenarios', [])}
    files_b = {sc['id']: sc for sc in b.get('scenarios', [])}
    file_movers: List[Dict[str, Any]] = []
    for scen_id in sorted(set(files_a) | set(files_b)):
        ra = files_a.get(scen_id, {}).get('readinessRate', 1.0)
        rb = files_b.get(scen_id, {}).get('readinessRate', 1.0)
        pa = files_a.get(scen_id, {}).get('polishRate', 1.0)
        pb = files_b.get(scen_id, {}).get('polishRate', 1.0)
        rd = round(rb - ra, 4)
        pd = round(pb - pa, 4)
        if rd != 0 or pd != 0:
            file_movers.append({
                'scen': scen_id,
                'readinessDelta': rd,
                'polishDelta': pd,
            })
    file_movers.sort(
        key=lambda f: -(abs(f['readinessDelta']) + abs(f['polishDelta']))
    )

    return {
        'a': _meta(a),
        'b': _meta(b),
        'readiness': _delta('playabilityRate'),
        'polish': _delta('polishRate'),
        'errors': _delta('entriesError'),
        'playable': _delta('entriesPlayable'),
        'polished': _delta('entriesPolished'),
        'byStatus': by_status,
        'byIssue': by_issue,
        'files': file_movers[:10],
    }


def format_diff_markdown(diff: Dict[str, Any]) -> str:
    """Render `diff_snapshots()` result as agent-friendly markdown."""
    a = diff['a']
    b = diff['b']
    lines: List[str] = []
    lines.append(f'# Snapshot diff')
    lines.append('')
    lines.append(f'- **A**: {a["date"]} `{a["label"]}` (commit `{a["gitCommit"]}`)')
    lines.append(f'- **B**: {b["date"]} `{b["label"]}` (commit `{b["gitCommit"]}`)')
    lines.append('')

    def _row_pct(label: str, payload):
        if not payload:
            return f'- {label}: missing in one side'
        return (f'- **{label}**: {payload["a"] * 100:.1f}% → '
                f'{payload["b"] * 100:.1f}% '
                f'({_signed(payload["delta"] * 100, "pp")})')

    def _row_count(label: str, payload):
        if not payload:
            return f'- {label}: missing in one side'
        return (f'- **{label}**: {payload["a"]} → {payload["b"]} '
                f'({_signed(payload["delta"])})')

    def _signed(n, unit=''):
        sign = '+' if n >= 0 else ''
        return f'{sign}{n:.1f}{unit}' if isinstance(n, float) else f'{sign}{n}{unit}'

    lines.append('## Headlines')
    lines.append(_row_pct('readiness', diff.get('readiness')))
    lines.append(_row_pct('polish', diff.get('polish')))
    lines.append(_row_count('entries ERROR', diff.get('errors')))
    lines.append(_row_count('entries PLAYABLE', diff.get('playable')))
    lines.append(_row_count('entries POLISHED', diff.get('polished')))
    lines.append('')

    if diff.get('byIssue'):
        lines.append('## Issues that changed')
        lines.append('')
        lines.append('| code | A | B | Δ |')
        lines.append('|---|---|---|---|')
        for code, p in sorted(diff['byIssue'].items(),
                              key=lambda kv: -abs(kv[1]['delta'])):
            lines.append(f'| `{code}` | {p["a"]} | {p["b"]} | '
                         f'{_signed(p["delta"])} |')
        lines.append('')

    if diff.get('files'):
        lines.append('## Top 10 file movers')
        lines.append('')
        lines.append('| scen | Δ readiness | Δ polish |')
        lines.append('|---|---|---|')
        for f in diff['files']:
            lines.append(
                f'| `{f["scen"]}` | '
                f'{_signed(f["readinessDelta"] * 100, "pp")} | '
                f'{_signed(f["polishDelta"] * 100, "pp")} |'
            )
        lines.append('')

    return '\n'.join(lines)


def resolve_snapshot(
    history_dir: Path,
    identifier: str,
) -> Path:
    """Resolve a user-supplied identifier to a snapshot path.

    Accepts:
      - full filename: `snapshot-2026-05-27_post-override.json`
      - basename:      `snapshot-2026-05-27_post-override`
      - label only:    `post-override` (latest snapshot with that label)
      - date only:     `2026-05-27` (latest snapshot from that date)
    """
    if not history_dir.exists():
        raise FileNotFoundError(f'history dir missing: {history_dir}')
    snaps = list_snapshots(history_dir)
    if not snaps:
        raise FileNotFoundError(f'no snapshots in {history_dir}')
    # Exact filename
    direct = history_dir / identifier
    if not identifier.endswith('.json'):
        direct = history_dir / f'{identifier}.json'
    if direct.exists():
        return direct
    # By label (latest)
    label = _slug(identifier)
    matching = [p for p in snaps if p.stem.endswith(f'_{label}')]
    if matching:
        return matching[-1]
    # By date (latest)
    date_matches = [p for p in snaps if f'snapshot-{identifier}_' in p.name]
    if date_matches:
        return date_matches[-1]
    raise FileNotFoundError(
        f'no snapshot matches {identifier!r} in {history_dir}'
    )
