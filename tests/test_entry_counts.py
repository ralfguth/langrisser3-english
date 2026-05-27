#!/usr/bin/env python3
"""
test_entry_counts.py - Validate EN script entry counts match JP D00.DAT sections.

Guardrail: ensures translated scripts have the correct number of entries
to prevent padding/truncation issues that cause in-game display bugs.

The game reads strings by index, so a single mismatched <$FFFE> / <$FFFC>
shift in the middle of a section desynchronizes every string after it
(this is exactly the Lushiris prologue regression — see commit 5a27497
and claude_tasks_ec/_context.md). The test below freezes the current
snapshot of pre-existing mismatches in ENTRY_COUNT_XFAIL and fails on
any new or worsened deviation, so middle-merge bugs can no longer pass
silently under measure.py's tail padding.
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00, parse_script_file

# Sections with pre-existing entry count mismatches, frozen at T1 snapshot.
# Each entry is scen_num -> (expected_en_count, expected_jp_count).
# Remove an entry only after the underlying file is fixed to match JP.
ENTRY_COUNT_XFAIL: dict[int, tuple[int, int]] = {}

JP_D00 = PROJ / 'cache' / 'd00_jp.dat'
SCRIPTS_DIR = PROJ / 'scripts' / 'en'


@pytest.fixture(scope='module')
def jp_sections():
    if not JP_D00.exists():
        pytest.skip('cache/d00_jp.dat not found (run build.py first)')
    return parse_d00(JP_D00.read_bytes())


def test_all_sections_have_scripts(jp_sections):
    """Every JP section should have a corresponding EN script file."""
    missing = []
    for sec in jp_sections:
        scen_num = sec.index + 1
        path = SCRIPTS_DIR / f'scen{scen_num:03d}E.txt'
        if not path.exists():
            # Also check lowercase
            path2 = SCRIPTS_DIR / f'scen{scen_num:03d}e.txt'
            if not path2.exists():
                missing.append(scen_num)
    if missing:
        pytest.fail(f'{len(missing)} missing EN scripts: {missing[:10]}...')


def test_entry_counts_match(jp_sections):
    """EN script entry count must match JP entry count, honoring the XFAIL whitelist.

    Any mismatch outside ``ENTRY_COUNT_XFAIL`` fails immediately. Entries in the
    whitelist must match their frozen ``(en, jp)`` counts exactly; a whitelisted
    section that now matches JP also fails, prompting removal from the whitelist.
    See the module docstring and ``claude_tasks_ec/_context.md`` for background.
    """
    regressions: list[str] = []
    drift_fixed: list[str] = []
    report_lines: list[str] = []

    for sec in jp_sections:
        scen_num = sec.index + 1
        script_path = None
        for pattern in [f'scen{scen_num:03d}E.txt', f'scen{scen_num:03d}e.txt']:
            candidate = SCRIPTS_DIR / pattern
            if candidate.exists():
                script_path = candidate
                break
        if script_path is None:
            continue

        en_count = len(parse_script_file(script_path))
        jp_count = sec.entry_count
        delta = en_count - jp_count

        if scen_num in ENTRY_COUNT_XFAIL:
            expected_en, expected_jp = ENTRY_COUNT_XFAIL[scen_num]
            if en_count == jp_count:
                drift_fixed.append(
                    f"  scen{scen_num:03d}: now matches JP ({jp_count}); "
                    f"remove from ENTRY_COUNT_XFAIL"
                )
            elif (en_count, jp_count) != (expected_en, expected_jp):
                regressions.append(
                    f"  scen{scen_num:03d}: whitelisted as EN={expected_en} JP={expected_jp}, "
                    f"now EN={en_count} JP={jp_count} (delta={delta:+d})"
                )
            report_lines.append(
                f"  scen{scen_num:03d}: JP={jp_count} EN={en_count} (delta={delta:+d}) [xfail]"
            )
        elif delta != 0:
            regressions.append(
                f"  scen{scen_num:03d}: JP={jp_count} EN={en_count} (delta={delta:+d}) "
                f"— not in ENTRY_COUNT_XFAIL"
            )

    if report_lines:
        print(f'\nEntry count status ({len(report_lines)} whitelisted sections):')
        print('\n'.join(report_lines))

    failures: list[str] = []
    if regressions:
        failures.append(
            f"{len(regressions)} entry count regression(s) detected:\n"
            + '\n'.join(regressions)
        )
    if drift_fixed:
        failures.append(
            f"{len(drift_fixed)} whitelisted section(s) now match JP — "
            f"remove them from ENTRY_COUNT_XFAIL:\n"
            + '\n'.join(drift_fixed)
        )
    if failures:
        pytest.fail('\n\n'.join(failures))


def test_entry_count_report(jp_sections):
    """Print a summary report of all entry counts (informational)."""
    total_jp = 0
    total_en = 0
    translated = 0
    padded = 0

    for sec in jp_sections:
        scen_num = sec.index + 1
        total_jp += sec.entry_count

        script_path = None
        for pattern in [f'scen{scen_num:03d}E.txt', f'scen{scen_num:03d}e.txt']:
            candidate = SCRIPTS_DIR / pattern
            if candidate.exists():
                script_path = candidate
                break

        if script_path:
            en_entries = parse_script_file(script_path)
            total_en += len(en_entries)
            translated += 1
            if len(en_entries) < sec.entry_count:
                padded += 1

    print(f'\n--- Entry Count Report ---')
    print(f'Total sections: {len(jp_sections)}')
    print(f'Translated: {translated}')
    print(f'Total JP entries: {total_jp}')
    print(f'Total EN entries: {total_en}')
    print(f'Sections needing padding: {padded}')

