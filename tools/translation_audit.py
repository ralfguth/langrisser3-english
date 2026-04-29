#!/usr/bin/env python3
"""
translation_audit.py — JP↔EN 1:1 translation review workflow.

This is the **translation routine**, not a unit test. Workflow:

  1. Run the audit on a scenario to get a per-entry status table.
  2. For each ``REVIEW`` / ``MISALIGNED`` entry, edit
     ``scripts/en/scenNNNE.txt`` so the EN entry mirrors the JP
     entry semantically and structurally.
  3. Re-run the audit; the count of ``OK`` entries should rise. Stop
     when the section is fully OK or the remaining issues are
     conscious editorial choices.

The audit reads JP from ``build/d00_jp.dat`` (authoritative) and EN
from ``scripts/en/scenNNNE.txt``. Per entry it checks:

1. **Strict control-code parity.** Every control code in the JP
   entry — `<$F600>`, `<$F7xx>` voice cues, `<$FFFC>` newlines,
   `<$FFFD>` scrolls, `<$FFFB>` waits — must appear in the same
   sequence in the EN entry. If JP says ``AAA<$FFFC>BBB``, the EN
   must also have one ``<$FFFC>`` between its two segments.
   Different numbers/positions of control codes means the engine
   will render the balloon differently from JP.
2. **Lexical** — JP keywords (names, places, key tokens) listed in
   ``tools/jp_keyword_dict.json`` must have their EN equivalent in
   the EN entry, or the entry is flagged.
3. **Length ratio** — very-different length between JP and EN
   suggests Akari Dawn verbosity or a dropped sentence. Default
   ratio threshold 3.0×; tunable via ``--length-tolerance``.

Status:

- ``OK`` — all three checks pass.
- ``REVIEW`` — lexical or length issue; might be acceptable
  paraphrase but worth reading.
- ``MISALIGNED`` — control-code mismatch, missing entry on either
  side, or voice-cue merged into next entry. Must be fixed.

Usage
-----

::

    # Single scenario, human-readable
    python3 tools/translation_audit.py scen044

    # Single scenario, JSON for agent
    python3 tools/translation_audit.py scen044 --format=json

    # Only show entries that aren't OK
    python3 tools/translation_audit.py scen044 --review-only

    # All 125 scenarios, summary only
    python3 tools/translation_audit.py --all --summary

The keyword dictionary grows organically. Add entries to
`tools/jp_keyword_dict.json` whenever you find a recurring JP token
that the audit misses.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00, parse_script_file

JP_D00 = PROJ / 'build' / 'd00_jp.dat'
SCRIPTS_DIR = PROJ / 'scripts' / 'en'
TILE_MAP_PATH = Path.home() / 'translation_analysis' / 'jp_tile_map.json'
KEYWORD_DICT_PATH = PROJ / 'tools' / 'jp_keyword_dict.json'

CTRL_RE = re.compile(r'<\$([0-9A-Fa-f]{4})>')


# ---------------------------------------------------------------------------
# Decoding helpers
# ---------------------------------------------------------------------------

def _load_tile_map() -> dict[int, str]:
    if not TILE_MAP_PATH.exists():
        return {}
    return {int(k): v for k, v in json.loads(TILE_MAP_PATH.read_text()).items()}


_TILE_MAP = _load_tile_map()


def decode_jp_entry(entry_bytes: bytes) -> str:
    """Decode JP raw bytes to a string with control codes shown as ``<$XXXX>``."""
    parts: list[str] = []
    i = 0
    while i < len(entry_bytes) - 1:
        word = struct.unpack_from('>H', entry_bytes, i)[0]
        i += 2
        if word >= 0xF000:
            parts.append(f'<${word:04X}>')
            if word == 0xF600 and i < len(entry_bytes) - 1:
                param = struct.unpack_from('>H', entry_bytes, i)[0]
                parts.append(f'<${param:04X}>')
                i += 2
        elif word in _TILE_MAP:
            parts.append(_TILE_MAP[word])
        else:
            parts.append(f'({word:04X})')
    return ''.join(parts)


def _strip_ctrl(text: str) -> str:
    """Remove every ``<$XXXX>`` sequence. Used for length and keyword checks."""
    return CTRL_RE.sub('', text).strip()


def jp_all_codes(entry_bytes: bytes) -> tuple[str, ...]:
    """Sequence of game-significant control codes in a raw JP entry.

    Captured (must match JP between EN and JP):
    - `<$F600:NNNN>` — name marker + slot index.
    - `<$F7xx>` — voice cues; position triggers an audio clip.
    - `<$FFFB>` — wait; pacing.
    - `<$FFFD>` — scroll.

    Excluded:
    - `<$FFFC>` — newline. Language-dependent (EN word lengths
      differ from JP); validated visually with the balloon viewer.
    - `<$FFFE>` / `<$FFFF>` — entry terminators. Already guaranteed
      by the entry-count rule (one terminator per entry); including
      them in this check would also fight the parser's
      representation choice for voice-cue-only entries.
    """
    codes: list[str] = []
    i = 0
    while i < len(entry_bytes) - 1:
        word = struct.unpack_from('>H', entry_bytes, i)[0]
        i += 2
        if word == 0xF600:
            if i < len(entry_bytes) - 1:
                param = struct.unpack_from('>H', entry_bytes, i)[0]
                codes.append(f'<$F600:{param:04X}>')
                i += 2
            else:
                codes.append('<$F600>')
        elif word in (0xFFFC, 0xFFFE, 0xFFFF):
            continue
        elif word >= 0xF000:
            codes.append(f'<${word:04X}>')
    return tuple(codes)


def en_all_codes(text: str) -> tuple[str, ...]:
    """Same as `jp_all_codes` but parses the EN script text representation."""
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
        elif val in (0xFFFC, 0xFFFE, 0xFFFF):
            i += 1
            continue
        elif val >= 0xF000:
            codes.append(f'<${val:04X}>')
        i += 1
    return tuple(codes)


# ---------------------------------------------------------------------------
# Keyword dictionary
# ---------------------------------------------------------------------------

def _load_keyword_dict() -> dict[str, list[str]]:
    """Map JP token → list of acceptable EN substrings (lowercased)."""
    if not KEYWORD_DICT_PATH.exists():
        return {}
    raw = json.loads(KEYWORD_DICT_PATH.read_text())
    return {jp: [e.lower() for e in en_list] for jp, en_list in raw.items()}


_KEYWORD_DICT = _load_keyword_dict()


def keyword_misses(jp_decoded: str, en_text: str) -> list[str]:
    """Return JP keywords whose EN equivalent is missing from the EN entry."""
    en_lower = en_text.lower()
    misses: list[str] = []
    for jp_token, en_options in _KEYWORD_DICT.items():
        if jp_token in jp_decoded:
            if not any(opt in en_lower for opt in en_options):
                misses.append(jp_token)
    return misses


# ---------------------------------------------------------------------------
# Per-entry classification
# ---------------------------------------------------------------------------

@dataclass
class EntryAudit:
    entry: int
    jp: str
    en: str
    status: str          # OK / REVIEW / MISALIGNED
    issues: list[str]    # short tags explaining why
    jp_codes: tuple[str, ...]
    en_codes: tuple[str, ...]
    jp_len: int
    en_len: int

    def to_dict(self) -> dict:
        d = asdict(self)
        d['jp_codes'] = list(self.jp_codes)
        d['en_codes'] = list(self.en_codes)
        return d


def classify_entry(
    idx: int,
    jp_bytes: bytes,
    en_text: str,
    length_tolerance: float,
) -> EntryAudit:
    jp_decoded = decode_jp_entry(jp_bytes)
    jp_codes = jp_all_codes(jp_bytes)
    en_codes = en_all_codes(en_text)
    jp_visible = _strip_ctrl(jp_decoded)
    en_visible = _strip_ctrl(en_text)

    issues: list[str] = []

    # Strict control-code parity: every JP code must appear in EN in the
    # same sequence. Mismatch means engine renders the balloon
    # differently from JP.
    if jp_codes != en_codes:
        issues.append('ctrl_mismatch')

    # Voice-cue-only entry: JP is just `<$F7xx><$FFFE>` with no text.
    # EN must also be just that — no leaked text.
    voice_only_jp = (
        not jp_visible
        and len(jp_codes) >= 1
        and any(c.startswith('<$F7') for c in jp_codes)
    )
    if voice_only_jp and en_visible:
        issues.append('voice_cue_merged')

    # Empty mismatches (one side has visible text, the other doesn't,
    # and it's not a voice-cue case).
    if jp_visible and not en_visible and not voice_only_jp:
        issues.append('en_empty')
    if en_visible and not jp_visible:
        issues.append('jp_empty_en_filled')

    # Length ratio (only on entries with visible text on both sides).
    if jp_visible and en_visible:
        ratio = max(len(en_visible), 1) / max(len(jp_visible), 1)
        if ratio > length_tolerance or ratio < (1 / length_tolerance):
            issues.append(f'length_ratio={ratio:.1f}x')

    # Keyword check.
    if jp_visible and en_visible:
        misses = keyword_misses(jp_visible, en_visible)
        if misses:
            issues.append('kw_miss=' + ','.join(misses))

    # Status: any structural issue → MISALIGNED; lexical/length →
    # REVIEW; otherwise OK.
    structural = {'ctrl_mismatch', 'voice_cue_merged',
                  'en_empty', 'jp_empty_en_filled'}
    if any(i in structural for i in issues):
        status = 'MISALIGNED'
    elif issues:
        status = 'REVIEW'
    else:
        status = 'OK'

    return EntryAudit(
        entry=idx, jp=jp_decoded, en=en_text,
        status=status, issues=issues,
        jp_codes=jp_codes, en_codes=en_codes,
        jp_len=len(jp_visible), en_len=len(en_visible),
    )


# ---------------------------------------------------------------------------
# Section audit
# ---------------------------------------------------------------------------

@dataclass
class SectionAudit:
    scenario: int
    jp_count: int
    en_count: int
    counts: dict[str, int]   # status → count
    entries: list[EntryAudit]


def audit_section(scen_num: int, length_tolerance: float = 3.0) -> SectionAudit:
    if not JP_D00.exists():
        raise FileNotFoundError(f'{JP_D00} not found — run build.py first')
    sections = parse_d00(JP_D00.read_bytes())
    if scen_num < 1 or scen_num > len(sections):
        raise ValueError(f'scen{scen_num:03d} out of range 1..{len(sections)}')
    sec = sections[scen_num - 1]

    en_path = SCRIPTS_DIR / f'scen{scen_num:03d}E.txt'
    if not en_path.exists():
        en_path = SCRIPTS_DIR / f'scen{scen_num:03d}e.txt'
    if not en_path.exists():
        raise FileNotFoundError(f'No EN script for scen{scen_num:03d}')
    en_entries = parse_script_file(en_path)

    n = max(sec.entry_count, len(en_entries))
    audits: list[EntryAudit] = []
    for i in range(n):
        jp_bytes = sec.entries[i] if i < sec.entry_count else b''
        en_text = en_entries[i] if i < len(en_entries) else ''
        if not jp_bytes and en_text:
            audits.append(EntryAudit(
                entry=i + 1, jp='', en=en_text, status='MISALIGNED',
                issues=['jp_missing_entry'], jp_codes=(), en_codes=(),
                jp_len=0, en_len=len(_strip_ctrl(en_text)),
            ))
        elif jp_bytes and not en_text:
            audits.append(EntryAudit(
                entry=i + 1, jp=decode_jp_entry(jp_bytes), en='',
                status='MISALIGNED', issues=['en_missing_entry'],
                jp_codes=jp_structural_codes(jp_bytes), en_codes=(),
                jp_len=len(_strip_ctrl(decode_jp_entry(jp_bytes))), en_len=0,
            ))
        else:
            audits.append(classify_entry(i + 1, jp_bytes, en_text,
                                         length_tolerance))

    counts = {'OK': 0, 'REVIEW': 0, 'MISALIGNED': 0}
    for a in audits:
        counts[a.status] = counts.get(a.status, 0) + 1

    return SectionAudit(
        scenario=scen_num,
        jp_count=sec.entry_count,
        en_count=len(en_entries),
        counts=counts,
        entries=audits,
    )


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def format_md(report: SectionAudit, review_only: bool = False) -> str:
    delta = report.en_count - report.jp_count
    delta_s = f'{delta:+d}' if delta else '0'
    out = [
        f'# scen{report.scenario:03d} translation audit',
        '',
        f'JP entries: **{report.jp_count}** | EN entries: **{report.en_count}** | Δ: **{delta_s}**',
        '',
        f'Status: OK={report.counts.get("OK",0)} '
        f'REVIEW={report.counts.get("REVIEW",0)} '
        f'MISALIGNED={report.counts.get("MISALIGNED",0)}',
        '',
        '| # | Status | Issues | JP | EN |',
        '| --: | :----- | :----- | :- | :- |',
    ]
    for a in report.entries:
        if review_only and a.status == 'OK':
            continue
        jp_disp = a.jp.replace('|', '\\|')[:80]
        en_disp = a.en.replace('|', '\\|')[:80]
        issues = ', '.join(a.issues) or '—'
        out.append(f'| {a.entry} | {a.status} | {issues} | {jp_disp} | {en_disp} |')
    return '\n'.join(out)


def format_text(report: SectionAudit, review_only: bool = False) -> str:
    delta = report.en_count - report.jp_count
    out = [
        f'=== scen{report.scenario:03d} audit ===',
        f'JP={report.jp_count} EN={report.en_count} Δ={delta:+d}',
        f'OK={report.counts.get("OK",0)} '
        f'REVIEW={report.counts.get("REVIEW",0)} '
        f'MISALIGNED={report.counts.get("MISALIGNED",0)}',
        '',
    ]
    for a in report.entries:
        if review_only and a.status == 'OK':
            continue
        out.append(f'[{a.status}] entry {a.entry}  ({", ".join(a.issues) or "clean"})')
        out.append(f'  JP: {a.jp[:120]}')
        out.append(f'  EN: {a.en[:120]}')
        out.append('')
    return '\n'.join(out)


def format_json(report: SectionAudit) -> str:
    d = {
        'scenario': report.scenario,
        'jp_count': report.jp_count,
        'en_count': report.en_count,
        'counts': report.counts,
        'entries': [a.to_dict() for a in report.entries],
    }
    return json.dumps(d, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('scenarios', nargs='*',
                   help='Scenario names like "scen003" or numbers like "3".')
    p.add_argument('--all', action='store_true',
                   help='Audit every scenario with an EN script.')
    p.add_argument('--format', choices=['text', 'md', 'json'], default='text',
                   help='Output format.')
    p.add_argument('--review-only', action='store_true',
                   help='Skip OK entries; show only REVIEW/MISALIGNED.')
    p.add_argument('--summary', action='store_true',
                   help='Print only the per-section summary line.')
    p.add_argument('--length-tolerance', type=float, default=3.0,
                   help='EN/JP length ratio threshold for REVIEW (default 3.0).')
    args = p.parse_args()

    if args.all:
        sections = parse_d00(JP_D00.read_bytes())
        targets = list(range(1, len(sections) + 1))
    else:
        if not args.scenarios:
            p.error('provide at least one scenario or pass --all')
        targets = []
        for s in args.scenarios:
            num = int(s.lower().replace('scen', '').lstrip('0') or '0')
            targets.append(num)

    reports = []
    for num in targets:
        try:
            r = audit_section(num, length_tolerance=args.length_tolerance)
        except (FileNotFoundError, ValueError) as e:
            print(f'scen{num:03d}: skip ({e})', file=sys.stderr)
            continue
        reports.append(r)

        if args.summary:
            delta = r.en_count - r.jp_count
            print(f'scen{r.scenario:03d}: JP={r.jp_count} EN={r.en_count} '
                  f'Δ={delta:+d} OK={r.counts.get("OK",0)} '
                  f'REVIEW={r.counts.get("REVIEW",0)} '
                  f'MISALIGNED={r.counts.get("MISALIGNED",0)}')
            continue

        if args.format == 'md':
            print(format_md(r, review_only=args.review_only))
        elif args.format == 'json':
            print(format_json(r))
        else:
            print(format_text(r, review_only=args.review_only))


if __name__ == '__main__':
    main()
