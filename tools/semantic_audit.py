#!/usr/bin/env python3
"""
semantic_audit.py — Detect semantic JP↔EN parity issues that the
structural audit cannot see.

Structural parity (count, control codes, voice cues) is verified by
``translation_audit.py``. Once a section is structurally OK, the next
class of bugs is *semantic*: Akari Dawn drift where the translation
loses meaning, repeats lines that JP varied, or merges variations
that JP intentionally separated.

Detectors
---------

**wrong_repeat** — Adjacent EN entries that are identical (or
near-identical after stripping control codes) while the corresponding
JP entries are distinct. Strong signal of an AD copy-paste error.
JP duplicates are intentional in this codebase (memory:
``feedback_jp_duplicates_intentional``) so we only flag the inverse:
EN duplicated where JP varies.

**wrong_merge** — A single EN entry whose decoded text covers content
from multiple distinct JP entries. Detected when the EN entry's length
exceeds JP+JP_next by 1.5x and the JP_next has a very short EN
counterpart (suggesting the EN translator squashed two JP entries
into one and left the second EN entry truncated).

**suspect_translation** — EN length << JP length AND JP contains a
keyword that doesn't appear in EN. Together these suggest the
translation dropped meaningful content, not just shortened phrasing.

Output
------

Per-scenario markdown report ordered by detector severity. Use::

    python3 tools/semantic_audit.py scen007
    python3 tools/semantic_audit.py --all > /tmp/semantic.md
    python3 tools/semantic_audit.py --all --format=summary

The report is meant to drive the next editorial pass (manual review
+ ChatGPT). It does not modify any file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00, parse_script_file
from translation_audit import (
    decode_jp_entry, _strip_ctrl, CTRL_RE, _KEYWORD_DICT as KEYWORDS,
)

JP_D00 = PROJ / 'build' / 'd00_jp.dat'
SCRIPTS_DIR = PROJ / 'scripts' / 'en'


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r'\s+')


def normalize_en(text: str) -> str:
    """Lowercase, strip ctrl codes and whitespace runs for similarity."""
    bare = _strip_ctrl(text)
    bare = _WS_RE.sub(' ', bare).strip().lower()
    return bare


def normalize_jp(text: str) -> str:
    """Strip ctrl codes from decoded JP for similarity."""
    return _WS_RE.sub('', _strip_ctrl(text)).strip()


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    scen: int
    entry: int
    detector: str
    severity: str           # 'high' | 'medium' | 'low'
    note: str
    jp: str
    en: str
    extra: dict = field(default_factory=dict)


def _is_voice_cue_only(en: str) -> bool:
    """True for entries that only carry voice cues (e.g. ``<$F702><$FFFE>``)."""
    return _strip_ctrl(en) == '' and '<$F70' in en


def detect_wrong_repeat(scen_num: int, jp_entries: list[bytes],
                        en_entries: list[str]) -> list[Finding]:
    """Flag adjacent EN duplicates where the JP varies."""
    findings: list[Finding] = []
    for i in range(len(en_entries) - 1):
        en_a = normalize_en(en_entries[i])
        en_b = normalize_en(en_entries[i + 1])
        if not en_a or not en_b:
            continue
        if en_a != en_b:
            continue
        if i + 1 >= len(jp_entries):
            continue
        jp_a = normalize_jp(decode_jp_entry(jp_entries[i]))
        jp_b = normalize_jp(decode_jp_entry(jp_entries[i + 1]))
        if not jp_a or not jp_b:
            continue
        if jp_a == jp_b:
            # JP duplicates are intentional; skip.
            continue
        findings.append(Finding(
            scen=scen_num, entry=i + 1,
            detector='wrong_repeat', severity='high',
            note=f'EN matches entry {i + 2} but JP differs',
            jp=decode_jp_entry(jp_entries[i]),
            en=en_entries[i],
            extra={'next_jp': decode_jp_entry(jp_entries[i + 1]),
                   'next_en': en_entries[i + 1]},
        ))
    return findings


def detect_suspect_translation(scen_num: int, jp_entries: list[bytes],
                               en_entries: list[str],
                               min_jp_len: int = 20,
                               max_ratio: float = 0.25) -> list[Finding]:
    """Flag entries where EN is dramatically shorter AND drops a JP keyword.

    Both conditions must hold: very short EN (might just be a tight
    paraphrase) is OK; a missing keyword alone is often editorial.
    Both together strongly suggest content was lost.
    """
    findings: list[Finding] = []
    for i, (jp_b, en_t) in enumerate(zip(jp_entries, en_entries)):
        jp_decoded = decode_jp_entry(jp_b)
        jp_bare = _strip_ctrl(jp_decoded)
        en_bare = _strip_ctrl(en_t)
        if _is_voice_cue_only(en_t):
            continue
        if len(jp_bare) < min_jp_len:
            continue
        ratio = len(en_bare) / max(len(jp_bare), 1)
        if ratio > max_ratio:
            continue
        # Find any JP keyword missing from EN.
        misses = []
        for jp_token, en_variants in KEYWORDS.items():
            if jp_token in jp_decoded:
                if not any(v.lower() in en_bare.lower() for v in en_variants):
                    misses.append(jp_token)
        if not misses:
            continue
        findings.append(Finding(
            scen=scen_num, entry=i + 1,
            detector='suspect_translation', severity='high',
            note=f'EN/JP ratio {ratio:.2f}, missing {", ".join(misses[:3])}',
            jp=jp_decoded, en=en_t,
            extra={'ratio': ratio, 'missing_kw': misses},
        ))
    return findings


def detect_keyword_shift(scen_num: int, jp_entries: list[bytes],
                         en_entries: list[str]) -> list[Finding]:
    """Detect content shift via keyword cross-overlap (length-agnostic).

    For each entry i, find JP keywords (from the keyword dict) that
    appear in EN[i]. If those keywords' JP forms are absent from JP[i]
    but present in JP[i-1] or JP[i+1], EN[i] is likely shifted by one
    slot. This catches the AD pattern that pure length checks miss:
    an EN entry whose length is normal but whose *content* belongs to
    the neighbour JP entry.
    """
    findings: list[Finding] = []
    # Pre-decode JP entries once.
    jp_decoded = [decode_jp_entry(b) for b in jp_entries]

    # Filter to keywords distinctive enough to signal a real shift.
    # Single-kanji generics like 兵/戦/敵 collide with too many EN words
    # ("troops" matches both 兵 and 部隊; "battle" matches both 戦 and any
    # combat context). Require ≥3 chars to make false positives rare.
    # Exception: known long names get a free pass.
    distinctive = {
        jp_t: en_vs for jp_t, en_vs in KEYWORDS.items()
        if len(jp_t) >= 3
    }

    for i, en_t in enumerate(en_entries):
        if _is_voice_cue_only(en_t):
            continue
        en_bare = _strip_ctrl(en_t).lower()
        if not en_bare:
            continue

        # Which keywords does EN[i] use?
        present_kw: list[tuple[str, list[str]]] = []
        for jp_token, en_variants in distinctive.items():
            if any(v.lower() in en_bare for v in en_variants):
                present_kw.append((jp_token, en_variants))

        if not present_kw:
            continue

        # For each keyword EN[i] uses, is the JP token in JP[i]? If not,
        # check JP[i-1] and JP[i+1]. A match in the neighbour but not in
        # JP[i] is the shift signal.
        leaked: list[str] = []
        for jp_token, en_variants in present_kw:
            if jp_token in jp_decoded[i]:
                continue
            in_prev = i > 0 and jp_token in jp_decoded[i - 1]
            in_next = (i + 1 < len(jp_decoded)
                       and jp_token in jp_decoded[i + 1])
            if in_prev or in_next:
                direction = []
                if in_prev:
                    direction.append('JP[-1]')
                if in_next:
                    direction.append('JP[+1]')
                leaked.append(f'{jp_token} ({"|".join(direction)})')

        if not leaked:
            continue

        # Hint which side the shift is on for the user.
        extra = {}
        if i > 0:
            extra['prev_jp'] = jp_decoded[i - 1]
            extra['prev_en'] = en_entries[i - 1]
        if i + 1 < len(jp_decoded):
            extra['next_jp'] = jp_decoded[i + 1]
            extra['next_en'] = en_entries[i + 1]

        findings.append(Finding(
            scen=scen_num, entry=i + 1,
            detector='keyword_shift', severity='high',
            note=f'EN uses keyword in neighbour JP slot: {", ".join(leaked[:3])}',
            jp=jp_decoded[i], en=en_t, extra=extra,
        ))
    return findings


def detect_wrong_merge(scen_num: int, jp_entries: list[bytes],
                       en_entries: list[str]) -> list[Finding]:
    """Disabled — length-based merge detection too noisy. See keyword_shift."""
    return []


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


DETECTORS = [detect_wrong_repeat, detect_keyword_shift]


def audit_scenario(scen_num: int, sections) -> list[Finding]:
    en_path = SCRIPTS_DIR / f'scen{scen_num:03d}E.txt'
    if not en_path.exists():
        return []
    sec = sections[scen_num - 1]
    jp_entries = sec.entries
    en_entries = parse_script_file(en_path)
    if len(jp_entries) != len(en_entries):
        # Structural mismatch — semantic audit irrelevant; skip.
        return []
    findings: list[Finding] = []
    for det in DETECTORS:
        findings.extend(det(scen_num, jp_entries, en_entries))
    return findings


def format_markdown(findings: list[Finding]) -> str:
    if not findings:
        return '_No semantic issues detected._\n'
    by_scen: dict[int, list[Finding]] = {}
    for f in findings:
        by_scen.setdefault(f.scen, []).append(f)
    out: list[str] = []
    for scen, items in sorted(by_scen.items()):
        out.append(f'## scen{scen:03d} — {len(items)} finding(s)\n')
        items.sort(key=lambda x: (
            {'high': 0, 'medium': 1, 'low': 2}[x.severity], x.entry
        ))
        for f in items:
            out.append(f'### entry {f.entry} — `{f.detector}` ({f.severity})')
            out.append(f'_{f.note}_\n')
            out.append(f'```')
            out.append(f'JP: {f.jp}')
            out.append(f'EN: {f.en}')
            if 'next_jp' in f.extra:
                out.append(f'JP next: {f.extra["next_jp"]}')
                out.append(f'EN next: {f.extra["next_en"]}')
            out.append('```\n')
    return '\n'.join(out)


def format_summary(findings: list[Finding]) -> str:
    by_scen: dict[int, dict[str, int]] = {}
    for f in findings:
        by_scen.setdefault(f.scen, {}).setdefault(f.detector, 0)
        by_scen[f.scen][f.detector] += 1
    lines = []
    for scen, counts in sorted(by_scen.items()):
        parts = [f'{k}={v}' for k, v in sorted(counts.items())]
        total = sum(counts.values())
        lines.append(f'scen{scen:03d}: total={total} {" ".join(parts)}')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('scenarios', nargs='*',
                        help='e.g. scen007 scen039. Default: --all')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--format', choices=['md', 'summary', 'json'],
                        default='md')
    args = parser.parse_args()

    if not JP_D00.exists():
        sys.exit(f'JP D00 not found at {JP_D00}; run build.py first.')

    sections = parse_d00(JP_D00.read_bytes())

    if args.all or not args.scenarios:
        targets = list(range(1, len(sections) + 1))
    else:
        targets = [int(s.removeprefix('scen').lstrip('0') or '0')
                   for s in args.scenarios]

    all_findings: list[Finding] = []
    for scen in targets:
        all_findings.extend(audit_scenario(scen, sections))

    if args.format == 'summary':
        print(format_summary(all_findings))
    elif args.format == 'json':
        print(json.dumps([f.__dict__ for f in all_findings], ensure_ascii=False,
                         indent=2))
    else:
        print(format_markdown(all_findings))


if __name__ == '__main__':
    main()
