#!/usr/bin/env python3
"""
dump_jp_en_pairs.py — Generate per-scenario JP↔EN paired JSON files.

For each scenario in `build/d00_jp.dat`, emit a JSON file at
`data/translation_pairs/scenNNN.json` that contains every entry's JP
raw form (decoded via tile map) alongside the corresponding EN entry
from `scripts/en/scenNNNE.txt`. Designed for agent consumption — an
agent can read the JSON directly without re-parsing the binary or
running tooling.

Each scenario JSON looks like:

::

    {
      "scenario": 44,
      "jp_count": 68,
      "en_count": 68,
      "entries": [
        {
          "index": 1,
          "jp": "ティアリス<$FFFF>",
          "jp_codes": ["<$FFFF>"],
          "jp_visible": "ティアリス",
          "en": "Tiaris<$FFFF>",
          "en_codes": ["<$FFFF>"],
          "en_visible": "Tiaris",
          "ctrl_match": true
        },
        ...
      ]
    }

Run once to generate, re-run when the JP source or EN scripts change.
The output is checked in to the repo so agents have a stable
artifact to read; do not gitignore.

Usage::

    python3 tools/dump_jp_en_pairs.py            # all 125 sections
    python3 tools/dump_jp_en_pairs.py scen003    # one section
    python3 tools/dump_jp_en_pairs.py --pretty   # readable indentation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00, parse_script_file
from translation_audit import (
    decode_jp_entry,
    jp_all_codes,
    en_all_codes,
    _strip_ctrl,
)
from balloon_opcodes import parse_d00_opcodes, BalloonType
from list_named_entries import (
    parse_script_preserving_indent,
    detect_narration_block,
)

JP_D00 = PROJ / 'build' / 'd00_jp.dat'
SCRIPTS_DIR = PROJ / 'scripts' / 'en'
OUT_DIR = PROJ / 'data' / 'translation_pairs'


_BTYPE_NAMES = {
    BalloonType.PORTRAIT: 'portrait_name',
    BalloonType.PORT_CONT: 'portrait_cont',
    BalloonType.NARRATION: 'narration',
    BalloonType.UNKNOWN: 'unknown',
}

# 12-tile portrait balloons fit ~24 chars per line of bigram-encoded text;
# 16-tile narration balloons fit ~32. Encoded with the field for agent use.
_TILE_BUDGET = {
    'portrait_name': 12,
    'portrait_cont': 12,
    'narration': 16,
    'unknown': 12,
    'none': 12,
}


def _classify_entry_balloon(scen_num: int, entry_idx: int,
                             info, en_raw_text: str,
                             narration_block: set[int]) -> tuple[str, str | None, str]:
    """Return (balloon_type, balloon_opcode, source) for one entry.

    Mirrors the priority chain in `list_named_entries.classify_section`:
    bytecode > scen001 narration > Scenario-intro narration block >
    leading-space heuristic (C4 vs C0).
    """
    if info is not None:
        return _BTYPE_NAMES.get(info.btype, 'unknown'), \
            f'0x{info.opcode:02X}', 'bytecode'
    if scen_num == 1:
        return 'narration', '0xBC', 'scen001_override'
    if entry_idx in narration_block:
        return 'narration', '0xBC', 'narration_block'
    if not en_raw_text:
        return 'none', None, 'no_text'
    if '<$01E9>' in en_raw_text:
        return 'narration', '0xBC', 'condition_tag'
    if en_raw_text.endswith('<$FFFF>'):
        # Name-table / location-header entry, not a balloon.
        return 'none', None, 'name_table'
    if en_raw_text.startswith(' '):
        return 'portrait_name', '0xC4', 'leading_space'
    return 'portrait_cont', '0xC0', 'no_leading_space'


def build_scenario_json(scen_num: int, jp_section, en_entries: list[str],
                        en_raw_entries: list[str],
                        balloon_map: dict) -> dict:
    n = max(jp_section.entry_count, len(en_entries))
    section_balloons = balloon_map.get(scen_num - 1, {})
    narration_block = detect_narration_block(en_raw_entries)
    entries = []
    for i in range(n):
        jp_bytes = jp_section.entries[i] if i < jp_section.entry_count else b''
        en_text = en_entries[i] if i < len(en_entries) else ''
        en_raw = en_raw_entries[i] if i < len(en_raw_entries) else ''
        jp_decoded = decode_jp_entry(jp_bytes) if jp_bytes else ''
        jp_codes = list(jp_all_codes(jp_bytes)) if jp_bytes else []
        en_codes = list(en_all_codes(en_text)) if en_text else []
        info = section_balloons.get(i)
        btype, opcode, source = _classify_entry_balloon(
            scen_num, i, info, en_raw, narration_block)
        entries.append({
            'index': i + 1,
            'balloon_type': btype,
            'balloon_opcode': opcode,
            'balloon_source': source,
            'tile_budget': _TILE_BUDGET[btype],
            'jp': jp_decoded,
            'jp_codes': jp_codes,
            'jp_visible': _strip_ctrl(jp_decoded),
            'en': en_text,
            'en_codes': en_codes,
            'en_visible': _strip_ctrl(en_text),
            'ctrl_match': jp_codes == en_codes,
        })
    return {
        'scenario': scen_num,
        'jp_count': jp_section.entry_count,
        'en_count': len(en_entries),
        'delta': len(en_entries) - jp_section.entry_count,
        'entries': entries,
    }


def write_scenario(scen_num: int, jp_section, pretty: bool,
                   balloon_map: dict) -> Path:
    en_path = SCRIPTS_DIR / f'scen{scen_num:03d}E.txt'
    if not en_path.exists():
        en_path = SCRIPTS_DIR / f'scen{scen_num:03d}e.txt'
    en_entries = parse_script_file(en_path) if en_path.exists() else []
    en_raw = parse_script_preserving_indent(en_path) if en_path.exists() else []

    data = build_scenario_json(scen_num, jp_section, en_entries,
                               en_raw, balloon_map)
    out_path = OUT_DIR / f'scen{scen_num:03d}.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    else:
        out_path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('scenarios', nargs='*',
                        help='Specific scenarios to dump (e.g. scen003 or 3); empty = all')
    parser.add_argument('--pretty', action='store_true',
                        help='Indent JSON for human reading (larger files)')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress per-file progress output')
    args = parser.parse_args()

    if not JP_D00.exists():
        print(f'ERROR: {JP_D00} not found — run build.py first', file=sys.stderr)
        return 1

    raw = JP_D00.read_bytes()
    sections = parse_d00(raw)
    try:
        balloon_map = parse_d00_opcodes(raw)
    except Exception as e:  # pragma: no cover
        print(f'WARN: balloon opcode parse failed ({e}); '
              f'balloon_type fields will be "none"', file=sys.stderr)
        balloon_map = {}

    if args.scenarios:
        targets = []
        for s in args.scenarios:
            num = int(s.lower().replace('scen', '').lstrip('0') or '0')
            if num < 1 or num > len(sections):
                print(f'WARN: scen{num:03d} out of range', file=sys.stderr)
                continue
            targets.append(num)
    else:
        targets = list(range(1, len(sections) + 1))

    written = 0
    for num in targets:
        out = write_scenario(num, sections[num - 1], args.pretty, balloon_map)
        written += 1
        if not args.quiet:
            print(f'  wrote {out.relative_to(PROJ)}')

    print(f'Wrote {written} pair files to {OUT_DIR.relative_to(PROJ)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
