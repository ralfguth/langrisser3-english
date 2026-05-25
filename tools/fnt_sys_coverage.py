#!/usr/bin/env python3
"""
fnt_sys_coverage.py — Classify FNT_SYS records as translated vs JP-intact.

Compares JP-original and EN-patched FNT_SYS.BIN record by record. For each
of the 15 (offset, data) section pairs, splits the data into FFFF-terminated
records and produces a coverage report:

- TRANSLATED: EN bytes differ from JP bytes (CWX produced new content)
- JP_INTACT:  EN bytes identical to JP bytes (CWX did not translate;
              renders as mojibake in-game because EN font replaced JP glyphs)
- MISSING:    record exists in JP but EN section is shorter (entry dropped)
- EXTRA:      record exists in EN but JP section is shorter (CWX added)

Output: markdown report on stdout; CSV per-entry on --csv path.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from iso_tools import build_file_index, extract_file_data
from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP

JP_ISO = Path('/home/ralf/Jogos/emulacao/romsets/sega-saturn/cue-bin'
              '/Langrisser III (Japan)'
              '/Langrisser III (Japan) (3M) (Track 01).bin')
EN_ISO = PROJ / 'build' / 'track01.bin'
JP_TILE_MAP_PATH = Path('/home/ralf/Jogos/emulacao/tools/lang3_translation_analisis/jp_tile_map.json')

FNT_SYS_PAIRS = [
    (0, 1), (2, 3), (4, 5), (6, 7), (8, 9),
    (10, 11), (12, 13), (14, 15), (16, 17), (18, 19),
    (20, 21), (22, 23), (24, 25), (26, 27), (29, 30),
]


def load_fnt_sys(iso_path: Path) -> bytes:
    img = iso_path.read_bytes()
    idx = build_file_index(img)
    e = idx['LANG/FNT_SYS.BIN']
    return extract_file_data(img, e.extent, e.size)


def section_bounds(data: bytes) -> list[tuple[int, int]]:
    pointers = list(struct.unpack('>31I', data[:124]))
    bounds = []
    off = 0x7C
    for i, ptr in enumerate(pointers):
        nxt = pointers[i + 1] if i + 1 < len(pointers) else None
        length = (len(data) - off) if nxt is None else (nxt - ptr)
        bounds.append((off, length))
        off += length
    return bounds


def split_records(section_bytes: bytes, count: int) -> list[bytes]:
    records = []
    cur = bytearray()
    i = 0
    while i < len(section_bytes) - 1 and len(records) < count:
        word = struct.unpack_from('>H', section_bytes, i)[0]
        i += 2
        cur.extend(struct.pack('>H', word))
        if word == 0xFFFF:
            records.append(bytes(cur))
            cur = bytearray()
    return records


def decode(rec: bytes, tile_map: dict[int, str]) -> str:
    parts: list[str] = []
    i = 0
    while i < len(rec) - 1:
        w = struct.unpack_from('>H', rec, i)[0]
        i += 2
        if w >= 0xF000:
            parts.append(f'<${w:04X}>')
            if w == 0xF600 and i < len(rec) - 1:
                p = struct.unpack_from('>H', rec, i)[0]
                parts.append(f'<${p:04X}>')
                i += 2
        else:
            parts.append(tile_map.get(w, f'<${w:04X}>'))
    return ''.join(parts)


def build_en_tile_map() -> dict[int, str]:
    m: dict[int, str] = {}
    for ch, idx in CHAR_TILE_MAP.items():
        m[idx] = ch
    for (l, r), idx in BIGRAM_TILE_MAP.items():
        m[idx] = l + r
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--csv', type=Path, help='per-entry CSV output')
    ap.add_argument('--md', type=Path, help='markdown report output (default: stdout)')
    args = ap.parse_args()

    jp_fnt = load_fnt_sys(JP_ISO)
    en_fnt = load_fnt_sys(EN_ISO)
    jp_bounds = section_bounds(jp_fnt)
    en_bounds = section_bounds(en_fnt)

    jp_tile_map = {int(k): v for k, v in json.loads(JP_TILE_MAP_PATH.read_text()).items()}
    en_tile_map = build_en_tile_map()

    md_lines: list[str] = []
    csv_rows: list[dict] = []
    md_lines.append('# FNT_SYS Translation Coverage\n')
    md_lines.append(f'JP source: {JP_ISO.name}  ')
    md_lines.append(f'EN source: {EN_ISO.relative_to(PROJ)}  ')
    md_lines.append('Method: byte-equality per FFFF-terminated record.\n')
    md_lines.append('| File | JP entries | EN entries | Translated | JP_INTACT | Coverage |')
    md_lines.append('|------|-----------:|-----------:|-----------:|----------:|---------:|')

    totals = {'jp': 0, 'en': 0, 'translated': 0, 'jp_intact': 0}

    for pair_idx, (oi, di) in enumerate(FNT_SYS_PAIRS, start=1):
        jp_off_off, jp_off_len = jp_bounds[oi]
        en_off_off, en_off_len = en_bounds[oi]
        jp_count = jp_off_len // 2
        en_count = en_off_len // 2

        jp_off, jp_len = jp_bounds[di]
        en_off, en_len = en_bounds[di]
        jp_records = split_records(jp_fnt[jp_off:jp_off + jp_len], jp_count)
        en_records = split_records(en_fnt[en_off:en_off + en_len], en_count)

        translated = 0
        jp_intact = 0
        common = min(len(jp_records), len(en_records))
        for i in range(common):
            jp_rec = jp_records[i]
            en_rec = en_records[i]
            status = 'TRANSLATED' if jp_rec != en_rec else 'JP_INTACT'
            if status == 'TRANSLATED':
                translated += 1
            else:
                jp_intact += 1
            csv_rows.append({
                'file': f'fntsys{pair_idx}',
                'entry': i + 1,
                'status': status,
                'jp_text': decode(jp_rec, jp_tile_map).replace('\n', '\\n'),
                'en_text': decode(en_rec, en_tile_map).replace('\n', '\\n'),
            })
        # Missing or extra
        for i in range(len(en_records), len(jp_records)):
            csv_rows.append({
                'file': f'fntsys{pair_idx}',
                'entry': i + 1,
                'status': 'MISSING',
                'jp_text': decode(jp_records[i], jp_tile_map).replace('\n', '\\n'),
                'en_text': '',
            })
        for i in range(len(jp_records), len(en_records)):
            csv_rows.append({
                'file': f'fntsys{pair_idx}',
                'entry': i + 1,
                'status': 'EXTRA',
                'jp_text': '',
                'en_text': decode(en_records[i], en_tile_map).replace('\n', '\\n'),
            })

        cov = translated / common * 100 if common else 0.0
        md_lines.append(
            f'| fntsys{pair_idx} | {len(jp_records)} | {len(en_records)} | '
            f'{translated} | {jp_intact} | {cov:.1f}% |'
        )
        totals['jp'] += len(jp_records)
        totals['en'] += len(en_records)
        totals['translated'] += translated
        totals['jp_intact'] += jp_intact

    overall_cov = totals['translated'] / max(1, totals['translated'] + totals['jp_intact']) * 100
    md_lines.append(
        f'| **TOTAL** | **{totals["jp"]}** | **{totals["en"]}** | '
        f'**{totals["translated"]}** | **{totals["jp_intact"]}** | **{overall_cov:.1f}%** |\n'
    )

    md_lines.append('## Reading this report\n')
    md_lines.append('- **JP entries** = number of FFFF-terminated records in the JP binary.')
    md_lines.append('- **EN entries** = same count in the EN-patched binary. A mismatch means CWX dropped or added records.')
    md_lines.append('- **Translated** = EN record bytes differ from the JP record bytes — CWX produced new content.')
    md_lines.append('- **JP_INTACT** = EN record bytes are byte-identical to JP. These render as mojibake in-game because')
    md_lines.append('  the EN font has different glyphs at the same tile IDs. These are what still needs translation work.')
    md_lines.append('- **Coverage** = Translated / (Translated + JP_INTACT). Excludes MISSING/EXTRA.\n')

    output = '\n'.join(md_lines)
    if args.md:
        args.md.write_text(output, encoding='utf-8')
        print(f'Wrote {args.md}')
    else:
        print(output)

    if args.csv:
        with args.csv.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=['file', 'entry', 'status', 'jp_text', 'en_text'])
            w.writeheader()
            w.writerows(csv_rows)
        print(f'Wrote {args.csv}  ({len(csv_rows)} rows)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
