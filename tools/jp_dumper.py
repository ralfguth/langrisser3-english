#!/usr/bin/env python3
"""
jp_dumper.py - Dump Japanese text from D00.DAT and compare with EN translations.

Extracts raw tile codes from each section, decodes control codes,
and compares entry counts between JP and EN scripts.
"""

import struct
import sys
from pathlib import Path

from d00_tools import parse_d00, D00Section


def dump_section_entries(section: D00Section) -> list:
    """Dump entries from a section as lists of (type, value) tuples.

    type = 'text' (tile code) or 'ctrl' (control code) or 'param' (parameter).
    """
    entries = []
    for entry_bytes in section.entries:
        tokens = []
        i = 0
        while i < len(entry_bytes) - 1:
            word = struct.unpack_from('>H', entry_bytes, i)[0]
            i += 2
            if word >= 0xF000:
                tokens.append(('ctrl', word))
                # F600 has a parameter word
                if word == 0xF600 and i < len(entry_bytes) - 1:
                    param = struct.unpack_from('>H', entry_bytes, i)[0]
                    tokens.append(('param', param))
                    i += 2
            else:
                tokens.append(('text', word))
        entries.append(tokens)
    return entries


def count_text_chars(tokens: list) -> int:
    """Count text characters (non-control) in a token list."""
    return sum(1 for t, v in tokens if t == 'text')


def compare_jp_en(d00_path: Path, scripts_dir: Path) -> dict:
    """Compare JP D00.DAT sections with EN script files.

    Returns comparison report.
    """
    data = d00_path.read_bytes()
    sections = parse_d00(data)

    report = {
        'total_sections': len(sections),
        'sections': [],
    }

    for sec in sections:
        scen_num = sec.index + 1
        jp_entries = dump_section_entries(sec)

        # Find EN script
        en_path = None
        en_count = 0
        for pat in [f'scen{scen_num:03d}E.txt', f'scen{scen_num:03d}e.txt']:
            candidate = scripts_dir / pat
            if candidate.exists():
                en_path = candidate
                break

        if en_path:
            text = en_path.read_text('utf-8')
            en_lines = [l.strip() for l in text.split('\n')
                        if l.strip() and not l.strip().startswith('Langrisser')
                        and not l.strip().startswith('Cyber')]
            en_count = len(en_lines)

        jp_count = len(jp_entries)
        status = 'OK' if en_count == jp_count else (
            'MISMATCH' if en_path else 'MISSING'
        )

        sec_report = {
            'section': sec.index,
            'scenario': scen_num,
            'jp_entries': jp_count,
            'en_entries': en_count,
            'status': status,
            'has_voice': any(
                0xF700 <= v <= 0xF7FF
                for tokens in jp_entries
                for t, v in tokens if t == 'ctrl'
            ),
            'has_timing': any(
                0xFE00 <= v <= 0xFEFF
                for tokens in jp_entries
                for t, v in tokens if t == 'ctrl'
            ),
        }

        # Collect unique control codes
        all_ctrl = set()
        for tokens in jp_entries:
            for t, v in tokens:
                if t == 'ctrl':
                    all_ctrl.add(v)
        sec_report['control_codes'] = sorted(all_ctrl)

        report['sections'].append(sec_report)

    return report


def print_report(report: dict) -> None:
    """Print comparison report."""
    missing = 0
    mismatch = 0
    ok = 0
    voice_sections = 0
    timing_sections = 0

    for sec in report['sections']:
        if sec['status'] == 'MISSING':
            missing += 1
        elif sec['status'] == 'MISMATCH':
            mismatch += 1
        else:
            ok += 1
        if sec['has_voice']:
            voice_sections += 1
        if sec['has_timing']:
            timing_sections += 1

    print(f'=== JP↔EN Comparison Report ===')
    print(f'Total sections: {report["total_sections"]}')
    print(f'  OK (entry counts match): {ok}')
    print(f'  MISMATCH (different counts): {mismatch}')
    print(f'  MISSING (no EN translation): {missing}')
    print(f'  Sections with voice codes (F7xx): {voice_sections}')
    print(f'  Sections with timing codes (FExx): {timing_sections}')

    if mismatch:
        print(f'\n--- Entry Count Mismatches ---')
        for sec in report['sections']:
            if sec['status'] == 'MISMATCH':
                print(f'  scen{sec["scenario"]:03d}: JP={sec["jp_entries"]} EN={sec["en_entries"]} '
                      f'({"+" if sec["en_entries"] > sec["jp_entries"] else ""}'
                      f'{sec["en_entries"] - sec["jp_entries"]})')

    if missing:
        print(f'\n--- Missing EN Translations ---')
        nums = [sec["scenario"] for sec in report["sections"] if sec["status"] == "MISSING"]
        print(f'  Scenarios: {", ".join(str(n) for n in nums)}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <d00.dat> <scripts_en_dir>')
        sys.exit(1)

    report = compare_jp_en(Path(sys.argv[1]), Path(sys.argv[2]))
    print_report(report)
