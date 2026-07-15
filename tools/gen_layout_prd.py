#!/usr/bin/env python3
"""Generate scripts/ralph/prd.json from reports/layout-qa-report.json.

One user story per scen that is NOT yet passing the gate:
    passes  ↔  byStatus.ERROR == 0  AND  polishRate >= 0.7
                  AND no parity tests broken

Priority is ranked so the worst scens (most ERROR entries, lowest
polish) come first.

Re-run this whenever:
  - The layout-qa report changes (new analyze pass).
  - You want Ralph to re-evaluate which scens still need work.

Stories that ALREADY meet the gate get `passes: true` so Ralph
skips them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJ = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = PROJ / 'reports' / 'layout-qa-report.json'
DEFAULT_PRD = PROJ / 'scripts' / 'ralph' / 'prd.json'
DEFAULT_EXCLUDED = PROJ / 'config' / 'layout-fitting-excluded.json'

# Quality gate (matches CLAUDE.md template):
ERROR_THRESHOLD = 0
POLISH_THRESHOLD = 0.70
ENTRIES_PER_ITERATION = 8

BRANCH_NAME = 'layout-fitting-sweep'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report', type=Path, default=DEFAULT_REPORT,
                    help=f'Layout QA report JSON. Default: {DEFAULT_REPORT.relative_to(PROJ)}')
    ap.add_argument('--output', type=Path, default=DEFAULT_PRD,
                    help=f'Output prd.json. Default: {DEFAULT_PRD.relative_to(PROJ)}')
    ap.add_argument('--excluded', type=Path, default=DEFAULT_EXCLUDED,
                    help=f'JSON listing scens to skip. Default: {DEFAULT_EXCLUDED.relative_to(PROJ)}')
    args = ap.parse_args()

    report = json.loads(args.report.read_text(encoding='utf-8'))
    scens = report['scenarios']

    excluded_by_scen = {}
    if args.excluded.exists():
        excl_doc = json.loads(args.excluded.read_text(encoding='utf-8'))
        for item in excl_doc.get('excluded', []):
            excluded_by_scen[item['scen']] = item.get('reason', '')

    stories = []
    for i, scen in enumerate(scens):
        if scen['id'] in excluded_by_scen:
            continue
        err = scen['byStatus']['ERROR']
        polish = scen.get('polishRate', 0.0)
        passes = (err <= ERROR_THRESHOLD) and (polish >= POLISH_THRESHOLD)

        # Priority: lower number = higher priority.
        # Worst-ERROR-first weighted heavily; polish gap as tiebreaker.
        if passes:
            priority_score = 0  # already done — order doesn't matter
        else:
            priority_score = -(err * 1000 + int((1.0 - polish) * 100))

        stories.append({
            'id': f'US-{scen["id"]}',
            'scen': scen['id'],
            'path': scen['path'],
            'title': f'Fit {scen["id"]} to playable + polished',
            'description': (
                f'Apply the langrisser3-layout-fitting skill to up to '
                f'{ENTRIES_PER_ITERATION} broken entries in {scen["id"]}. '
                f'Read paired JP. Preserve control-code and entry-count parity. '
                f'Re-analyze after the edit pass.'
            ),
            'acceptanceCriteria': [
                f'`byStatus.ERROR == {ERROR_THRESHOLD}` for {scen["id"]} in '
                f'reports/layout-qa-report.json after re-analyze.',
                f'`polishRate >= {POLISH_THRESHOLD}` for {scen["id"]} in the same report.',
                'pytest tests/test_control_code_parity.py passes.',
                'pytest tests/test_entry_counts.py passes.',
                'pytest tests/test_layout_qa_simulator.py tests/test_layout_qa_metrics.py passes.',
                f'Each edited EN entry pairs 1:1 with JP[N] at the same index '
                f'(no merges, no splits, no reorder).',
            ],
            'priorityScore': priority_score,
            'priority': i + 1,  # rank — filled below after sort
            'passes': passes,
            'baseline': {
                'entryCount': scen['entryCount'],
                'byStatus': scen['byStatus'],
                'polishRate': polish,
                'readinessRate': scen.get('readinessRate', 0.0),
            },
            'notes': '',
        })

    # Sort: unfinished worst-first, finished at the bottom.
    stories.sort(key=lambda s: (s['passes'], s['priorityScore']))
    # Renumber priority field after sort.
    for rank, s in enumerate(stories, start=1):
        s['priority'] = rank
    # Strip the internal sort key.
    for s in stories:
        del s['priorityScore']

    open_count = sum(1 for s in stories if not s['passes'])

    prd = {
        'project': 'Langrisser III English patch — layout fitting sweep',
        'branchName': BRANCH_NAME,
        'description': (
            'Iteratively fit broken EN script entries to the engine layout. '
            f'One scen per iteration, up to {ENTRIES_PER_ITERATION} entries. '
            f'Gate per scen: ERROR == {ERROR_THRESHOLD} AND '
            f'polishRate >= {POLISH_THRESHOLD} AND parity tests green.'
        ),
        'gate': {
            'errorThreshold': ERROR_THRESHOLD,
            'polishThreshold': POLISH_THRESHOLD,
            'entriesPerIteration': ENTRIES_PER_ITERATION,
        },
        'excluded': [
            {'scen': k, 'reason': v} for k, v in sorted(excluded_by_scen.items())
        ],
        'userStories': stories,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(prd, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )

    print(f'Wrote {args.output.relative_to(PROJ)}')
    print(f'  stories:  {len(stories)}')
    print(f'  open:     {open_count}')
    print(f'  passing:  {len(stories) - open_count}')
    print(f'  excluded: {len(excluded_by_scen)} ({", ".join(sorted(excluded_by_scen)) or "none"})')
    if open_count:
        top = next(s for s in stories if not s['passes'])
        print(f'  top:     {top["scen"]} '
              f'(ERROR={top["baseline"]["byStatus"]["ERROR"]}, '
              f'polish={top["baseline"]["polishRate"]:.3f})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
