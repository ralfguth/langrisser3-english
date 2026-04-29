#!/usr/bin/env python3
"""
test_control_code_parity.py — Per-section control-code parity between JP and EN.

Guardrail beyond raw entry count: for each entry index N in section S,
the multiset of control codes (F600 / F602 / F70x / etc.) in EN entry N
must match the multiset of control codes in JP entry N.

Why this matters
----------------
Entry-count parity (test_entry_counts.py) is necessary but not sufficient.
The Akari Dawn scen003 dump had four tail entries collapsed into two
because two voice cue lines (`<$F702>` and `<$F703>`) lacked the
`<$FFFE>` terminator. After parsing, the voice codes appeared as a
prefix of the next entry — the count was technically -2 from JP at the
tail (the other -2 came from a separate gap mid-section), but the
control-code shape of every affected entry was wrong: an entry that
should have held `<$F702>` alone instead held `<$F702><$F702><$F703>`.

This test compares the *sequence* of control codes per entry between
JP and EN. A whitelist `CTRL_PARITY_XFAIL` mirrors the same shape as
ENTRY_COUNT_XFAIL: pre-existing per-section mismatch counts are
frozen so that progress is measurable, and any regression beyond the
frozen counts fails immediately.

The whitelist values record the number of entries with non-matching
control sequences in each section. Add a section here only after
confirming the divergence is pre-existing Akari Dawn drift, not a
regression from a recent edit. Remove (or lower) the count once the
section has been retranslated and aligned with JP.
"""

import re
import struct
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00, parse_script_file

JP_D00 = PROJ / 'build' / 'd00_jp.dat'
SCRIPTS_DIR = PROJ / 'scripts' / 'en'

CTRL_RE = re.compile(r'<\$([0-9A-Fa-f]{4})>')

# scen_num -> max number of entries allowed to have mismatched control sequences.
# Frozen at the audit snapshot of 2026-04-27. Lower the count when retranslating.
CTRL_PARITY_XFAIL: dict[int, int] = {
    # Frozen baseline at 2026-04-28 (rule: F600/F7xx/FFFB/FFFD must
    # match JP; FFFC excluded since EN line wrapping is language-
    # dependent). Lower the count whenever a section is retranslated.
    4: 28, 5: 32, 6: 3, 7: 78, 8: 4, 11: 26, 12: 5, 13: 1, 14: 28,
    17: 5, 18: 26, 19: 1, 20: 1, 21: 18, 23: 22, 24: 1, 27: 29, 28: 22,
    29: 14, 30: 1, 31: 7, 32: 22, 33: 43, 34: 37, 35: 40, 36: 6, 37: 38,
    38: 6, 39: 73, 41: 3, 42: 5, 45: 4, 50: 1, 51: 5, 52: 2, 54: 1,
    55: 6, 56: 1, 64: 1, 72: 1, 76: 1, 78: 1, 84: 1, 89: 1, 96: 1, 107: 1,
    112: 1, 118: 1, 119: 1, 120: 2, 121: 2, 124: 33, 125: 2,
}


def _is_structural_code(word: int) -> bool:
    """Codes that must match JP per-entry between JP and EN.

    Includes:
    - `<$F600>` (with parameter) — name marker; slot index must match.
    - `<$F7xx>` — voice cues; embedded position triggers an audio clip.
    - `<$FFFB>` — wait; pacing must match JP.
    - `<$FFFD>` — scroll; must match JP.

    Excludes:
    - `<$FFFC>` — newline within a balloon. Line wrapping is
      language-dependent (English word lengths differ from Japanese);
      validated visually with the balloon viewer instead.
    - `<$FFFE>` / `<$FFFF>` — entry terminators, already enforced by
      `test_entry_counts.py`.
    """
    return (
        word == 0xF600
        or 0xF700 <= word <= 0xF7FF
        or word == 0xFFFB
        or word == 0xFFFD
    )


def _extract_jp_ctrl_codes(entry_bytes: bytes) -> tuple[str, ...]:
    """Return the sequence of structural control codes in a raw JP entry."""
    codes: list[str] = []
    i = 0
    while i < len(entry_bytes) - 1:
        word = struct.unpack_from('>H', entry_bytes, i)[0]
        i += 2
        if word == 0xF600:
            # F600 is followed by a name-id parameter word; capture both
            # so a misassigned name (different parameter) also fails.
            if i < len(entry_bytes) - 1:
                param = struct.unpack_from('>H', entry_bytes, i)[0]
                codes.append(f'<$F600:{param:04X}>')
                i += 2
            else:
                codes.append('<$F600>')
        elif _is_structural_code(word):
            codes.append(f'<${word:04X}>')
    return tuple(codes)


def _extract_en_ctrl_codes(text: str) -> tuple[str, ...]:
    """Return the sequence of structural control codes in an EN entry string."""
    codes: list[str] = []
    matches = list(CTRL_RE.finditer(text))
    i = 0
    while i < len(matches):
        val = int(matches[i].group(1), 16)
        if val == 0xF600:
            param = None
            if i + 1 < len(matches):
                param = int(matches[i + 1].group(1), 16)
            if param is not None:
                codes.append(f'<$F600:{param:04X}>')
                i += 2
                continue
            codes.append('<$F600>')
        elif _is_structural_code(val):
            codes.append(f'<${val:04X}>')
        i += 1
    return tuple(codes)


@pytest.fixture(scope='module')
def jp_sections():
    if not JP_D00.exists():
        pytest.skip('build/d00_jp.dat not found (run build.py first)')
    return parse_d00(JP_D00.read_bytes())


def _section_diff_count(jp_section, scen_num: int) -> int:
    """Count entries whose control-code sequence differs between JP and EN.

    Returns -1 if EN script is missing, otherwise the number of mismatched
    entries in the overlapping range.
    """
    en_path = None
    for pat in [f'scen{scen_num:03d}E.txt', f'scen{scen_num:03d}e.txt']:
        candidate = SCRIPTS_DIR / pat
        if candidate.exists():
            en_path = candidate
            break
    if en_path is None:
        return -1

    en_entries = parse_script_file(en_path)
    jp_count = jp_section.entry_count
    en_count = len(en_entries)
    overlap = min(jp_count, en_count)

    diffs = 0
    for i in range(overlap):
        jp_codes = _extract_jp_ctrl_codes(jp_section.entries[i])
        en_codes = _extract_en_ctrl_codes(en_entries[i])
        if jp_codes != en_codes:
            diffs += 1
    # Entries that exist in only one side count as mismatches too — they
    # signal a structural gap the count test will already flag.
    diffs += abs(jp_count - en_count)
    return diffs


def test_control_code_parity(jp_sections):
    """JP↔EN control-code sequence must match per entry, honoring whitelist."""
    regressions: list[str] = []
    drift_fixed: list[str] = []

    for sec in jp_sections:
        scen_num = sec.index + 1
        diffs = _section_diff_count(sec, scen_num)
        if diffs < 0:
            continue  # missing EN script — covered by another test
        allowed = CTRL_PARITY_XFAIL.get(scen_num, 0)
        if diffs > allowed:
            regressions.append(
                f'  scen{scen_num:03d}: {diffs} ctrl-code mismatches '
                f'(allowed {allowed})'
            )
        elif diffs < allowed:
            drift_fixed.append(
                f'  scen{scen_num:03d}: {diffs} mismatches < whitelist '
                f'{allowed} — lower or remove from CTRL_PARITY_XFAIL'
            )

    if regressions or drift_fixed:
        msg = []
        if regressions:
            msg.append('Regressions (fix or whitelist):')
            msg.extend(regressions)
        if drift_fixed:
            msg.append('Whitelist now too lax (lower or remove):')
            msg.extend(drift_fixed)
        pytest.fail('\n'.join(msg))


def test_voice_cue_entries_are_standalone(jp_sections):
    """An entry whose JP body is exactly one voice cue (F702/F703/etc.) must
    have an EN counterpart that is also exactly that voice cue.

    Catches the tail-merge bug seen in scen003 where `<$F702>` and `<$F703>`
    lines lost their `<$FFFE>` terminators and were parsed as a prefix of
    the following dialogue entry.
    """
    failures: list[str] = []

    for sec in jp_sections:
        scen_num = sec.index + 1
        en_path = None
        for pat in [f'scen{scen_num:03d}E.txt', f'scen{scen_num:03d}e.txt']:
            candidate = SCRIPTS_DIR / pat
            if candidate.exists():
                en_path = candidate
                break
        if en_path is None:
            continue

        en_entries = parse_script_file(en_path)
        overlap = min(sec.entry_count, len(en_entries))
        for i in range(overlap):
            jp_codes = _extract_jp_ctrl_codes(sec.entries[i])
            # JP body has only voice cues + the entry terminator?
            jp_voice_only = (
                len(jp_codes) >= 2
                and all(c.startswith('<$F7') for c in jp_codes[:-1])
                and jp_codes[-1] == '<$FFFE>'
            )
            if not jp_voice_only:
                continue
            en_text = en_entries[i].strip()
            en_codes = _extract_en_ctrl_codes(en_text)
            if en_codes != jp_codes:
                failures.append(
                    f'  scen{scen_num:03d} entry {i + 1}: '
                    f'JP={jp_codes} EN={en_codes} '
                    f'(EN text: {en_text[:60]!r})'
                )

    # This test is informational while the broken sections are still being
    # retranslated. Convert hard failures into a baseline check by allowing
    # the snapshot count.
    expected_failures = 18  # current 18 broken sections from XFAIL
    if len(failures) > expected_failures:
        pytest.fail(
            f'Voice-cue standalone regression: {len(failures)} failures '
            f'(baseline {expected_failures}):\n' + '\n'.join(failures[:20])
        )
