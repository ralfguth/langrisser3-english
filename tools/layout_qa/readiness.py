"""readiness.py — render the Layout-QA report as a human-readable markdown
dashboard (the Phase 2 Readiness Reporter from the spec).

Reads a JSON produced by `analyze` on the real source scripts and
emits a single markdown file that distinguishes two metrics:

    readiness (playability) = entries WITHOUT errors / total entries
    polish                  = entries POLISHED         / total entries

These are conceptually different questions:
    - readiness: "is this slice of the game shippable?"
    - polish: "is this slice well-presented even though it ships?"

The renderer is dependency-free: it walks the JSON, derives nothing
more than what the schema already provides, and emits markdown.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


# ---------------------------------------------------------------------------
# Issue grouping — readiness criteria vs polish criteria.
#
# Per the spec / user definition:
#   - readiness = no ERROR-class issue       (the entry is jugável)
#   - polish    = no issue at all            (entry is fully POLISHED)
#
# The current bucketer already encodes this in `summary.byStatus`, but
# the reporter calls out the criteria in the markdown so a human can
# see what each metric is gating on.
# ---------------------------------------------------------------------------

READINESS_BLOCKERS = (
    'line_budget_exceeded',
    'label_overflow',
    'balloon_line_overflow',
    'broken_word_wrap',
    'implicit_wrap_without_fffc',
    # A padding space at an internal wrap boundary leaves a ghost gap /
    # leading indent on the rendered line — a real defect (2026-06-19).
    'line_padding_space',
    'unknown_layout_profile',
    # CHOICE-fit errors break the player-facing menu (an option spills into the
    # next slot), so they block readiness like any other hard layout error.
    'choice_overflow',
    'choice_multiline',
    # Spoken-punctuation gate: `:` `;` `—` are forbidden in scen/plot prose.
    'forbidden_punctuation',
)

POLISH_BLOCKERS = (
    'low_line_usage',
    'special_token_overflow_risk',
    'encoding_risk',
)


def _pct(num: int, denom: int) -> float:
    return (num / denom) if denom else 0.0


@dataclass
class FileRow:
    scen_id: str
    total: int
    error: int
    playable: int
    polished: int

    @property
    def readiness(self) -> float:
        return _pct(self.playable + self.polished, self.total)

    @property
    def polish(self) -> float:
        return _pct(self.polished, self.total)


def _file_rows(report: Dict[str, Any]) -> List[FileRow]:
    rows: List[FileRow] = []
    for sc in report.get('scenarios', []):
        bs = sc.get('byStatus', {}) or {}
        rows.append(FileRow(
            scen_id=sc['id'],
            total=int(sc.get('entryCount', 0)),
            error=int(bs.get('ERROR', 0)),
            playable=int(bs.get('PLAYABLE', 0)),
            polished=int(bs.get('POLISHED', 0)),
        ))
    return rows


def _md_table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> List[str]:
    hdrs = list(headers)
    out = ['| ' + ' | '.join(hdrs) + ' |',
           '|' + '|'.join('---' for _ in hdrs) + '|']
    for r in rows:
        out.append('| ' + ' | '.join(str(c) for c in r) + ' |')
    return out


def _fmt_pct(p: float) -> str:
    return f'{p * 100:.1f}%'


def _project_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    """Return projectSummary, deriving from `summary` if missing (back-compat)."""
    return report.get('projectSummary') or {
        'filesAnalyzed': report['summary']['scenarioCount'],
        'entriesAnalyzed': report['summary']['entryCount'],
        'entriesError': report['summary']['byStatus']['ERROR'],
        'entriesPlayable': report['summary']['byStatus']['PLAYABLE'],
        'entriesPolished': report['summary']['byStatus']['POLISHED'],
        'playabilityRate': report['summary']['playabilityRate'],
        'polishRate': report['summary']['polishRate'],
    }


def render_markdown(
    report: Dict[str, Any],
    *,
    top_n_files: int = 15,
    source: str | None = None,
) -> str:
    ps = _project_summary(report)
    summary = report.get('summary', {}) or {}
    by_profile = summary.get('byProfile', {}) or {}
    by_profile_status = summary.get('byProfileStatus', {}) or {}
    by_issue = summary.get('byIssue', {}) or {}
    by_issue_scope = summary.get('byIssueScope', {}) or {}
    line_utilization = summary.get('lineUtilization', {}) or {}
    overrides_applied = summary.get('overridesApplied', []) or []
    generated = report.get('generatedAt', _dt.datetime.now(_dt.timezone.utc).isoformat())
    lang = report.get('lang', '?')

    rows = _file_rows(report)
    total = ps['entriesAnalyzed'] or 1

    lines: List[str] = []
    lines.append('# Layout QA — Readiness Report')
    lines.append('')
    lines.append(f'_Generated: {generated} · lang: {lang}_')
    if source:
        lines.append(f'_Source: `{source}`_')
    lines.append('')
    lines.append('Units: every count is qualified — **entries** (one line of '
                 'a scen file), **balloons** (one `<$FFFD>`-separated bubble '
                 'inside an entry), **lines** (one rendered line within a '
                 'balloon), **occurrences** (issue instances; can exceed '
                 'entries because the simulator emits one per spilled line), '
                 'and **files** (one scen file).')
    lines.append('')

    # ---- Project summary -----------------------------------------------
    lines.append('## Project summary')
    lines.append('')
    lines.append(f'- Files analyzed: **{ps["filesAnalyzed"]} files**')
    lines.append(f'- Entries analyzed: **{ps["entriesAnalyzed"]} entries**')
    lines.append(f'- Readiness (playability, entries): **{_fmt_pct(ps["playabilityRate"])}** '
                 f'({ps["entriesPlayable"] + ps["entriesPolished"]} / {ps["entriesAnalyzed"]})')
    lines.append(f'- Polish (entries): **{_fmt_pct(ps["polishRate"])}** '
                 f'({ps["entriesPolished"]} / {ps["entriesAnalyzed"]})')
    lines.append(f'- Distance to 100% readiness: **{ps["entriesError"]} entries**')
    lines.append(f'- Distance to 100% polish: **{ps["entriesError"] + ps["entriesPlayable"]} entries**')
    lines.append('')

    # ---- Next actions (synthesized priorities) -------------------------
    lines.append('## Next actions')
    lines.append('')
    lines.append('Synthesized from the current aggregates — concrete handles to '
                 'attack first. Rank order matches the order in which fixing '
                 'them shifts the needles most.')
    lines.append('')
    # 1. Top 3 issue codes by raw count (errors first, warnings after).
    err_codes = sorted(
        ((c, by_issue.get(c, 0)) for c in READINESS_BLOCKERS),
        key=lambda kv: -kv[1],
    )
    err_codes = [(c, n) for c, n in err_codes if n > 0]
    if err_codes:
        lines.append('**Top readiness blockers**:')
        for c, n in err_codes[:5]:
            scope = by_issue_scope.get(c, {}).get('filesAffected', 0)
            lines.append(f'- `{c}` × {n} (in {scope} files)')
        lines.append('')
    pol_codes = sorted(
        ((c, by_issue.get(c, 0)) for c in POLISH_BLOCKERS),
        key=lambda kv: -kv[1],
    )
    pol_codes = [(c, n) for c, n in pol_codes if n > 0]
    if pol_codes:
        lines.append('**Top polish blockers**:')
        for c, n in pol_codes[:5]:
            scope = by_issue_scope.get(c, {}).get('filesAffected', 0)
            lines.append(f'- `{c}` × {n} (in {scope} files)')
        lines.append('')
    # 2. Top 3 files by absolute error count (where rewriting yields the
    # biggest single-file win).
    if rows:
        top_err_files = sorted(rows, key=lambda r: -r.error)[:5]
        top_err_files = [r for r in top_err_files if r.error > 0]
        if top_err_files:
            lines.append('**Top files by absolute errors** (biggest single-file '
                         'wins available):')
            for r in top_err_files:
                lines.append(f'- `{r.scen_id}` — {r.error} errors '
                             f'({_fmt_pct(r.readiness)} readiness, '
                             f'{r.total} entries)')
            lines.append('')
    # 3. Profile with the worst readiness — focus area.
    profile_rank = sorted(
        ((p, d) for p, d in by_profile_status.items() if d.get('total', 0) > 0),
        key=lambda kv: kv[1].get('readiness', 1.0),
    )
    if profile_rank:
        worst_p, worst_d = profile_rank[0]
        if worst_d.get('readiness', 1.0) < 1.0:
            lines.append(f'**Profile most in need of work**: `{worst_p}` — '
                         f'readiness {_fmt_pct(worst_d["readiness"])}, '
                         f'{worst_d["ERROR"]} errors across '
                         f'{worst_d["total"]} entries.')
            lines.append('')

    # ---- Readiness vs Polish framing -----------------------------------
    lines.append('## Readiness vs Polish')
    lines.append('')
    lines.append('Two separate questions about the same corpus:')
    lines.append('')
    lines.append('**Readiness** — *is it shippable?* — entries free of '
                 'ERROR-class issues:')
    for code in READINESS_BLOCKERS:
        n = by_issue.get(code, 0)
        scope = by_issue_scope.get(code, {}).get('filesAffected', 0)
        lines.append(f'- `{code}`: {n} occurrences in {scope} files')
    lines.append('')
    lines.append('**Polish** — *is it well-presented?* — entries with zero '
                 'issues (no warnings either):')
    for code in POLISH_BLOCKERS:
        n = by_issue.get(code, 0)
        scope = by_issue_scope.get(code, {}).get('filesAffected', 0)
        lines.append(f'- `{code}`: {n} occurrences in {scope} files')
    lines.append('')

    # ---- Status breakdown ---------------------------------------------
    lines.append('## Status breakdown')
    lines.append('')
    lines.extend(_md_table(
        ['status', 'count', 'share'],
        [
            ['ERROR', ps['entriesError'], _fmt_pct(ps['entriesError'] / total)],
            ['PLAYABLE', ps['entriesPlayable'], _fmt_pct(ps['entriesPlayable'] / total)],
            ['POLISHED', ps['entriesPolished'], _fmt_pct(ps['entriesPolished'] / total)],
        ],
    ))
    lines.append('')

    # ---- By profile — status split + line utilization ------------------
    lines.append('## By profile')
    lines.append('')
    lines.append('Each layout profile carries its own readiness/polish '
                 'curve. The four utilization columns on the right come '
                 'from each entry\'s `tileUsage`: average tile count per '
                 'line, average tile count of the worst line, and the '
                 'corresponding fill ratios against the profile budget.')
    lines.append('')
    prof_rows = []
    for prof in sorted(by_profile_status.keys(),
                       key=lambda p: -by_profile_status[p].get('total', 0)):
        d = by_profile_status[prof]
        n = d.get('total', 0)
        if n == 0:
            continue
        util = line_utilization.get(prof, {}) or {}
        prof_rows.append([
            prof, n,
            _fmt_pct(d.get('readiness', 1.0)),
            _fmt_pct(d.get('polish', 1.0)),
            d.get('ERROR', 0), d.get('PLAYABLE', 0), d.get('POLISHED', 0),
            f'{util.get("avgLine", 0):.1f}',
            _fmt_pct(util.get('avgFillRatio', 0)),
            f'{util.get("avgMaxLine", 0):.1f}',
            _fmt_pct(util.get('avgFillRatioOfMaxLine', 0)),
        ])
    lines.extend(_md_table(
        ['profile', 'entries', 'readiness', 'polish',
         'error', 'playable', 'polished',
         'avgLine', 'avgFill', 'avgMaxLine', 'avgMaxFill'],
        prof_rows,
    ))
    lines.append('')

    # ---- All issues, with each unit of coverage ------------------------
    lines.append('## Issues')
    lines.append('')
    lines.append('Each issue code reported at three granularities:')
    lines.append('')
    lines.append('- **occurrences** — raw emit count (one per spilled '
                 'line for balloon overflows, one per affected line for '
                 'wrap warnings)')
    lines.append('- **entriesAffected** — unique entries with at least '
                 'one occurrence (≤ occurrences)')
    lines.append('- **balloonsAffected** — unique balloons (only meaningful '
                 'for codes whose detail carries a `balloon` field)')
    lines.append('- **filesAffected** — unique scen files')
    lines.append('')
    issue_rows = []
    for code, n in sorted(by_issue.items(), key=lambda kv: -kv[1]):
        sev = 'error' if code in READINESS_BLOCKERS else 'warning'
        sc = by_issue_scope.get(code, {}) or {}
        issue_rows.append([
            code, sev,
            n,
            sc.get('entriesAffected', 0),
            sc.get('balloonsAffected', 0),
            sc.get('filesAffected', 0),
        ])
    lines.extend(_md_table(
        ['code', 'severity', 'occurrences', 'entriesAffected',
         'balloonsAffected', 'filesAffected'],
        issue_rows,
    ))
    lines.append('')

    # ---- Worst files by readiness % -----------------------------------
    if rows:
        # By readiness ascending then by ERROR desc as tie-breaker — files
        # most likely to break the game first.
        worst_ready = sorted(rows, key=lambda r: (r.readiness, -r.error))[:top_n_files]
        lines.append(f'## Worst {len(worst_ready)} files by readiness %')
        lines.append('')
        lines.extend(_md_table(
            ['scen', 'entries', 'readiness (entries)', 'polish (entries)',
             'error (entries)', 'playable (entries)', 'polished (entries)'],
            [[r.scen_id, r.total, _fmt_pct(r.readiness), _fmt_pct(r.polish),
              r.error, r.playable, r.polished] for r in worst_ready],
        ))
        lines.append('')

        # By absolute error count — where the biggest single-file wins are.
        worst_abs = sorted(rows, key=lambda r: -r.error)[:top_n_files]
        worst_abs = [r for r in worst_abs if r.error > 0]
        if worst_abs:
            lines.append(f'## Worst {len(worst_abs)} files by absolute errors')
            lines.append('')
            lines.append('Different ranking from the % view: a 200-entry '
                         'file at 90% readiness has 20 errors to fix, more '
                         'than a 5-entry file at 0%.')
            lines.append('')
            lines.extend(_md_table(
                ['scen', 'entries', 'error (entries)', 'readiness (entries)'],
                [[r.scen_id, r.total, r.error, _fmt_pct(r.readiness)]
                 for r in worst_abs],
            ))
            lines.append('')

        # Files that are 100% playable but have polish work to do.
        shippable = [r for r in rows if r.readiness >= 1.0 and r.polish < 1.0]
        shippable.sort(key=lambda r: r.polish)
        worst_polish = shippable[:top_n_files]
        if worst_polish:
            lines.append(f'## Worst {len(worst_polish)} files by polish '
                         f'(among readiness=100%)')
            lines.append('')
            lines.extend(_md_table(
                ['scen', 'entries', 'polish (entries)',
                 'playable (entries)', 'polished (entries)'],
                [[r.scen_id, r.total, _fmt_pct(r.polish),
                  r.playable, r.polished] for r in worst_polish],
            ))
            lines.append('')

    # ---- Active overrides ----------------------------------------------
    if overrides_applied:
        lines.append('## Active layout overrides')
        lines.append('')
        lines.append('These scenarios were reclassified via '
                     '`config/layout-overrides.json` because their narration '
                     'body does not render in the default DIALOGUE_12X4 '
                     'balloon. If any of these scens regress, re-verify the '
                     'override in-game.')
        lines.append('')
        for scen in overrides_applied:
            lines.append(f'- `{scen}`')
        lines.append('')

    # ---- See also -------------------------------------------------------
    lines.append('## See also')
    lines.append('')
    lines.append('- `reports/layout-qa-rewrite-worklist.csv` — per-balloon '
                 'rewrite worklist ranked by severity '
                 '(generate with `python3 -m tools.layout_qa.cli worklist`).')
    lines.append('- `reports/layout-qa-report.json` — raw JSON consumed by '
                 'this report (per-entry detail, issues, classification '
                 'provenance).')
    lines.append('')

    return '\n'.join(lines)


def write_markdown(report: Dict[str, Any], path: Path, **kwargs) -> int:
    """Write the markdown report. Returns its character count.

    Accepts the same kwargs as `render_markdown` (top_n_files, source).
    """
    text = render_markdown(report, **kwargs)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return len(text)
