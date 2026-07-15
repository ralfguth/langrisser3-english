#!/usr/bin/env python3
"""polish_order.py — the walkthrough-ordered work-list for the 100% polish pass.

The order is the player's journey, mirroring the strategy guide's chapter order
(guide.json): character creation -> each in-game scenario's intro cutscene,
battle dialogue, and post-battle cutscene -> secret stages interleaved at their
unlock points -> endings. Mapping (confirmed by the ＳＣＥＮＡＲＩＯ‐NN labels and
by the guide's own scen references):

    Scenario N   battle  = scen{N+1}              (Sc01->002 .. Sc36->037)
                 cutscene = scen{40+2N} (intro)   (+ scen{40+2N+1} = part 2 / post)
    Secret ?1..?4 battle = scen038..041, cutscene = scen114/115 .. 120/121
    Secret ?5            = label-less Gell bonus, no scen
    Opening              = scen122/123 (CN-origin subtitles, layout-QA exempt)
    Character creation   = scen001
    Endings              = scen124 (epilogues) / scen125 (post-credits)

`build_order()` returns the structured order; `render(order, report)` renders the
markdown work-list, annotating each scen with how many entries are not yet
POLISHED (from a layout-qa report) so the pass knows where the work is.

CLI:  python3 tools/polish_order.py [--report reports/layout-qa-report.json]
                                     [--output archive/docs/polish-order.md]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJ = Path(__file__).resolve().parent.parent

# In-game scenario titles (mirror the guide's guide.json).
TITLES = {
    1: "Assault on the Floating Castle", 2: "Madness in Laffel",
    3: "The Sad-Eyed Master Swordsman", 4: "General Geier",
    5: "Wily General Emerick", 6: "Enemies on all Sides",
    7: "Mountain Pass Reunion", 8: "The Southern Lushiris Gate",
    9: "Shaman Attack", 10: "Ceremony of Scorching Heat", 11: "Deception",
    12: "The Wise Sage Fauvel", 13: "To Hunt a Holy Beast",
    14: "Dios on the Run", 15: "The Sword of Decimation", 16: "Call to Arms",
    17: "Operation Recapture Laffel", 18: "Ultimate Military Device of Antiquity",
    19: "A man called Bortz", 20: "Skirmish in the Vast Skies",
    21: "The Magnificent capital, Larcussia", 22: "To a New Battle",
    23: "The Necromancer, Again", 24: "The Field Marshal's Determination",
    25: "Light Over Shadow", 26: "Suspicion", 27: "The Shapeshifter Feraquea",
    28: "Demon Defense Force", 29: "Böser, Master of the Demon Blade",
    30: "Behind the Mask", 31: "Threads between People",
    32: "The Insanity of King Wilder", 33: "Unwavering Loyalty",
    34: "The Shape of a Heart", 35: "The True Enemy", 36: "The Birth of a Legend",
}

# Secret stage that unlocks AFTER a given scenario number:
#   N -> (code, name, battle_scen, cutscene_a, cutscene_b)
SECRET = {
    4:  ("?1", "Hidden Gyudon Restaurant", 38, 114, 115),
    10: ("?2", "Successive Heroes",        39, 116, 117),
    25: ("?5", "Tale of a Gell Family",    None, None, None),
    27: ("?3", "The Queen and Aesthetic Men", 40, 118, 119),
    35: ("?4", "The Mightiest Foe",        41, 120, 121),
}


def _sid(n: int) -> str:
    return f"scen{n:03d}"


def build_order() -> List[Dict[str, Any]]:
    """Return the ordered work-list as a list of sections.

    Each section: {'title': str, 'items': [{'scen': str, 'role': str} | {'note': str}]}.
    """
    order: List[Dict[str, Any]] = []

    order.append({'title': "0 — Opening & Character Creation", 'items': [
        {'scen': 'scen122', 'role': 'opening movie subtitles (CN-origin)'},
        {'scen': 'scen123', 'role': 'opening movie subtitles (CN-origin)'},
        {'scen': 'scen001', 'role': 'Character Creation — Lushiris quiz'},
    ]})

    for n in range(1, 37):
        order.append({'title': f"Scenario {n:02d} — {TITLES[n]}", 'items': [
            {'scen': _sid(40 + 2 * n), 'role': 'intro cutscene'},
            {'scen': _sid(n + 1), 'role': 'battle dialogue'},
            {'scen': _sid(40 + 2 * n + 1), 'role': 'post-battle cutscene'},
        ]})
        if n in SECRET:
            code, name, batt, c1, c2 = SECRET[n]
            items: List[Dict[str, Any]] = []
            if c1:
                items.append({'scen': _sid(c1), 'role': 'cutscene'})
            if batt:
                items.append({'scen': _sid(batt), 'role': 'battle dialogue'})
            if c2:
                items.append({'scen': _sid(c2), 'role': 'cutscene'})
            if not batt:
                items.append({'note': 'no dedicated scen — label-less Gell bonus, '
                                      'no cutscene/dialogue file'})
            order.append({
                'title': f"Stage {code} — {name}  (unlocks after Scenario {n:02d})",
                'items': items})

    order.append({'title': "Endings", 'items': [
        {'scen': 'scen124', 'role': 'epilogues / best-ending route'},
        {'scen': 'scen125', 'role': 'post-credits / free-talk'},
    ]})
    return order


def all_scens_in_order() -> List[str]:
    """Flat list of every scen id in walkthrough order (each appears once)."""
    return [it['scen'] for sec in build_order() for it in sec['items']
            if 'scen' in it]


def _not_polished(report: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Map scen_id -> (not_polished_count, exempt) from a layout-qa report."""
    if not report:
        return {}
    out: Dict[str, Any] = {}
    exempt = set(report.get('summary', {}).get('exemptScenarios', []))
    for s in report.get('scenarios', []):
        n = s['entryCount'] - s['byStatus']['POLISHED']
        out[s['id']] = (n, s['id'] in exempt)
    return out


def render(order: List[Dict[str, Any]],
           report: Optional[Dict[str, Any]] = None) -> str:
    np = _not_polished(report)
    lines: List[str] = ["# Polish order — walkthrough sequence\n"]
    lines.append(
        "Drive the 100% polish pass in this order (the player's journey). Per "
        "scenario: **intro cutscene → battle dialogue → post-battle cutscene**. "
        "Counts are entries not yet POLISHED; re-check live with "
        "`python3 -m tools.layout_qa.cli analyze scenNNN --jp-scripts scripts/jp`.\n")
    if report:
        s = report.get('summary', {})
        lines.append(f"_Corpus: polishRate={s.get('polishRate', 0):.1%}, "
                     f"playability={s.get('playabilityRate', 0):.1%}, "
                     f"{s.get('entryCount', 0)} entries._\n")

    def fmt(it: Dict[str, Any]) -> str:
        if 'note' in it:
            return f"  - ({it['note']})"
        sid = it['scen']
        tag = ''
        badge = ''
        if sid in np:
            n, exempt = np[sid]
            tag = ' [EXEMPT]' if exempt else ''
            badge = ' — ✅ POLISHED' if n == 0 else f' — {n} to polish'
        elif report:
            badge = ' — (not in report)'
        return f"  - {sid} — {it['role']}{tag}{badge}"

    for sec in order:
        depth = '###' if sec['title'].startswith('Stage') else '##'
        lines.append(f"\n{depth} {sec['title']}\n")
        lines.extend(fmt(it) for it in sec['items'])

    lines.append("\n> Appendix chapters (Heroine System, Classes, Item List, "
                 "Cheats) are guide content sourced from FNT_SYS, not scen "
                 "dialogue — not part of this scen polish order.")
    return '\n'.join(lines) + '\n'


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog='polish_order',
        description='Render the walkthrough-ordered polish work-list.')
    ap.add_argument('--report', type=Path,
                    default=PROJ / 'reports' / 'layout-qa-report.json',
                    help='layout-qa report JSON for live not-polished counts '
                         '(optional; order renders without it).')
    ap.add_argument('--output', type=Path,
                    default=PROJ / 'archive' / 'docs' / 'polish-order.md',
                    help='Markdown output path.')
    args = ap.parse_args(argv)

    report = None
    if args.report.exists():
        report = json.loads(args.report.read_text(encoding='utf-8'))
    text = render(build_order(), report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding='utf-8')
    print(f"polish order → {args.output} "
          f"({len(all_scens_in_order())} scens"
          + ("" if report else "; no report — run layout-qa for counts") + ")")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
