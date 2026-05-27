#!/usr/bin/env python3
"""
plot_audit.py — JP↔EN per-paragraph audit for LANG/PLOT.DAT.

Companion to translation_audit.py, but for the 35 chapter-recap blocks
in PLOT.DAT (loaded from cache/plot_jp.dat after the first build.py
run).

PLOT.DAT block structure:

    <$FFF8NNNN>  scenario title  <$FFFD>
                 paragraph 1     <$FFFD>
                 paragraph 2     <$FFFD>
                 ...
                 paragraph k     <$FFFE>

So the audit unit is a **paragraph** (split on <$FFFD>) rather than a
D00 entry (split on <$FFFE>). Paragraph 0 of each block is the
scenario title line, paragraphs 1..k are narration.

Key difference vs translation_audit.py: in plot context the engine
does NOT substitute <$F600><$0000> with the player name (verified by
playtest — token renders as a raw tile). So this audit reports F600
appearances as ctrl_mismatch, where translation_audit.py masks them.

Usage::

    python3 tools/plot_audit.py              # all 35 blocks, text
    python3 tools/plot_audit.py 2 7 16       # specific block IDs
    python3 tools/plot_audit.py --format=md --review-only
    python3 tools/plot_audit.py --summary
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

from plot_tools import parse_plot, parse_plot_script, N_BLOCKS
from translation_audit import (
    decode_jp_entry, _strip_ctrl, keyword_misses, CTRL_RE,
)

JP_PLOT = PROJ / 'cache' / 'plot_jp.dat'
EN_PLOT_SCRIPT = PROJ / 'scripts' / 'en' / 'plotE.txt'


# ---------------------------------------------------------------------------
# Block → paragraph splitters
# ---------------------------------------------------------------------------

def split_jp_paragraphs(block_raw: bytes) -> list[bytes]:
    """Strip the FFF8NNNN header + FFFE/FFFF terminator from a JP block,
    then split on raw 0xFFFD into paragraph chunks.

    Paragraph 0 is the scenario title. FFFC line breaks remain inline.
    """
    if len(block_raw) < 4 or block_raw[:2] != b'\xff\xf8':
        raise ValueError(f'block does not start with FFF8: {block_raw[:4].hex()}')
    body = block_raw[4:]
    # Strip trailing 0xFFFF (last block only) then 0xFFFE
    if body.endswith(b'\xff\xff'):
        body = body[:-2]
    if body.endswith(b'\xff\xfe'):
        body = body[:-2]

    paragraphs: list[bytes] = []
    cur = bytearray()
    i = 0
    while i + 1 < len(body):
        word = struct.unpack_from('>H', body, i)[0]
        if word == 0xFFFD:
            paragraphs.append(bytes(cur))
            cur = bytearray()
            i += 2
        else:
            cur.extend(body[i:i + 2])
            i += 2
    if cur:
        paragraphs.append(bytes(cur))
    return paragraphs


_HEADER_RE = re.compile(r'^<\$FFF8[0-9A-Fa-f]{4}>')
_TRAIL_FFFF = re.compile(r'<\$FFFF>\s*$')
_TRAIL_FFFE = re.compile(r'<\$FFFE>\s*$')


def split_en_paragraphs(block_text: str) -> list[str]:
    """Mirror of split_jp_paragraphs for an EN plotE block string.

    Strips the <$FFF8NNNN> header + trailing <$FFFE>/<$FFFF>, then
    splits on <$FFFD>. Paragraph 0 is the scenario title.
    """
    text = _HEADER_RE.sub('', block_text, count=1)
    text = _TRAIL_FFFF.sub('', text)
    text = _TRAIL_FFFE.sub('', text)
    return text.split('<$FFFD>')


# ---------------------------------------------------------------------------
# Control-code parity (plot variant: F600 is NOT masked)
# ---------------------------------------------------------------------------

def jp_codes_plot(para_bytes: bytes) -> tuple[str, ...]:
    """Sequence of game-significant control codes in a JP paragraph.

    Differences vs translation_audit.jp_all_codes:
    - F600 IS captured (in plot context it renders as a raw tile, not
      as the player name, so any divergence between JP and EN must be
      flagged).
    - FFFD is never present (it's the paragraph separator, consumed
      by the splitter).
    - FFFC is excluded (language-dependent line break).
    - FFFE/FFFF excluded (block terminator, consumed by splitter).
    """
    codes: list[str] = []
    i = 0
    while i + 1 < len(para_bytes):
        word = struct.unpack_from('>H', para_bytes, i)[0]
        i += 2
        if word in (0xFFFC, 0xFFFE, 0xFFFF):
            continue
        if word == 0xF600:
            # capture F600 AND its parameter word as separate codes,
            # so EN '<$F600><$0000>' shows up as 2 codes vs JP's 0.
            codes.append(f'<${word:04X}>')
            if i + 1 < len(para_bytes):
                param = struct.unpack_from('>H', para_bytes, i)[0]
                codes.append(f'<${param:04X}>')
                i += 2
            continue
        if word >= 0xF000:
            codes.append(f'<${word:04X}>')
    return tuple(codes)


_NAME_TOKEN_RE = re.compile(r"\[diehardt's name\]", re.IGNORECASE)


def en_codes_plot(text: str) -> tuple[str, ...]:
    """Same as jp_codes_plot but reads the EN script text representation.

    The encoder maps the literal alias `[diehardt's name]` to the byte
    pair F600 0000. Treat each alias as a (F600, 0000) code pair so it
    parities against the JP-side capture above.

    Also captures explicit `<$F600><$0000>` escape pairs if anyone
    wrote them directly.
    """
    # Substitute the alias with the canonical escape pair, then parse.
    text = _NAME_TOKEN_RE.sub('<$F600><$0000>', text)
    codes: list[str] = []
    for m in CTRL_RE.finditer(text):
        val = int(m.group(1), 16)
        if val in (0xFFFC, 0xFFFE, 0xFFFF):
            continue
        if val >= 0xF000:
            codes.append(f'<${val:04X}>')
        elif val == 0x0000:
            # 0000 only meaningful as the slot index after F600.
            codes.append(f'<${val:04X}>')
    return tuple(codes)


# ---------------------------------------------------------------------------
# Per-paragraph classification
# ---------------------------------------------------------------------------

@dataclass
class ParaAudit:
    block: int
    paragraph: int           # 0 = title, 1..k = narration
    jp: str
    en: str
    status: str              # OK / REVIEW / MISALIGNED
    issues: list[str]
    jp_codes: tuple[str, ...]
    en_codes: tuple[str, ...]
    jp_len: int
    en_len: int

    def to_dict(self) -> dict:
        d = asdict(self)
        d['jp_codes'] = list(self.jp_codes)
        d['en_codes'] = list(self.en_codes)
        return d


def classify_paragraph(
    block_id: int,
    para_idx: int,
    jp_bytes: bytes,
    en_text: str,
    length_tolerance: float,
) -> ParaAudit:
    jp_decoded = decode_jp_entry(jp_bytes)
    jp_codes = jp_codes_plot(jp_bytes)
    en_codes = en_codes_plot(en_text)
    jp_visible = _strip_ctrl(jp_decoded)
    en_visible = _strip_ctrl(en_text)

    issues: list[str] = []

    if jp_codes != en_codes:
        # Make F600 mismatch explicit — it's the headline plot bug.
        if '<$F600>' in en_codes and '<$F600>' not in jp_codes:
            issues.append('f600_in_en_only')
        else:
            issues.append('ctrl_mismatch')

    if jp_visible and not en_visible:
        issues.append('en_empty')
    if en_visible and not jp_visible:
        issues.append('jp_empty_en_filled')

    if jp_visible and en_visible:
        ratio = max(len(en_visible), 1) / max(len(jp_visible), 1)
        if ratio > length_tolerance or ratio < (1 / length_tolerance):
            issues.append(f'length_ratio={ratio:.1f}x')

        misses = keyword_misses(jp_visible, en_visible)
        if misses:
            issues.append('kw_miss=' + ','.join(misses))

    structural = {'ctrl_mismatch', 'f600_in_en_only',
                  'en_empty', 'jp_empty_en_filled'}
    if any(i in structural for i in issues):
        status = 'MISALIGNED'
    elif issues:
        status = 'REVIEW'
    else:
        status = 'OK'

    return ParaAudit(
        block=block_id, paragraph=para_idx,
        jp=jp_decoded, en=en_text,
        status=status, issues=issues,
        jp_codes=jp_codes, en_codes=en_codes,
        jp_len=len(jp_visible), en_len=len(en_visible),
    )


# ---------------------------------------------------------------------------
# Block audit
# ---------------------------------------------------------------------------

@dataclass
class BlockAudit:
    block: int                # 1..35
    jp_count: int             # paragraphs incl. title
    en_count: int
    counts: dict[str, int]
    paragraphs: list[ParaAudit]


def audit_block(
    block_id: int,
    jp_paragraphs: list[bytes],
    en_paragraphs: list[str],
    length_tolerance: float,
) -> BlockAudit:
    n = max(len(jp_paragraphs), len(en_paragraphs))
    audits: list[ParaAudit] = []
    for i in range(n):
        jp_b = jp_paragraphs[i] if i < len(jp_paragraphs) else b''
        en_t = en_paragraphs[i] if i < len(en_paragraphs) else ''
        if not jp_b and en_t:
            audits.append(ParaAudit(
                block=block_id, paragraph=i,
                jp='', en=en_t, status='MISALIGNED',
                issues=['jp_missing_para'], jp_codes=(), en_codes=(),
                jp_len=0, en_len=len(_strip_ctrl(en_t)),
            ))
        elif jp_b and not en_t:
            audits.append(ParaAudit(
                block=block_id, paragraph=i,
                jp=decode_jp_entry(jp_b), en='',
                status='MISALIGNED', issues=['en_missing_para'],
                jp_codes=jp_codes_plot(jp_b), en_codes=(),
                jp_len=len(_strip_ctrl(decode_jp_entry(jp_b))), en_len=0,
            ))
        else:
            audits.append(classify_paragraph(
                block_id, i, jp_b, en_t, length_tolerance))

    counts = {'OK': 0, 'REVIEW': 0, 'MISALIGNED': 0}
    for a in audits:
        counts[a.status] = counts.get(a.status, 0) + 1

    return BlockAudit(
        block=block_id,
        jp_count=len(jp_paragraphs),
        en_count=len(en_paragraphs),
        counts=counts,
        paragraphs=audits,
    )


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def format_text(report: BlockAudit, review_only: bool = False) -> str:
    delta = report.en_count - report.jp_count
    out = [
        f'=== plot block {report.block:02d} audit ===',
        f'JP paras={report.jp_count} EN paras={report.en_count} Δ={delta:+d}',
        f'OK={report.counts.get("OK",0)} '
        f'REVIEW={report.counts.get("REVIEW",0)} '
        f'MISALIGNED={report.counts.get("MISALIGNED",0)}',
        '',
    ]
    for a in report.paragraphs:
        if review_only and a.status == 'OK':
            continue
        label = 'title' if a.paragraph == 0 else f'¶{a.paragraph}'
        out.append(f'[{a.status}] block {a.block:02d} {label}  '
                   f'({", ".join(a.issues) or "clean"})')
        out.append(f'  JP: {a.jp[:160]}')
        out.append(f'  EN: {a.en[:160]}')
        out.append('')
    return '\n'.join(out)


def format_md(report: BlockAudit, review_only: bool = False) -> str:
    delta = report.en_count - report.jp_count
    delta_s = f'{delta:+d}' if delta else '0'
    out = [
        f'# plot block {report.block:02d} audit',
        '',
        f'JP paragraphs: **{report.jp_count}** | '
        f'EN paragraphs: **{report.en_count}** | Δ: **{delta_s}**',
        '',
        f'Status: OK={report.counts.get("OK",0)} '
        f'REVIEW={report.counts.get("REVIEW",0)} '
        f'MISALIGNED={report.counts.get("MISALIGNED",0)}',
        '',
        '| ¶ | Status | Issues | JP | EN |',
        '| --: | :----- | :----- | :- | :- |',
    ]
    for a in report.paragraphs:
        if review_only and a.status == 'OK':
            continue
        label = 'title' if a.paragraph == 0 else str(a.paragraph)
        jp_disp = a.jp.replace('|', '\\|')[:100]
        en_disp = a.en.replace('|', '\\|')[:100]
        issues = ', '.join(a.issues) or '—'
        out.append(f'| {label} | {a.status} | {issues} | {jp_disp} | {en_disp} |')
    return '\n'.join(out)


def format_json(report: BlockAudit) -> str:
    d = {
        'block': report.block,
        'jp_count': report.jp_count,
        'en_count': report.en_count,
        'counts': report.counts,
        'paragraphs': [a.to_dict() for a in report.paragraphs],
    }
    return json.dumps(d, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('blocks', nargs='*',
                   help='Block IDs 1..35 (e.g. 2, 7, 16). Default: all.')
    p.add_argument('--format', choices=['text', 'md', 'json'], default='text',
                   help='Output format.')
    p.add_argument('--review-only', action='store_true',
                   help='Skip OK paragraphs; show only REVIEW/MISALIGNED.')
    p.add_argument('--summary', action='store_true',
                   help='Print only the per-block summary line.')
    p.add_argument('--length-tolerance', type=float, default=3.0,
                   help='EN/JP length ratio threshold for REVIEW (default 3.0).')
    args = p.parse_args()

    if not JP_PLOT.exists():
        p.error(f'{JP_PLOT} not found — run build.py first')
    if not EN_PLOT_SCRIPT.exists():
        p.error(f'{EN_PLOT_SCRIPT} not found')

    jp_blocks = parse_plot(JP_PLOT.read_bytes())
    en_block_texts = parse_plot_script(EN_PLOT_SCRIPT)

    if args.blocks:
        targets = [int(s) for s in args.blocks]
    else:
        targets = list(range(1, N_BLOCKS + 1))

    for block_id in targets:
        if block_id < 1 or block_id > N_BLOCKS:
            print(f'block {block_id}: skip (out of 1..{N_BLOCKS})',
                  file=sys.stderr)
            continue
        jp_paras = split_jp_paragraphs(jp_blocks[block_id - 1].raw_bytes)
        en_paras = split_en_paragraphs(en_block_texts[block_id - 1])
        report = audit_block(block_id, jp_paras, en_paras,
                             length_tolerance=args.length_tolerance)

        if args.summary:
            delta = report.en_count - report.jp_count
            print(f'block {report.block:02d}: JP={report.jp_count} '
                  f'EN={report.en_count} Δ={delta:+d} '
                  f'OK={report.counts.get("OK",0)} '
                  f'REVIEW={report.counts.get("REVIEW",0)} '
                  f'MISALIGNED={report.counts.get("MISALIGNED",0)}')
            continue

        if args.format == 'md':
            print(format_md(report, review_only=args.review_only))
        elif args.format == 'json':
            print(format_json(report))
        else:
            print(format_text(report, review_only=args.review_only))


if __name__ == '__main__':
    main()
