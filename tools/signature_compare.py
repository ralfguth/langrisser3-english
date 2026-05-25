"""signature_compare.py — cross-version structural signature compare.

Builds an ordered structural signature per entry per version (JP / EN / CN)
that interleaves text-content markers with control codes in occurrence
order. Format:

    (1, 'FFFC', 1, 'FFFD', 1, 'FFFE')        # 3 text runs, with FFFC, FFFD, FFFE
    ('F702',)                                # voice-only, no text, no terminator
    (1, 'F600:0000', 1, 'FFFE')              # text, name marker w/ param, text, terminator

`1` = at least one non-control word of text content in that position.
`0` = explicitly empty between codes (rare).
Codes are uppercased hex; F600 carries its parameter word.

Usage:
    python3 tools/signature_compare.py <scen_num> [--show-all] [--show-diffs-only]
    python3 tools/signature_compare.py --summary
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00, parse_script_file

JP_D00 = PROJ / 'build' / 'd00_jp.dat'
CN_D00 = PROJ / 'data' / 'cn' / 'd00_cn.dat'
EN_DIR = PROJ / 'scripts' / 'en'

CTRL_RE = re.compile(r'<\$([0-9A-Fa-f]{4})>')


def _is_structural(w: int) -> bool:
    """Codes that appear in the signature.

    Excluded by design:
    - `<$FFFC>` (newline): line wrapping is language-dependent.
    - `<$F600>` (player-name token): inclusion depends on EN
      adaptation (narrations drop it for word wrap; dialogue may add
      or remove it). Not a structural invariant.
    """
    return (
        0xF700 <= w <= 0xF7FF
        or w == 0xFFFB
        or w == 0xFFFD
        or w == 0xFFFE
        or w == 0xFFFF
    )


def signature_from_bytes(b: bytes) -> tuple:
    """Build signature from raw entry bytes (JP/CN D00.DAT format)."""
    sig: list = []
    has_text = False
    i = 0
    while i < len(b) - 1:
        w = struct.unpack_from('>H', b, i)[0]
        i += 2
        if w == 0xF600:
            # Player-name token: skip parameter word; treat token as text.
            if i < len(b) - 1:
                i += 2
            has_text = True
        elif _is_structural(w):
            if has_text:
                sig.append(1); has_text = False
            sig.append(f'{w:04X}')
        else:
            has_text = True
    if has_text:
        sig.append(1)
    # Strip trailing FFFF padding: last-entry alignment artifact in JP
    # D00.DAT (text area is offset-bounded; leftover bytes after the
    # real FFFE terminator are filled with FFFF and have no engine
    # meaning). EN scripts don't need to replicate this.
    if len(sig) >= 2 and sig[-1] == 'FFFF' and sig[-2] == 'FFFE':
        sig = sig[:-1]
    return tuple(sig)


def signature_from_text(s: str) -> tuple:
    """Build signature from EN script text (with <$XXXX> notation)."""
    sig: list = []
    has_text = False
    last = 0
    matches = list(CTRL_RE.finditer(s))
    skip_next = False
    for idx, m in enumerate(matches):
        if skip_next:
            skip_next = False
            last = m.end()
            continue
        between = s[last:m.start()]
        if between.strip():
            has_text = True
        val = int(m.group(1), 16)
        if val == 0xF600:
            # Player-name token: skip following parameter; treat as text.
            if idx + 1 < len(matches):
                skip_next = True
            has_text = True
        elif _is_structural(val):
            if has_text:
                sig.append(1); has_text = False
            sig.append(f'{val:04X}')
        else:
            has_text = True
        last = m.end()
    after = s[last:]
    if after.strip():
        has_text = True
    if has_text:
        sig.append(1)
    # Strip trailing FFFF padding (mirror signature_from_bytes).
    if len(sig) >= 2 and sig[-1] == 'FFFF' and sig[-2] == 'FFFE':
        sig = sig[:-1]
    return tuple(sig)


def load_signatures(scen: int) -> dict[str, list[tuple]]:
    """Load JP/EN/CN signatures for one scen. Missing sides return empty list."""
    out: dict[str, list[tuple]] = {'JP': [], 'EN': [], 'CN': []}
    jp = parse_d00(JP_D00.read_bytes())
    out['JP'] = [signature_from_bytes(e) for e in jp[scen - 1].entries]
    if CN_D00.exists():
        cn = parse_d00(CN_D00.read_bytes())
        out['CN'] = [signature_from_bytes(e) for e in cn[scen - 1].entries]
    en_path = EN_DIR / f'scen{scen:03d}E.txt'
    if not en_path.exists():
        en_path = EN_DIR / f'scen{scen:03d}e.txt'
    if en_path.exists():
        out['EN'] = [signature_from_text(s) for s in parse_script_file(en_path)]
    return out


def _is_voice_only_jp(sig: tuple) -> bool:
    """JP voice-only entries have signature like ('F702',) — only F7xx codes,
    no terminator FFFE/FFFF, no text marker."""
    if not sig:
        return False
    for s in sig:
        if s == 1:
            return False
        if isinstance(s, str) and (s.startswith('FFFE') or s.startswith('FFFF')):
            return False
    return all(isinstance(s, str) and s.startswith('F7') for s in sig)


def compare_scen(scen: int, show_all: bool = False) -> dict:
    sigs = load_signatures(scen)
    n_jp = len(sigs['JP'])
    n_en = len(sigs['EN'])
    n_cn = len(sigs['CN'])

    rows = []
    counts = {'jp_eq_en': 0, 'jp_eq_cn': 0, 'en_eq_cn': 0, 'all_eq': 0,
              'jp_voiceonly': 0, 'jp_eq_en_with_carveout': 0}
    overlap = min(x for x in [n_jp, n_en, n_cn] if x > 0)

    for i in range(overlap):
        j = sigs['JP'][i] if i < n_jp else None
        e = sigs['EN'][i] if i < n_en else None
        c = sigs['CN'][i] if i < n_cn else None
        jp_voice = _is_voice_only_jp(j) if j else False
        if jp_voice:
            counts['jp_voiceonly'] += 1
        eq_je = (j == e) if (j is not None and e is not None) else None
        eq_jc = (j == c) if (j is not None and c is not None) else None
        eq_ec = (e == c) if (e is not None and c is not None) else None
        if eq_je: counts['jp_eq_en'] += 1
        if eq_jc: counts['jp_eq_cn'] += 1
        if eq_ec: counts['en_eq_cn'] += 1
        if eq_je and eq_jc: counts['all_eq'] += 1
        # JP voice-only entries: EN adds FFFE for the parser, so the
        # natural EN signature is (F7xx, FFFE) vs JP (F7xx,). Treat as
        # matching when JP is voice-only and EN signature == JP+('FFFE',).
        if eq_je or (jp_voice and e is not None
                     and e == tuple(list(j) + ['FFFE'])):
            counts['jp_eq_en_with_carveout'] += 1
        rows.append({
            'idx': i + 1,
            'jp': j, 'en': e, 'cn': c,
            'jp_voice': jp_voice,
            'eq_je': eq_je, 'eq_jc': eq_jc, 'eq_ec': eq_ec,
        })
    return {
        'scen': scen,
        'n_jp': n_jp, 'n_en': n_en, 'n_cn': n_cn,
        'overlap': overlap,
        'counts': counts,
        'rows': rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('scen', nargs='?', type=int)
    ap.add_argument('--show-all', action='store_true')
    ap.add_argument('--show-diffs', action='store_true', help='Only show entries where signatures differ')
    ap.add_argument('--summary', action='store_true', help='Project-wide summary')
    ap.add_argument('--dump-all', metavar='DIR',
                    help='Dump per-scen signature JSON for the whole project to DIR')
    args = ap.parse_args()

    if args.dump_all:
        import json
        out_dir = Path(args.dump_all)
        out_dir.mkdir(parents=True, exist_ok=True)
        scen_summaries = []
        for scen in range(1, 126):
            try:
                r = compare_scen(scen)
            except Exception as ex:
                print(f'scen{scen:03d}: ERR {ex}')
                continue
            payload = {
                'scen': scen,
                'n_jp': r['n_jp'], 'n_en': r['n_en'], 'n_cn': r['n_cn'],
                'counts': r['counts'],
                'entries': [
                    {
                        'idx': row['idx'],
                        'jp': list(row['jp']) if row['jp'] is not None else None,
                        'en': list(row['en']) if row['en'] is not None else None,
                        'cn': list(row['cn']) if row['cn'] is not None else None,
                        'jp_voice_only': row['jp_voice'],
                        'eq_je': row['eq_je'],
                        'eq_jc': row['eq_jc'],
                        'eq_ec': row['eq_ec'],
                    }
                    for row in r['rows']
                ],
            }
            (out_dir / f'scen{scen:03d}.json').write_text(
                json.dumps(payload, ensure_ascii=False, indent=1)
            )
            scen_summaries.append({
                'scen': scen,
                'overlap': r['overlap'],
                'jp_eq_en_strict': r['counts']['jp_eq_en'],
                'jp_eq_en_carve':  r['counts']['jp_eq_en_with_carveout'],
                'gap': r['overlap'] - r['counts']['jp_eq_en_with_carveout'],
                'voice_only': r['counts']['jp_voiceonly'],
                'jp_eq_cn': r['counts']['jp_eq_cn'],
            })
        (out_dir / 'index.json').write_text(
            json.dumps(scen_summaries, ensure_ascii=False, indent=1)
        )
        total_gap = sum(s['gap'] for s in scen_summaries)
        print(f'Dumped {len(scen_summaries)} scens to {out_dir}')
        print(f'Total JP↔EN gap (carve-out applied): {total_gap}')
        return

    if args.summary:
        print(f'{"scen":>5} {"N":>4} {"JP=EN":>6} {"+carve":>7} {"gap":>5} {"voice":>6} {"JP=CN":>6}')
        total_gap = 0
        for scen in range(1, 126):
            try:
                r = compare_scen(scen)
            except Exception as ex:
                print(f'{scen:>5}  ERR  {ex}')
                continue
            c = r['counts']; n = r['overlap']
            gap = n - c['jp_eq_en_with_carveout']
            total_gap += gap
            print(f'{scen:>5} {n:>4} {c["jp_eq_en"]:>6} '
                  f'{c["jp_eq_en_with_carveout"]:>7} {gap:>5} '
                  f'{c["jp_voiceonly"]:>6} {c["jp_eq_cn"]:>6}')
        print(f'\nTotal JP↔EN parity gap (after voice-only carve-out): {total_gap}')
        return

    if args.scen is None:
        ap.error('scen number required (or --summary)')

    r = compare_scen(args.scen)
    print(f'scen{args.scen:03d}: JP={r["n_jp"]} EN={r["n_en"]} CN={r["n_cn"]}')
    c = r['counts']
    print(f'  JP=EN (strict):                {c["jp_eq_en"]}/{r["overlap"]}')
    print(f'  JP=EN (with voice-only carve): {c["jp_eq_en_with_carveout"]}/{r["overlap"]}  ← parity metric')
    print(f'  JP=CN (analysis only):         {c["jp_eq_cn"]}/{r["overlap"]}')
    print(f'  JP voice-only entries:         {c["jp_voiceonly"]}')
    if args.show_all or args.show_diffs:
        print()
        for row in r['rows']:
            if args.show_diffs and row['eq_je'] and row['eq_jc'] and row['eq_ec']:
                continue
            mark = []
            if row['jp_voice']: mark.append('V')
            if row['eq_je'] is False: mark.append('JE')
            if row['eq_jc'] is False: mark.append('JC')
            if row['eq_ec'] is False: mark.append('EC')
            tag = ','.join(mark) if mark else 'ok'
            print(f'  [{row["idx"]:3d}] {tag:10s}')
            print(f'      JP: {row["jp"]}')
            print(f'      EN: {row["en"]}')
            print(f'      CN: {row["cn"]}')


if __name__ == '__main__':
    main()
