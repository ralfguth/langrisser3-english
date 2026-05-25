#!/usr/bin/env python3
"""
normalize_scenario_titles.py — rewrite SCENARIO‑NN title entries to mirror JP.

Reads each ``scripts/en/scenNNNE.txt`` file, finds the title entry
(identified by the JP ``ＳＣＥＮＡＲＩＯ`` tile pattern in the paired
JSON), extracts the existing EN title text, and rewrites the entry in
the JP-mirrored 3-line structure::

    <$0000><$FFFC>   Scenario-NN<$FFFC>title text<$FFFE>

Where:
- ``<$0000>`` is the space tile (1 word margin, mirroring JP line 1).
- ``   Scenario-NN`` is the centered header (3 leading spaces, half-width hyphen
  via tile 1627). ``NN`` is derived from the JP digit/marker tiles.
- ``title text`` is the existing translated subtitle, with ``"..."`` quotes
  stripped if present.

Scenario 086 is skipped — its EN entry currently holds prose narration
instead of a title (content bug to be fixed separately).
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent

SCRIPTS_EN = PROJ / 'scripts' / 'en'
PAIRS_DIR = PROJ / 'data' / 'translation_pairs'

# JP tile sequence "ＳＣＥＮＡＲＩＯ" identifies title entries.
SCENARIO_TILE_MARKER = '(0023)(0013)(0015)(001E)(0011)(0022)(0019)(001F)'

# Map JP digit / marker tile id -> ASCII char used in the EN title number.
NUMBER_TILE_TO_CHAR = {
    0x0005: '?',         # ？ (full-width question mark) for bonus scenarios
    0x0007: '0', 0x0008: '1', 0x0009: '2', 0x000A: '3', 0x000B: '4',
    0x000C: '5', 0x000D: '6', 0x000E: '7', 0x000F: '8', 0x0010: '9',
}
HYPHEN_TILE = 0x0174

# Scenarios to skip (content bugs, not format bugs).
SKIP_SCENARIOS = {86}

# Matches every observed EN title variant, capturing number + title text.
#   Variants seen (old formats + the new normalized form for idempotence):
#     "     Scenario<$0236>01<$FFFC> Title <$FFFE>"
#     "= =SCENARIO<$0236>02<$FFFC>     Title <$FFFE>"
#     "Scenario <$0236> 03 \"Title\"<$FFFE>"
#     "Scenario <$0236> <$0613> \"Title\"<$FFFE>"
#     "Scenario <$0236> ?1 \"Title\"<$FFFE>"
#     "Scenario ?2 \"Title\"<$FFFE>"
#     "<$0000><$FFFC>   Scenario-01<$FFFC>Title<$FFFE>"            (old normalized)
#     "<$0000><$FFFC>  <$0000>SCENARIO-01<$FFFC>    Title <$FFFE>" (current normalized)
EN_TITLE_RE = re.compile(
    r'^(?:<\$[0-9A-Fa-f]+>|\s|=)*'
    r'S(?:cenario|CENARIO)\s*(?:<\$0236>)?\s*'
    r'(<\$[0-9A-Fa-f]+>|\??\d+|-?\??\d+)'
    r'(?:<\$FFFC>|\s)*\"?(.+?)\"?\s*<\$FFFE>\s*$'
)


def jp_title_number(jp_raw: str) -> str | None:
    """Extract the scenario number from JP raw tiles (e.g. '01', '15', '?1').

    Reads the 2 tile codes that follow ``(0174)`` (the JP full-width hyphen)
    and converts each to its ASCII counterpart.
    """
    # Find the hyphen tile then take the next two tile codes.
    m = re.search(rf'\(0174\)\(([0-9A-Fa-f]+)\)\(([0-9A-Fa-f]+)\)', jp_raw)
    if not m:
        return None
    t1, t2 = int(m.group(1), 16), int(m.group(2), 16)
    c1 = NUMBER_TILE_TO_CHAR.get(t1)
    c2 = NUMBER_TILE_TO_CHAR.get(t2)
    if not (c1 and c2):
        return None
    return c1 + c2


def find_title_entry(scen_num: int) -> tuple[int, str, str] | None:
    """Return (entry_index, jp_raw, en_raw) for the title entry, if any."""
    pair_path = PAIRS_DIR / f'scen{scen_num:03d}.json'
    if not pair_path.exists():
        return None
    data = json.loads(pair_path.read_text())
    for e in data['entries']:
        if SCENARIO_TILE_MARKER in e.get('jp', ''):
            return e['index'], e['jp'], e['en']
    return None


def build_normalized(number: str, title: str) -> str:
    """Build the new title entry line, JP tile-count-mirrored.

    Layout, line-by-line (using `<$FFFC>` for in-game newline):

      <$0000><$FFFC>  <$0000>SCENARIO-NN<$FFFC>    title text <$FFFE>

    - Leading ``<$0000>``: 1-word top margin (JP line 1).
    - ``  <$0000>`` before SCENARIO: 2 ASCII spaces + explicit space-tile.
      The ``<$0000>`` is anti-bigram protection — otherwise the encoder
      fuses the 3rd space with ``S`` into a (' ', 'S') bigram (tile 0x5c8),
      shifting the ``S`` glyph 8px right and breaking alignment with JP.
    - ``SCENARIO`` uppercase mirrors JP full-width ``ＳＣＥＮＡＲＩＯ`` —
      each uppercase letter is a 16x16 standalone tile, matching JP cell
      width exactly (14 tiles total for header line, same as JP).
    - 4 ASCII spaces + title + 1 trailing space (JP line 3 uses
      4 leading + ``『 』`` brackets; trailing space stands in for ``』``).
    """
    return (f'<$0000><$FFFC>  <$0000>SCENARIO-{number}<$FFFC>'
            f'    {title} <$FFFE>')


def normalize_file(scen_num: int, dry_run: bool = False) -> str | None:
    """Rewrite the title entry in scenNNNE.txt; return status message."""
    if scen_num in SKIP_SCENARIOS:
        return f'scen{scen_num:03d}: SKIP (in SKIP_SCENARIOS)'

    info = find_title_entry(scen_num)
    if info is None:
        return None  # no title entry in this scenario
    entry_idx, jp_raw, en_raw = info

    number = jp_title_number(jp_raw)
    if number is None:
        return f'scen{scen_num:03d}: WARN — could not derive number from JP'

    m = EN_TITLE_RE.match(en_raw)
    if not m:
        return f'scen{scen_num:03d}: WARN — EN entry did not match title regex'
    title = m.group(2).strip()

    new_line = build_normalized(number, title)

    # Locate the matching physical line in the .txt and replace it.
    en_path = SCRIPTS_EN / f'scen{scen_num:03d}E.txt'
    if not en_path.exists():
        en_path = SCRIPTS_EN / f'scen{scen_num:03d}e.txt'
    text = en_path.read_text(encoding='utf-8')
    lines = text.split('\n')
    target_line = en_raw.rstrip()
    matches = [i for i, ln in enumerate(lines) if ln.strip() == target_line.strip()]
    if not matches:
        return f'scen{scen_num:03d}: WARN — title line not found verbatim in file'
    if len(matches) > 1:
        return f'scen{scen_num:03d}: WARN — multiple verbatim matches for title line'
    idx = matches[0]

    if dry_run:
        return (f'scen{scen_num:03d} entry {entry_idx} (line {idx + 1}):\n'
                f'  BEFORE: {lines[idx]}\n'
                f'  AFTER : {new_line}')

    lines[idx] = new_line
    en_path.write_text('\n'.join(lines), encoding='utf-8')
    return f'scen{scen_num:03d}: OK ({number}, title preserved)'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('scenarios', nargs='*',
                    help='scen042, scen044, ... (omit for all)')
    ap.add_argument('--dry-run', action='store_true',
                    help='preview changes without writing files')
    args = ap.parse_args()

    if args.scenarios:
        nums = [int(s.replace('scen', '').lstrip('0') or '0')
                for s in args.scenarios]
    else:
        nums = list(range(1, 126))

    ok = warn = skip = 0
    for n in nums:
        status = normalize_file(n, dry_run=args.dry_run)
        if status is None:
            continue
        print(status)
        if 'OK' in status or 'BEFORE' in status:
            ok += 1
        elif 'SKIP' in status:
            skip += 1
        else:
            warn += 1

    print(f'\nSummary: {ok} processed, {skip} skipped, {warn} warnings')
    return 0 if warn == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
