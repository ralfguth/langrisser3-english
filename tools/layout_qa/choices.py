#!/usr/bin/env python3
"""choices.py — CHOICE-fit analysis for player-facing menu options.

A CHOICE entry (marked in ``config/entry-annotations.json`` with
``class == "CHOICE"``) is a single-line selection option. Its budget is the
resolved balloon width minus the 1-tile selection cursor that occupies column 0,
so:

    CHOICE budget = (resolved balloon width) - 1 cursor tile

An option that wraps (`<$FFFC>`) or exceeds the budget renders broken — it spills
into the line below, which is the slot for the *next* option.

Choices are structurally invisible in the script (plain `<$FFFE>` entries, no
marker), so the JP-anchored annotation store is the oracle for which entries are
options. The balloon width comes from the entry's resolved classification (with
``config/layout-overrides.json`` applied). ``max-JP`` is only a fallback estimate
when an entry's balloon cannot be classified (not used here yet).

See: archive/docs/20260614_choice_budget_and_meta_guide_plan.md
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from layout_qa.parser import parse_scenario  # noqa: E402
from layout_qa.classifier import classify_entries  # noqa: E402
from layout_qa.simulator import iter_tiles  # noqa: E402

# The selection cursor occupies one tile (column 0). Confirmed by the user
# 2026-06-14 against two anchors: field 12-wide balloons fit JP options up to 11,
# narration 16-wide balloons fit correct EN options up to 15.
CURSOR_TILES = 1

# Canonical profile names encode their geometry as ``..._<WIDTH>X<LINES>``
# (e.g. NARRATION_16X5, DIALOGUE_12X4, LABEL_CHARACTER_12X1). Read width from
# the name so this module needs no dependency on the CLI's spec table.
_PROFILE_WIDTH_RE = re.compile(r'_(\d+)X\d+$')
_CTRL_RE = re.compile(r'<\$[0-9A-Fa-f]{4}>')


def _profile_width(profile: Optional[str]) -> Optional[int]:
    if not profile:
        return None
    m = _PROFILE_WIDTH_RE.search(profile)
    return int(m.group(1)) if m else None


def _line_widths(raw: str) -> List[int]:
    """Real tile-cost width of each `<$FFFC>`-delimited visual line.

    Uses the simulator's `iter_tiles` cost model so cost-0 right-blank spaces do
    not inflate the width.
    """
    widths: List[int] = []
    for part in re.split(r'<\$FFFC>', raw):
        text = _CTRL_RE.sub('', part)
        widths.append(sum(cost for _, cost in iter_tiles(text)))
    return widths


def analyze_choice_fit(
    scen_id: str,
    en_dir: Path,
    jp_dir: Path,
    overrides: Dict[str, Dict],
    annotations: Dict[str, Dict],
) -> List[Dict[str, Any]]:
    """Return CHOICE-fit issues for one scenario.

    Each issue is a dict::

        {scen, index, code, severity, profile, width, budget, lines, notes}

    where ``code`` is ``choice_multiline`` (the option wraps to >1 line) or
    ``choice_overflow`` (single line wider than the budget). ``notes`` carries the
    annotation's free-form note through so it surfaces alongside the finding.
    """
    ann = annotations.get(scen_id, {}) or {}
    choices = {
        int(k): v for k, v in ann.items()
        if isinstance(v, dict) and v.get('class') == 'CHOICE'
    }
    if not choices:
        return []

    entries = parse_scenario(Path(en_dir) / f'{scen_id}E.txt')
    classifications = classify_entries(entries, scen_overrides=overrides)

    issues: List[Dict[str, Any]] = []
    n = len(entries)
    for idx in sorted(choices):
        # An annotated index that doesn't exist in this parsed file (e.g. the
        # live config applied to a different/smaller file) can't be analyzed —
        # skip it rather than crash. Real entry-count drift is caught elsewhere.
        if idx < 0 or idx >= n:
            continue
        meta = choices[idx]
        entry = entries[idx]
        profile = getattr(classifications[idx], 'profile', None)
        width = _profile_width(profile)
        if width is None:
            # Unclassified balloon → max-JP fallback (future); skip for now.
            continue
        budget = width - CURSOR_TILES
        line_w = _line_widths(entry.raw)
        base = {
            'scen': scen_id, 'index': idx, 'severity': 'error',
            'profile': profile, 'budget': budget,
            'notes': meta.get('notes'),
        }
        if len(line_w) > 1:
            issues.append({**base, 'code': 'choice_multiline',
                           'width': max(line_w), 'lines': len(line_w)})
        elif line_w[0] > budget:
            issues.append({**base, 'code': 'choice_overflow',
                           'width': line_w[0], 'lines': 1})
    return issues
