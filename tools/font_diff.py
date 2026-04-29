#!/usr/bin/env python3
"""font_diff.py - Diff canonical (generated) font vs CWX and VD fonts.

Identifies tile positions where the glyph differs, i.e. where a CWX-era
binary referencing a given tile-ID will render a DIFFERENT character than
what the current canonical pipeline would encode for that same tile-ID.

Output: list of divergent tile indices with ASCII-art visualization of both
glyphs side by side, to help spot bigram mismatches.
"""
import struct
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJ = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from iso_tools import build_file_index, extract_file_data
from font_tools import generate_english_font, TILE_CHAR_MAP, BIGRAM_TILE_MAP

JP_TRACK01 = Path.home() / 'Jogos/emulacao/romsets/sega-saturn/cue-bin/Langrisser III (Japan)/Langrisser III (Japan) (3M) (Track 01).bin'
CWX_FONT = PROJ / 'archive' / 'unused_patches' / 'cwx_font.bin'
VD_FONT = PROJ / 'archive' / 'unused_patches' / 'vd_font.bin'

TILE_SIZE = 32


def tile_to_ascii(data: bytes) -> list:
    rows = []
    for row in range(16):
        word = (data[row * 2] << 8) | data[row * 2 + 1]
        line = ''
        for col in range(16):
            line += '#' if word & (1 << (15 - col)) else '.'
        rows.append(line[:8] + '|' + line[8:])
    return rows


def describe_tile(idx: int) -> str:
    """Human-readable label for a tile index using canonical maps."""
    if idx in TILE_CHAR_MAP:
        c = TILE_CHAR_MAP[idx]
        return repr(c)
    # find bigram
    for pair, i in BIGRAM_TILE_MAP.items():
        if i == idx:
            return repr(pair[0] + pair[1])
    return '(unmapped)'


def diff_fonts(font_a: bytes, font_b: bytes, label_a: str, label_b: str):
    assert len(font_a) == len(font_b), f'{label_a}={len(font_a)} vs {label_b}={len(font_b)}'
    total_tiles = len(font_a) // TILE_SIZE
    divergent = []
    for i in range(total_tiles):
        a = font_a[i * TILE_SIZE:(i + 1) * TILE_SIZE]
        b = font_b[i * TILE_SIZE:(i + 1) * TILE_SIZE]
        if a != b:
            divergent.append(i)
    print(f'\n=== {label_a} vs {label_b} ===')
    print(f'Total tiles: {total_tiles}, divergent: {len(divergent)} ({len(divergent)*100//total_tiles}%)')
    return divergent


def visualize_divergence(idx: int, font_a: bytes, font_b: bytes,
                          label_a: str, label_b: str) -> str:
    a = font_a[idx * TILE_SIZE:(idx + 1) * TILE_SIZE]
    b = font_b[idx * TILE_SIZE:(idx + 1) * TILE_SIZE]
    rows_a = tile_to_ascii(a)
    rows_b = tile_to_ascii(b)
    lines = [f'Tile {idx} [canon={describe_tile(idx)}]    {label_a:>12}   |   {label_b:>12}']
    for ra, rb in zip(rows_a, rows_b):
        lines.append(f'  {ra}   {rb}')
    return '\n'.join(lines)


def main():
    # Extract JP FONT.BIN from ISO
    if not JP_TRACK01.exists():
        print(f'ERROR: JP Track 01 not found at {JP_TRACK01}')
        return 1
    image = JP_TRACK01.read_bytes()
    file_index = build_file_index(image)
    font_entry = file_index.get('LANG/FONT.BIN')
    if not font_entry:
        print('ERROR: LANG/FONT.BIN not in ISO')
        return 1
    jp_font = extract_file_data(image, font_entry.extent, font_entry.size)
    print(f'JP FONT.BIN extracted: {len(jp_font)} bytes ({len(jp_font)//TILE_SIZE} tiles)')

    # Generate canonical
    canon = generate_english_font(jp_font)
    print(f'Canonical font generated: {len(canon)} bytes')

    # Load CWX and VD
    cwx = CWX_FONT.read_bytes() if CWX_FONT.exists() else None
    vd = VD_FONT.read_bytes() if VD_FONT.exists() else None

    # Summary diffs
    divergent_vs_cwx = diff_fonts(canon, cwx, 'canon', 'cwx') if cwx else []
    divergent_vs_vd = diff_fonts(canon, vd, 'canon', 'vd') if vd else []
    divergent_cwx_vs_vd = diff_fonts(cwx, vd, 'cwx', 'vd') if (cwx and vd) else []

    # Categorize CWX divergences by tile zone
    print()
    print('CWX divergences by zone:')
    zones = [
        (0, 46, 'standalone punctuation/digits/UC'),
        (46, 906, 'LC bigrams'),
        (906, 914, 'ellipsis + punct bigrams'),
        (914, 1435, 'UC bigrams'),
        (1435, 1500, 'space+letter + apostrophe'),
        (1500, 1621, 'CWX menu tiles'),
        (1621, 1630, 'custom apostrophe bigrams'),
        (1630, 1691, 'kanji area'),
    ]
    for start, end, label in zones:
        in_zone = [i for i in divergent_vs_cwx if start <= i < end]
        print(f'  [{start:>4}-{end:>4}] {label}: {len(in_zone)} divergent')

    # Write out detailed report
    out = PROJ / 'build' / 'font_diff_report.txt'
    out.parent.mkdir(exist_ok=True)
    with open(out, 'w') as f:
        f.write(f'# Font Diff Report\n')
        f.write(f'Generated: canon vs patches/cwx_font.bin vs patches/vd_font.bin\n\n')
        f.write(f'Canon vs CWX: {len(divergent_vs_cwx)} divergent tiles\n')
        f.write(f'Canon vs VD:  {len(divergent_vs_vd)} divergent tiles\n')
        f.write(f'CWX vs VD:    {len(divergent_cwx_vs_vd)} divergent tiles\n\n')
        f.write(f'## Canon vs CWX — divergent tile indices\n')
        f.write(', '.join(str(i) for i in divergent_vs_cwx) + '\n\n')
        f.write(f'## Per-tile visualization (canon vs cwx), first 50\n\n')
        for i in divergent_vs_cwx[:50]:
            f.write(visualize_divergence(i, canon, cwx, 'canon', 'cwx'))
            f.write('\n\n')
    print(f'\nReport written to {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
