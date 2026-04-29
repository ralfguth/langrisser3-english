#!/usr/bin/env python3
"""migrate_cwx_bins.py — word-level tile-ID migration for CWX binaries.

Applies safe 2-byte-to-2-byte tile-ID substitutions across all patches/*.bin:
  - Diacritic removal: Jü→Ju, gü→gu, mü→mu, Jä→Ja, jä→ja, äl→al, öl→ol
  - Canonical alignment: tile 1613 (CWX-custom "Bo") → canonical (B,o)
                         tile 1614 (CWX-custom "os") → canonical (o,s)

Each substitution is same-size (1 word → 1 word), so no byte count changes.
No pointer tables need updates. No sector-shift required.

Outputs a preview diff before writing. Use --apply to write changes.
"""
import argparse
import struct
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJ = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from font_tools import BIGRAM_TILE_MAP

PATCHES_DIR = PROJ / 'patches'

# Mapping: CWX custom tile -> canonical tile with same/equivalent rendering
# (diacritic removal where applicable)
TILE_MIGRATION = {
    1506: (BIGRAM_TILE_MAP[('J', 'u')], 'Jü→Ju'),   # 1169
    1507: (BIGRAM_TILE_MAP[('m', 'u')], 'mü→mu'),   # 488
    1508: (BIGRAM_TILE_MAP[('g', 'u')], 'gü→gu'),   # 266
    1533: (BIGRAM_TILE_MAP[('J', 'a')], 'Jä→Ja'),   # 1149
    1534: (BIGRAM_TILE_MAP[('j', 'a')], 'jä→ja'),   # 375
    1535: (BIGRAM_TILE_MAP[('a', 'l')], 'äl→al'),   # 58
    1536: (BIGRAM_TILE_MAP[('o', 'l')], 'öl→ol'),   # 543
    1613: (BIGRAM_TILE_MAP[('B', 'o')], 'Bo→Bo (canonical)'),  # 955
    1614: (BIGRAM_TILE_MAP[('o', 's')], 'os→os (canonical)'),  # 550
}


def migrate_binary(data: bytes) -> tuple:
    """Apply tile migrations to a binary's words. Returns (new_bytes, diff_list).

    diff_list: list of (offset, old_tile, new_tile, label).
    """
    result = bytearray(data)
    diffs = []
    for i in range(0, len(data) - 1, 2):
        word = struct.unpack_from('>H', data, i)[0]
        if word in TILE_MIGRATION:
            new_tile, label = TILE_MIGRATION[word]
            struct.pack_into('>H', result, i, new_tile)
            diffs.append((i, word, new_tile, label))
    return bytes(result), diffs


def main():
    parser = argparse.ArgumentParser(description='Migrate CWX binaries to canonical tile-IDs')
    parser.add_argument('--apply', action='store_true',
                        help='Write changes (default: preview only)')
    parser.add_argument('--file', type=str, default=None,
                        help='Only migrate this single binary filename')
    args = parser.parse_args()

    bins = [args.file] if args.file else sorted(p.name for p in PATCHES_DIR.glob('*.bin'))

    total_changes = 0
    per_file_diffs = {}

    for fname in bins:
        path = PATCHES_DIR / fname
        if not path.exists():
            print(f'SKIP {fname} (not found)')
            continue
        data = path.read_bytes()
        new_data, diffs = migrate_binary(data)
        per_file_diffs[fname] = diffs
        if not diffs:
            print(f'{fname}: no migrations needed')
            continue
        total_changes += len(diffs)
        print(f'\n=== {fname}: {len(diffs)} migration{"s" if len(diffs)!=1 else ""} ===')
        # Group diffs by migration label for summary
        from collections import Counter
        by_label = Counter((d[1], d[3]) for d in diffs)
        for (old_tile, label), count in sorted(by_label.items()):
            new_tile = TILE_MIGRATION[old_tile][0]
            print(f'  {label:<25} tile {old_tile:>4} → {new_tile:<4}  ({count}x)')
        # Show first 5 offsets
        for off, old_t, new_t, lbl in diffs[:5]:
            print(f'    0x{off:06X}: {old_t:04X} → {new_t:04X}')
        if len(diffs) > 5:
            print(f'    ... (+{len(diffs) - 5} more)')
        if args.apply:
            path.write_bytes(new_data)
            print(f'  → written to {path}')

    print(f'\n{"="*60}')
    print(f'Total: {total_changes} word substitutions across {len(per_file_diffs)} files')
    if not args.apply:
        print('Preview only. Re-run with --apply to write changes.')


if __name__ == '__main__':
    main()
