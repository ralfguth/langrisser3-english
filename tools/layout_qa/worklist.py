"""worklist.py — derive a rewrite worklist from a layout-QA report.

Entries that emit `balloon_line_overflow` errors are the ones that
cannot fit no matter how `<$FFFC>` breaks are placed — they need to be
**rewritten** (shortened), not re-wrapped. This module turns those
issues into an ordered worklist (CSV + markdown) so the translator
knows which balloons to attack first.

One row per overflowing balloon: when the simulator emits multiple
`balloon_line_overflow` issues against the same (scen, entry, balloon)
— it does that incrementally as each new line spills past the cap —
the rows are collapsed and only the worst (highest `actualLines`) is
kept. An entry with two distinct overflowing balloons still produces
two rows. Rows are ranked by:

    1. linesOver  = actualLines - maxLines      (descending)
    2. linesUsed  = total emitted lines (proxy for content size, desc)
    3. scen, entry, balloon                     (ascending, stable)

The text snippet is the visible-text portion of the entry (control
codes stripped), truncated to keep the table readable.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from layout_qa.parser import parse_scenario  # noqa: E402
from layout_qa.classifier import visible_text  # noqa: E402


SNIPPET_MAX = 80


@dataclass
class WorklistRow:
    scen: str
    entry: int
    profile: str
    balloon: int
    actual_lines: int
    max_lines: int
    lines_over: int
    lines_used: int
    max_line_tiles: int
    line_budget: int
    snippet: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            'scen': self.scen,
            'entry': self.entry,
            'profile': self.profile,
            'balloon': self.balloon,
            'actualLines': self.actual_lines,
            'maxLines': self.max_lines,
            'linesOver': self.lines_over,
            'linesUsed': self.lines_used,
            'maxLineTiles': self.max_line_tiles,
            'lineBudget': self.line_budget,
            'snippet': self.snippet,
        }


def _normalize_snippet(text: str, max_len: int = SNIPPET_MAX) -> str:
    """Collapse whitespace and truncate for table-row legibility."""
    s = ' '.join(text.split())
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + '…'
    return s


def _load_snippets(scripts_dir: Path) -> Dict[Tuple[str, int], str]:
    """Pre-parse every scen file once and cache snippet by (scen_id, index)."""
    out: Dict[Tuple[str, int], str] = {}
    for path in sorted(scripts_dir.glob('scen*E.txt')):
        for entry in parse_scenario(path):
            out[(entry.scen_id, entry.index)] = _normalize_snippet(visible_text(entry))
    return out


def build_worklist(
    report: Dict[str, Any],
    scripts_dir: Path,
) -> List[WorklistRow]:
    """Walk a layout-QA report and emit one row per balloon_line_overflow."""
    snippets = _load_snippets(scripts_dir)
    # Collapse duplicate issues per (scen, entry, balloon) — keep the
    # worst (highest actualLines). The simulator emits an issue for
    # each line that spills past the cap, so a balloon that ends up
    # 4 lines over the budget yields 4 issues; the worklist treats
    # them as a single rewrite target.
    worst: Dict[Tuple[str, int, int], WorklistRow] = {}

    for scen in report.get('scenarios', []):
        scen_id = scen['id']
        for entry in scen.get('entries', []):
            usage = entry.get('tileUsage', {}) or {}
            budget = usage.get('budget') or [0, 0]
            line_budget = int(budget[0]) if budget else 0
            lines_used = int(usage.get('linesUsed', 0))
            max_line = int(usage.get('maxLine', 0))
            entry_idx = int(entry['index'])
            for iss in entry.get('issues', []):
                if iss.get('code') != 'balloon_line_overflow':
                    continue
                detail = iss.get('detail', {}) or {}
                actual = int(detail.get('actualLines', 0))
                max_l = int(detail.get('maxLines', 0))
                balloon = int(detail.get('balloon', 0))
                row = WorklistRow(
                    scen=scen_id,
                    entry=entry_idx,
                    profile=entry.get('profile', '?'),
                    balloon=balloon,
                    actual_lines=actual,
                    max_lines=max_l,
                    lines_over=max(0, actual - max_l),
                    lines_used=lines_used,
                    max_line_tiles=max_line,
                    line_budget=line_budget,
                    snippet=snippets.get((scen_id, entry_idx), ''),
                )
                key = (scen_id, entry_idx, balloon)
                prev = worst.get(key)
                if prev is None or row.actual_lines > prev.actual_lines:
                    worst[key] = row

    rows: List[WorklistRow] = list(worst.values())

    rows.sort(key=lambda r: (
        -r.lines_over,
        -r.lines_used,
        r.scen,
        r.entry,
        r.balloon,
    ))
    return rows


CSV_FIELDS = [
    'scen', 'entry', 'profile', 'balloon',
    'actualLines', 'maxLines', 'linesOver',
    'linesUsed', 'maxLineTiles', 'lineBudget',
    'snippet',
]


def write_csv(rows: Iterable[WorklistRow], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r.as_dict())
            n += 1
    return n


def _md_escape(s: str) -> str:
    return s.replace('|', '\\|').replace('\n', ' ')


def write_markdown(
    rows: List[WorklistRow],
    path: Path,
    top_n: Optional[int] = None,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    shown = rows if top_n is None else rows[:top_n]
    total = len(rows)
    lines: List[str] = []
    lines.append('# Layout QA — Rewrite Worklist')
    lines.append('')
    lines.append(f'Total `balloon_line_overflow` rows after optimal wrap: **{total}**.')
    if top_n is not None and total > top_n:
        lines.append('')
        lines.append(f'Showing top **{top_n}** by severity.')
    lines.append('')
    lines.append('Ranking: `linesOver` desc, then `linesUsed` desc, '
                 'then `scen` / `entry` / `balloon` asc.')
    lines.append('')
    lines.append('| # | scen | entry | balloon | profile | actual/max | over | tiles/budget | snippet |')
    lines.append('|---|------|-------|---------|---------|------------|------|--------------|---------|')
    for i, r in enumerate(shown, start=1):
        lines.append(
            f'| {i} | {r.scen} | {r.entry} | {r.balloon} | {r.profile} '
            f'| {r.actual_lines}/{r.max_lines} | +{r.lines_over} '
            f'| {r.max_line_tiles}/{r.line_budget} '
            f'| {_md_escape(r.snippet)} |'
        )
    lines.append('')
    path.write_text('\n'.join(lines), encoding='utf-8')
    return len(shown)


def load_report(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))
