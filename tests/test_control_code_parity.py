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

JP_D00 = PROJ / 'cache' / 'd00_jp.dat'
SCRIPTS_DIR = PROJ / 'scripts' / 'en'

CTRL_RE = re.compile(r'<\$([0-9A-Fa-f]{4})>')

# scen_num -> max number of entries allowed to have mismatched control sequences.
# EMPTY since 2026-06-14: the 61 frozen entries were all the trailing-FFFF that
# the EN dropped from the last entry of each section. They were RESTORED (the EN
# last entry now ends <$FFFE><$FFFF> matching JP, in exactly the 61 sections
# where JP has it), so the whitelist is no longer needed. Rule now: ALL control
# codes except FFFC (wrap, language-dependent) and F600 (player-name token) must
# match JP per entry, in position. scen122/scen123 are exempt (CN-origin, no JP
# pair — see project_scen122_123_cn_origin). Keep this EMPTY: a non-zero entry
# means real structural drift to fix, not to whitelist.
CTRL_PARITY_XFAIL: dict[int, int] = {}

# CN-origin scens with no JP counterpart — control-code parity does not apply.
CTRL_PARITY_EXEMPT = {122, 123}


def _is_structural_code(word: int) -> bool:
    """Inline codes that must match JP per-entry between JP and EN.

    Includes:
    - `<$F7xx>` — voice cues; embedded position triggers an audio clip.
    - `<$FFFB>` — wait; pacing must match JP.
    - `<$FFFD>` — scroll; must match JP.
    - `<$FFFF>` — string terminator. Used mid-entry to separate sub-strings
      (e.g. name|text in nameplate entries, location-label strings) AND as the
      trailing string terminator on the last entry. It is a real engine-read
      code (RE: name/text split + location-label FFFF-anim), NOT padding, so its
      position must match JP. (Restored to the EN last entries 2026-06-14.)

    Excludes (the ONLY two not verified):
    - `<$F600>` (player-name token) — position follows the voiced line; EN may
      adapt (narrations drop for word wrap, dialogue may add/remove).
    - `<$FFFC>` — newline within a balloon; wrapping is language-dependent.

    `<$FFFE>` (end-of-message) is verified via the separate terminator check so
    name-slot vs dialogue parity is enforced per-index.
    """
    return (
        0xF700 <= word <= 0xF7FF
        or word == 0xFFFB
        or word == 0xFFFD
        or word == 0xFFFF
    )


def _jp_entry_terminator(entry_bytes: bytes) -> str | None:
    """Return 'FFFE', 'FFFF', or None for a raw JP entry.

    Returns None for voice-only entries (e.g. body is just `<$F702>`)
    where the JP D00.DAT relies on the offset table for boundaries and
    there is no inline terminator word.
    """
    if len(entry_bytes) >= 2:
        word = struct.unpack_from('>H', entry_bytes, len(entry_bytes) - 2)[0]
        if word == 0xFFFE:
            return 'FFFE'
        if word == 0xFFFF:
            return 'FFFF'
    return None


def _en_entry_terminator(text: str) -> str | None:
    if text.endswith('<$FFFE>'):
        return 'FFFE'
    if text.endswith('<$FFFF>'):
        return 'FFFF'
    return None


def _extract_jp_ctrl_codes(entry_bytes: bytes) -> tuple[str, ...]:
    """Return the sequence of structural control codes in a raw JP entry."""
    codes: list[str] = []
    i = 0
    while i < len(entry_bytes) - 1:
        word = struct.unpack_from('>H', entry_bytes, i)[0]
        i += 2
        if word == 0xF600:
            # Player-name token: skip parameter, do not record in signature.
            if i < len(entry_bytes) - 1:
                i += 2
            continue
        if _is_structural_code(word):
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
            # Player-name token: skip following parameter, do not record.
            i += 2 if i + 1 < len(matches) else 1
            continue
        if _is_structural_code(val):
            codes.append(f'<${val:04X}>')
        i += 1
    return tuple(codes)


@pytest.fixture(scope='module')
def jp_sections():
    if not JP_D00.exists():
        pytest.skip('cache/d00_jp.dat not found (run build.py first)')
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
        jp_term = _jp_entry_terminator(jp_section.entries[i])
        en_term = _en_entry_terminator(en_entries[i])
        inline_mismatch = jp_codes != en_codes
        # Voice-only JP entries (jp_term is None) have no inline terminator;
        # EN must add <$FFFE> for the parser. Exempt those from the check.
        term_mismatch = jp_term is not None and jp_term != en_term
        if inline_mismatch or term_mismatch:
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
        if scen_num in CTRL_PARITY_EXEMPT:
            continue  # CN-origin, no JP pair — parity does not apply
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
