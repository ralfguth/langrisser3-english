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
ENTRY_COUNT_XFAIL: dict[int, tuple[int, int]] = {
    3: (222, 226),
    4: (175, 179),
    5: (238, 250),
    7: (180, 207),
    11: (243, 249),
    14: (161, 166),
    17: (171, 173),
    18: (210, 214),
    21: (91, 97),
    23: (176, 184),
    27: (159, 169),
    28: (146, 148),
    29: (147, 148),
    32: (173, 175),
    33: (330, 334),
    34: (256, 270),
    35: (274, 278),
    37: (222, 225),
    39: (296, 304),
}

JP_DIR = Path.home() / 'Jogos/emulacao/romsets/sega-saturn/Langrisser III (Japan)'
JP_TRACK01 = JP_DIR / 'Langrisser III (Japan) (3M) (Track 01).bin'
SCRIPTS_DIR = PROJ / 'scripts' / 'en'

SECTOR_SIZE = 2352
USER_OFFSET = 16
USER_SIZE = 2048


def _extract_d00():
    """Extract D00.DAT from JP ISO and parse sections."""
    import math, struct
    image = JP_TRACK01.read_bytes()

    # Quick ISO9660 parse to find D00.DAT
    pvd = image[16 * SECTOR_SIZE + USER_OFFSET:16 * SECTOR_SIZE + USER_OFFSET + USER_SIZE]
    root_len = pvd[156]
    root = pvd[156:156 + root_len]
    root_extent = struct.unpack_from('<I', root, 2)[0]
    root_size = struct.unpack_from('<I', root, 10)[0]

    # Import iso_tools for proper parsing
    from iso_tools import build_file_index, extract_file_data
    file_index = build_file_index(bytearray(image))
    d00_entry = file_index.get('LANG/SCEN/D00.DAT')
    assert d00_entry is not None, "D00.DAT not found in ISO"
    d00_data = extract_file_data(image, d00_entry.extent, d00_entry.size)
    return parse_d00(d00_data)


@pytest.fixture(scope='module')
def jp_sections():
    if not JP_TRACK01.exists():
        pytest.skip('JP ISO not available')
    return _extract_d00()


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


def test_scen001_lushiris_prologue_order():
    """Canary: Lushiris prologue anchor strings must appear in expected order.

    Defense in depth against reshuffles in scen001E.txt that preserve the total
    entry count but shift strings in the character-creation questionnaire, which
    the game accesses by index rather than sequentially. A reshuffle that kept
    the count at 169 would bypass ``test_entry_counts_match`` but still silently
    corrupt the questionnaire. See ``claude_tasks_ec/_context.md`` and commit
    ``5a27497`` for background on the original regression.
    """
    entries = parse_script_file(SCRIPTS_DIR / 'scen001E.txt')

    # Anchor substrings (lower-cased) expected in narrative order. Note that
    # "goddess of light" sits on a ``<$FFFC>`` continuation line inside the
    # same entry as "my name is lushiris", so two anchors may legitimately
    # share an entry — we require monotonically non-decreasing indices, not
    # strictly increasing.
    anchors = [
        'my name is lushiris',
        'goddess of light',
        'please tell me',
        'gift for you',
        'what is the essential quality',
    ]

    found: dict[str, int] = {}
    for anchor in anchors:
        matches = [i for i, e in enumerate(entries) if anchor in e.lower()]
        if len(matches) == 0:
            pytest.fail(
                f"Lushiris canary: anchor {anchor!r} not found in scen001E.txt — "
                f"prologue may have been rewritten, update the anchor list"
            )
        if len(matches) > 1:
            pytest.fail(
                f"Lushiris canary: anchor {anchor!r} found in multiple entries "
                f"{matches} — ambiguous, cannot verify order"
            )
        found[anchor] = matches[0]

    indices = [found[a] for a in anchors]
    if indices != sorted(indices):
        locs = ', '.join(f'{a!r}@{found[a]}' for a in anchors)
        pytest.fail(
            f"Lushiris canary: prologue anchors out of order (expected "
            f"non-decreasing entry indices): {locs}"
        )

    # Specific invariants for the character-creation questionnaire flow.
    name_idx = found['please tell me']
    push_idx = found['gift for you']
    q1_idx = found['what is the essential quality']

    if name_idx >= q1_idx:
        pytest.fail(
            f"Lushiris canary: 'please tell me' (entry {name_idx}) must "
            f"appear BEFORE 'what is the essential quality' (entry {q1_idx}) — "
            f"the questionnaire indices are misordered"
        )
    if push_idx >= q1_idx:
        pytest.fail(
            f"Lushiris canary: 'gift for you' (entry {push_idx}) "
            f"must appear BEFORE the first questionnaire question "
            f"'what is the essential quality' (entry {q1_idx})"
        )
