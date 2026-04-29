#!/usr/bin/env python3
"""
list_named_entries.py — List script entries the engine renders with a
speaker nameplate (12-tile portrait+name balloon, opcode 0xC4).

In a C4 balloon the engine renders ``Name:dialogue`` on line 1 — the
name plus a literal ``:`` tile plus the dialogue text, all on the
same visual line, no `<$FFFC>` break. The name and the colon are
inserted by the engine; the script entry contains only the dialogue.
The engine looks up the speaker's name from the section's name
table using the slot index recorded in the bytecode event record.

Detection mirrors the logic in
``~/translation_analysis/balloon_viewer`` (Go binary used during
playtest), in priority order:

1. **Bytecode opcode** — `tools/balloon_opcodes.py` parses D00.DAT
   event records. Entries flagged `0xC4` are nameplate balloons.
   High confidence, but the 56-byte stride validation in the parser
   only covers about half the sections in practice.
2. **scen001 special case** — section 0 (Lushiris prologue) is
   entirely narration, confirmed by playtest. No portrait+name there.
3. **Scenario-intro narration block** — dialogue entries between a
   "Scenario NN" title (carrying `<$0236>`) and the first
   location/name header that follows. The engine renders these as
   16-tile narration, not portrait+name. Skipped.
4. **Leading-space convention** — for entries the bytecode parser
   doesn't cover, the Akari Dawn dump's convention is: leading space
   in the entry text = portrait+name (C4); no leading space =
   portrait continuation (C0). Verified against the balloon viewer.

Listing entries whose **text** starts with a character name (e.g.
"Gerold, I…") is a different thing — those are dialogue lines
*addressing* a character, not nameplate balloons.

Usage::

    python3 tools/list_named_entries.py
    python3 tools/list_named_entries.py --scenario scen044
    python3 tools/list_named_entries.py --json
    python3 tools/list_named_entries.py --summary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00, parse_script_file
from balloon_opcodes import parse_d00_opcodes, BalloonType
from translation_audit import _strip_ctrl, decode_jp_entry

JP_D00 = PROJ / 'build' / 'd00_jp.dat'
SCRIPTS_DIR = PROJ / 'scripts' / 'en'

CTRL_RE = re.compile(r'<\$([0-9A-Fa-f]{4})>')
FIRST_BREAK_RE = re.compile(r'<\$(FFFC|FFFE|FFFF)>', re.IGNORECASE)


def first_segment(text: str) -> str:
    """Return the visible text of the first balloon line.

    The first segment ends at `<$FFFC>` (newline within balloon),
    `<$FFFE>` (entry terminator), or `<$FFFF>` (metadata terminator).
    Control codes inside the segment (e.g. `<$F600><$0000>`) are
    stripped, leaving only visible characters.
    """
    m = FIRST_BREAK_RE.search(text)
    head = text[: m.start()] if m else text
    return _strip_ctrl(head).strip()


def collect_section_names(en_entries: list[str]) -> list[str]:
    """Pull character names from an EN script's name-table prefix.

    The name table sits at the top of every script: a run of entries
    terminated by `<$FFFF>` containing a single name each. Names with
    a title prefix (e.g. ``Swordmaster Gilbert``, ``Sir Gerold``) are
    expanded to also match the bare name (``Gilbert``, ``Gerold``) so
    a dialogue entry whose first line is just ``Gilbert<$FFFC>...``
    still matches.
    """
    names: list[str] = []
    for entry in en_entries:
        if not entry.endswith('<$FFFF>'):
            break
        name = _strip_ctrl(entry).strip()
        if not name:
            continue
        names.append(name)
        # Also accept the trailing word (last whitespace-separated token)
        # as an alias for title-prefixed names.
        if ' ' in name:
            names.append(name.split()[-1])
    # Dedupe while preserving order
    seen = set()
    deduped = []
    for n in names:
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(n)
    return deduped


def is_named_by_content(entry_text: str, names: list[str]) -> str | None:
    """Heuristic: return the matched name if the first segment looks like
    `name + line break`, else None.
    """
    first = first_segment(entry_text)
    if not first:
        return None
    # Compare case-insensitively. Match if the first segment IS a name
    # (e.g. "Tiaris") or starts with a name followed by punctuation
    # (e.g. "Tiaris:" or "Tiaris -").
    fl = first.lower()
    for name in names:
        nl = name.lower()
        if fl == nl:
            return name
        # name followed by a non-letter — name-like opener, not a sentence
        if fl.startswith(nl) and len(fl) > len(nl) and not fl[len(nl)].isalpha():
            return name
    return None


def parse_script_preserving_indent(path: Path) -> list[str]:
    """Like ``parse_script_file`` but preserves the leading whitespace
    of each line. Needed for the leading-space convention check, since
    `parse_script_file` strips lines."""
    text = path.read_text(encoding='utf-8')
    entries: list[str] = []
    current: list[str] = []
    for raw_line in text.split('\n'):
        # Drop the trailing newline-only artifact and skip pure-empty
        # lines, but DO NOT strip leading whitespace (that's the signal).
        line = raw_line.rstrip('\r\n')
        if not line.strip():
            continue
        if line.lstrip().startswith(('Langrisser', 'Cyber')):
            continue
        current.append(line)
        stripped = line.rstrip()
        if stripped.endswith('<$FFFF>') or stripped.endswith('<$FFFE>'):
            entries.append(''.join(current))
            current = []
    if current:
        full = ''.join(current)
        if not (full.endswith('<$FFFF>') or full.endswith('<$FFFE>')):
            full += '<$FFFF>'
        entries.append(full)
    return entries


def detect_narration_block(en_entries: list[str]) -> set[int]:
    """Return entry indices (0-based) inside a Scenario-intro narration block.

    A scenario intro starts at the entry containing `<$0236>` (scenario
    title) and runs through subsequent dialogue entries until the first
    name-table-like header (entry ending with `<$FFFF>`). The engine
    renders this whole block as narration (16 tiles), not portrait.
    """
    title_idx = -1
    for idx, e in enumerate(en_entries):
        if '<$0236>' in e:
            title_idx = idx
            break
    if title_idx < 0:
        return set()
    block: set[int] = {title_idx}
    for idx in range(title_idx + 1, len(en_entries)):
        e = en_entries[idx]
        if e.endswith('<$FFFF>'):
            break
        # Conditions-of-victory / defeat lines (with `<$01E9>`) are tagged
        # but we still treat them as narration (they are 16-tile strings).
        block.add(idx)
    return block


def classify_section(scen_num: int, jp_section, en_entries: list[str],
                     opmap: dict) -> list[dict]:
    """Return a list of nameplate-entry dicts for one scenario."""
    section_ops = opmap.get(scen_num - 1, {})
    narration_block = detect_narration_block(en_entries)

    results = []
    n = max(jp_section.entry_count, len(en_entries))
    for i in range(n):
        en_text = en_entries[i] if i < len(en_entries) else ''
        # Skip name-table entries (terminate with <$FFFF>).
        if en_text.endswith('<$FFFF>'):
            continue
        jp_bytes = jp_section.entries[i] if i < jp_section.entry_count else b''
        jp_decoded = decode_jp_entry(jp_bytes) if jp_bytes else ''

        info = section_ops.get(i)

        # 1. Bytecode wins. Only PORTRAIT (C4) is a nameplate.
        if info is not None:
            if info.btype != BalloonType.PORTRAIT:
                continue
            results.append({
                'scenario': scen_num,
                'entry': i + 1,
                'source': 'bytecode',
                'balloon_opcode': f'0x{info.opcode:02X}',
                'first_line_en': first_segment(en_text),
                'first_line_jp': first_segment(jp_decoded),
                'en': en_text,
                'jp': jp_decoded,
            })
            continue

        # 2. scen001 (section index 0) is all narration — never C4.
        if scen_num == 1:
            continue
        # 3. Scenario-intro narration block — never C4.
        if i in narration_block:
            continue
        # 4. Leading-space convention: starts with ' ' = C4 (nameplate),
        # no leading space = C0 (portrait continuation).
        if not en_text:
            continue
        if not en_text.startswith(' '):
            continue
        # `<$01E9>` lines are condition tags (narration-class). Skip.
        if '<$01E9>' in en_text:
            continue
        results.append({
            'scenario': scen_num,
            'entry': i + 1,
            'source': 'leading_space',
            'balloon_opcode': '0xC4',
            'first_line_en': first_segment(en_text),
            'first_line_jp': first_segment(jp_decoded),
            'en': en_text,
            'jp': jp_decoded,
        })
    return results


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--scenario', help='Limit to one scenario (e.g. scen044 or 44).')
    # Accepted but no-op now; kept for compatibility with prior runs.
    p.add_argument('--source', choices=['bytecode', 'heuristic', 'both'],
                   default='bytecode', help=argparse.SUPPRESS)
    p.add_argument('--json', action='store_true',
                   help='JSON output (for agents).')
    p.add_argument('--summary', action='store_true',
                   help='Per-scenario count summary.')
    args = p.parse_args()

    if not JP_D00.exists():
        print(f'ERROR: {JP_D00} not found — run build.py first', file=sys.stderr)
        return 1

    raw = JP_D00.read_bytes()
    sections = parse_d00(raw)
    try:
        opmap = parse_d00_opcodes(raw)
    except Exception as e:
        print(f'WARN: bytecode parse failed ({e}); falling back to heuristic',
              file=sys.stderr)
        opmap = {}

    if args.scenario:
        num = int(args.scenario.lower().replace('scen', '').lstrip('0') or '0')
        targets = [num]
    else:
        targets = list(range(1, len(sections) + 1))

    all_results: list[dict] = []
    summary: list[tuple[int, int, int]] = []  # (scen, bytecode, heuristic)

    for num in targets:
        if num < 1 or num > len(sections):
            continue
        en_path = SCRIPTS_DIR / f'scen{num:03d}E.txt'
        if not en_path.exists():
            en_path = SCRIPTS_DIR / f'scen{num:03d}e.txt'
        en_entries = parse_script_preserving_indent(en_path) if en_path.exists() else []

        rows = classify_section(num, sections[num - 1], en_entries, opmap)
        all_results.extend(rows)
        bc = sum(1 for r in rows if r['source'] == 'bytecode')
        ls = sum(1 for r in rows if r['source'] == 'leading_space')
        summary.append((num, bc, ls))

    if args.json:
        print(json.dumps(all_results, ensure_ascii=False, indent=2))
        return 0

    if args.summary:
        print(f'{"scen":>6}  {"bytecode":>9}  {"lead_sp":>8}  total')
        bc_total = ls_total = 0
        for n, bc, ls in summary:
            if bc + ls == 0:
                continue
            bc_total += bc
            ls_total += ls
            print(f'  scen{n:03d}  {bc:>9}  {ls:>8}  {bc + ls:>5}')
        print(f'  {"TOTAL":>6}  {bc_total:>9}  {ls_total:>8}  {bc_total + ls_total:>5}')
        return 0

    # Human-readable per-entry listing
    current_scen = None
    for r in all_results:
        if r['scenario'] != current_scen:
            current_scen = r['scenario']
            print(f'\n=== scen{current_scen:03d} ===')
        tag = r['source']
        op = f' {r["balloon_opcode"]}' if r['balloon_opcode'] else ''
        print(f'  #{r["entry"]:>3} [{tag}{op}]')
        print(f'    JP first: {r["first_line_jp"][:60]}')
        print(f'    EN first: {r["first_line_en"][:60]}')

    if not all_results:
        print('No named entries found with current filters.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
