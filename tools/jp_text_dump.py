#!/usr/bin/env python3
"""jp_text_dump.py — extract JP text tables from each PROG_*.BIN / SYSWIN.BIN.

Two modes:
  1. KNOWN — dump pre-identified tables (skill, magic, magic-icon, stat, ...)
     into per-table files under scripts/jp/<table>_JP.txt. Each line shows:
       slot_idx | file_offset | hex_bytes | JIS-X-0201-decode

  2. SCAN — find candidate string-table regions (runs of high bytes
     0x80..0xDF + null-padding) NOT covered by any existing overlay or
     known table. Output to scripts/jp/_scan_<binary>.txt.

The point is to capture every byte that the engine may render as text,
so we can translate each and locate the renderer (and thus the font)
afterwards via Ghidra cross-reference.

Usage:
    python3 tools/jp_text_dump.py        # both modes, default ranges
    python3 tools/jp_text_dump.py --known
    python3 tools/jp_text_dump.py --scan

JP encoding notes (this game uses a mixed single-byte custom encoding):
  - 0x20..0x7E : ASCII printable (used for stat names "EXP", "HP", ...).
  - 0x80..0x9F : appears as first byte of multibyte clusters; specific
                 meaning per renderer (kanji / custom tile indices /
                 SJIS-like). Decoded as <XX> in dumps.
  - 0xA1..0xDF : JIS X 0201 half-width katakana (single-byte). Decoded.
  - 0x00       : terminator / padding.

Output files are READ-ONLY documentation. The translation step writes
to scripts/en/<table>E.txt and is wired by tools/prog_text_tools.py.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from iso_tools import build_file_index, extract_file_data  # noqa: E402

JP_DIR_ENV = 'LANG3_JP_DIR'
SCRIPTS_JP_DIR = PROJ / 'scripts' / 'jp'

# ---------------------------------------------------------------------------
# Known text tables. Each: ISO path, table base, slot stride, slot count,
# name width (bytes considered as text; remaining bytes per stride are
# metadata).  When stride == name_width the table has no per-slot metadata
# tail.
# ---------------------------------------------------------------------------
KNOWN_TABLES = [
    # (key,                iso_path,                 base,    stride, name_width, count)
    ('prog3_magic',        'LANG/PROG_3.BIN',        0x3394C, 0x14,   12,         55),
    ('prog3_skill',        'LANG/PROG_3.BIN',        0x3314C, 0x0C,   12,         9),
    ('prog4_magic_icon',   'LANG/PROG_4.BIN',        0x7F80,  0x00,   0,          0),   # variable
    ('prog4_stat_name',    'LANG/PROG_4.BIN',        0x7F40,  0x00,   0,          0),   # variable
]


def decode_byte(b: int) -> str:
    """Single-character decode for hex-dump readability."""
    if b == 0:
        return '.'
    if 0x20 <= b < 0x7F:
        return chr(b)
    if 0xA1 <= b <= 0xDF:
        try:
            return bytes([b]).decode('shift_jis')
        except UnicodeDecodeError:
            return '?'
    return f'<{b:02X}>'


def decode_run(buf: bytes) -> str:
    return ''.join(decode_byte(b) for b in buf)


def dump_fixed_table(data: bytes, base: int, stride: int, name_width: int,
                     count: int) -> str:
    """Render a fixed-stride table. Returns a multi-line string."""
    out = []
    out.append(f'# fixed-stride table @ 0x{base:05X} '
               f'stride=0x{stride:X} name_width={name_width} count={count}')
    out.append('')
    for i in range(count):
        off = base + i * stride
        slot = data[off:off + stride]
        name_bytes = slot[:name_width]
        meta = slot[name_width:]
        hexn = name_bytes.hex()
        text = decode_run(name_bytes)
        line = f'{i:3d}  0x{off:05X}  {hexn:<24s}  {text}'
        if meta:
            line += f'  | meta {meta.hex()}'
        out.append(line)
    return '\n'.join(out) + '\n'


def dump_variable_region(data: bytes, base: int, length: int = 0x200) -> str:
    """Hex dump of a region of unknown structure, with text glosses."""
    out = []
    out.append(f'# variable-structure region @ 0x{base:05X} length=0x{length:X}')
    out.append('')
    for off in range(base, base + length, 16):
        row = data[off:off + 16]
        if not row:
            break
        h = ' '.join(f'{b:02X}' for b in row)
        text = decode_run(row)
        out.append(f'0x{off:05X}  {h:<47s}  {text}')
    return '\n'.join(out) + '\n'


def find_text_runs(data: bytes, exclude: set[int], min_len: int = 5) -> list[tuple[int, bytes]]:
    """Find runs of length >= min_len of bytes in 0x80..0xDF that aren't
    covered by `exclude` (file offsets). Returns [(offset, bytes)]."""
    runs = []
    i = 0
    n = len(data)
    while i < n:
        if (0x80 <= data[i] <= 0xDF) and i not in exclude:
            j = i
            while j < n and (0x80 <= data[j] <= 0xDF) and j not in exclude:
                j += 1
            if j - i >= min_len:
                runs.append((i, data[i:j]))
            i = j
        else:
            i += 1
    return runs


def load_overlays() -> dict[str, set[int]]:
    """For each ISO path, set of file offsets already covered by static
    or encoded overlays — so the scan can exclude them."""
    from byte_overlays import BYTE_OVERLAYS
    try:
        from prog_text_tools import encoded_overlays
        enc = encoded_overlays()
    except Exception:
        enc = {}
    out: dict[str, set[int]] = {}
    for iso_path, edits in {**BYTE_OVERLAYS, **enc}.items():
        covered = out.setdefault(iso_path, set())
        full = list(BYTE_OVERLAYS.get(iso_path, [])) + list(enc.get(iso_path, []))
        for off, chunk in full:
            if isinstance(chunk, int):
                chunk = bytes([chunk])
            for j in range(len(chunk)):
                covered.add(off + j)
    return out


def get_jp_image() -> bytes:
    jp_dir = os.environ.get(JP_DIR_ENV)
    if not jp_dir:
        sys.exit(f'ERROR: {JP_DIR_ENV} not set')
    cands = list(Path(jp_dir).glob('*rack*01*.bin'))
    if not cands:
        sys.exit(f'ERROR: no Track 01 .bin in {jp_dir}')
    return cands[0].read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--known', action='store_true', help='dump only known tables')
    parser.add_argument('--scan',  action='store_true', help='only run automatic scan')
    args = parser.parse_args()
    do_known = args.known or not (args.known or args.scan)
    do_scan = args.scan or not (args.known or args.scan)

    SCRIPTS_JP_DIR.mkdir(parents=True, exist_ok=True)
    img = get_jp_image()
    idx = build_file_index(img)
    overlays = load_overlays()

    if do_known:
        for key, iso_path, base, stride, name_width, count in KNOWN_TABLES:
            entry = idx.get(iso_path)
            if not entry:
                print(f'SKIP {key}: {iso_path} not in ISO')
                continue
            data = extract_file_data(img, entry.extent, entry.size)
            if count > 0 and stride > 0:
                body = dump_fixed_table(data, base, stride, name_width, count)
            else:
                body = dump_variable_region(data, base, 0x200)
            out_path = SCRIPTS_JP_DIR / f'{key}_JP.txt'
            out_path.write_text(body, encoding='utf-8')
            print(f'wrote {out_path.relative_to(PROJ)} ({len(body)} bytes)')

    if do_scan:
        targets = [
            ('a0lang',  'A0LANG.BIN'),
            ('prog_3',  'LANG/PROG_3.BIN'),
            ('prog_4',  'LANG/PROG_4.BIN'),
            ('prog_5',  'LANG/PROG_5.BIN'),
            ('prog_6',  'LANG/PROG_6.BIN'),
            ('syswin',  'LANG/BATTLE/SYSWIN.BIN'),
        ]
        for short, iso_path in targets:
            entry = idx.get(iso_path)
            if not entry:
                print(f'SKIP {short}: {iso_path} not in ISO')
                continue
            data = extract_file_data(img, entry.extent, entry.size)
            covered = overlays.get(iso_path, set())
            runs = find_text_runs(data, covered, min_len=4)
            out_path = SCRIPTS_JP_DIR / f'_scan_{short}_JP.txt'
            lines = [
                f'# automatic scan of {iso_path} ({len(data)} bytes)',
                f'# runs of >=4 consecutive bytes in 0x80..0xDF not covered by current overlays',
                f'# {len(runs)} runs total',
                '',
            ]
            for off, run in runs:
                lines.append(f'0x{off:05X}  len={len(run):3d}  {run.hex()}  {decode_run(run)}')
            body = '\n'.join(lines) + '\n'
            out_path.write_text(body, encoding='utf-8')
            print(f'wrote {out_path.relative_to(PROJ)} ({len(runs)} runs)')


if __name__ == '__main__':
    main()
