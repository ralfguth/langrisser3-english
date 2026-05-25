#!/usr/bin/env python3
"""
dump_en_scripts.py — Dump decoded EN scripts from the patched ISO.

Mirrors ``dump_jp_scripts.py`` but reads the EN-patched ISO at
``build/track01.bin`` and decodes tile codes with the EN tile maps from
``font_tools`` (CHAR_TILE_MAP ⊕ BIGRAM_TILE_MAP), inverted.

Sources (extracted live from ``build/track01.bin``):

- ``LANG/SCEN/D00.DAT`` → ``scenNNN.txt`` (125 dialogue scenarios)
- ``LANG/PLOT.DAT``     → ``plot.txt``    (35 chapter recap blocks)
- ``LANG/FNT_SYS.BIN``  → ``fntsysN.txt`` (15 menu/UI string tables)

Default output: ``scripts/wip/``.

Usage::

    python3 tools/dump_en_scripts.py                # all three artifacts
    python3 tools/dump_en_scripts.py --only d00
    python3 tools/dump_en_scripts.py --only fntsys
    python3 tools/dump_en_scripts.py scen042        # one D00 scenario

The output of this tool is *ground truth*: what's actually inside the
shipped patched ISO. Compare against ``scripts/en/`` to measure drift
between the script tree and the live binaries (notably for
``fntsys*E.txt`` which are stale historical snapshots).
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00
from iso_tools import build_file_index, extract_file_data
from plot_tools import parse_plot
from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP

PATCHED_ISO = PROJ / 'build' / 'track01.bin'
DEFAULT_OUT = Path('/home/ralf/romhack/lang3_english_translation_project/scripts/wip')

# Files inside the patched ISO
ISO_D00 = 'LANG/SCEN/D00.DAT'
ISO_PLOT = 'LANG/PLOT.DAT'
ISO_FNT_SYS = 'LANG/FNT_SYS.BIN'

HEADER = ''

# Same 15 (offset, data) section pairs as the JP layout. CWX's binary
# patch preserves the FNT_SYS layout, so the same pair indices apply.
FNT_SYS_PAIRS = [
    (0, 1), (2, 3), (4, 5), (6, 7), (8, 9),
    (10, 11), (12, 13), (14, 15), (16, 17), (18, 19),
    (20, 21), (22, 23), (24, 25), (26, 27), (29, 30),
]


def build_tile_decode_map() -> dict[int, str]:
    """Build tile_index → string map for the EN tile system.

    Bigrams (2-char strings) take precedence — most game text is
    encoded via bigram tiles. Singles fill in the gaps (digits,
    uppercase, punctuation, lowercase-as-trailing-space).

    Where a tile is both a single in CHAR_TILE_MAP AND a bigram in
    BIGRAM_TILE_MAP (e.g. lowercase 'a' = (a, ' ') bigram), the bigram
    form wins — that's the faithful representation of the bytes; we
    let post-processing decide if to trim the trailing space.
    """
    m: dict[int, str] = {}
    # Singles first
    for ch, idx in CHAR_TILE_MAP.items():
        m[idx] = ch
    # Bigrams override singles where applicable
    for (l, r), idx in BIGRAM_TILE_MAP.items():
        m[idx] = l + r
    return m


def decode_entry(entry_bytes: bytes, tile_map: dict[int, str]) -> str:
    """Decode raw bytes to an EN text string with control codes as ``<$XXXX>``.

    F600 carries a parameter word, also emitted as ``<$XXXX>``.
    Unknown tiles fall back to ``<$XXXX>`` — those are tiles outside
    our CHAR/BIGRAM maps (potentially CWX-installed custom glyphs).
    """
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
        else:
            parts.append(tile_map.get(word, f'<${word:04X}>'))
    return ''.join(parts)


def _load_patched_iso() -> bytes:
    if not PATCHED_ISO.exists():
        raise FileNotFoundError(
            f'patched ISO not found at {PATCHED_ISO} — run build.py first'
        )
    return PATCHED_ISO.read_bytes()


def _extract(img: bytes, name: str) -> bytes:
    idx = build_file_index(img)
    e = idx.get(name)
    if not e:
        raise RuntimeError(f'{name} missing from patched ISO')
    return extract_file_data(img, e.extent, e.size)


# ---------------------------------------------------------------------------
# D00.DAT (125 scenario scripts)
# ---------------------------------------------------------------------------

def dump_d00(out_dir: Path, tile_map: dict[int, str], img: bytes,
             only_scen: list[int] | None = None) -> int:
    data = _extract(img, ISO_D00)
    sections = parse_d00(data)
    nums = only_scen if only_scen else list(range(1, len(sections) + 1))
    written = 0
    for n in nums:
        if not (1 <= n <= len(sections)):
            print(f'WARN: scen{n:03d} out of range', file=sys.stderr)
            continue
        section = sections[n - 1]
        lines = [HEADER]
        for entry_bytes in section.entries:
            decoded = decode_entry(entry_bytes, tile_map)
            if not (decoded.endswith('<$FFFE>') or decoded.endswith('<$FFFF>')):
                decoded += '<$FFFE>'
            lines.append(decoded + '\n')
        out_path = out_dir / f'scen{n:03d}.txt'
        out_path.write_text(''.join(lines), encoding='utf-8')
        print(f'  wrote {out_path.name}  ({section.entry_count} entries)')
        written += 1
    return written


# ---------------------------------------------------------------------------
# PLOT.DAT (35 chapter recap blocks)
# ---------------------------------------------------------------------------

def _decode_plot_block(raw: bytes, tile_map: dict[int, str]) -> str:
    if len(raw) < 4:
        return ''
    marker, block_id = struct.unpack('>HH', raw[:4])
    parts = [f'<${marker:04X}{block_id:04X}>']
    parts.append(decode_entry(raw[4:], tile_map))
    return ''.join(parts)


def dump_plot(out_dir: Path, tile_map: dict[int, str], img: bytes) -> int:
    data = _extract(img, ISO_PLOT)
    blocks = parse_plot(data)
    lines = [HEADER]
    for block in blocks:
        lines.append(_decode_plot_block(block.raw_bytes, tile_map) + '\n')
    out_path = out_dir / 'plot.txt'
    out_path.write_text(''.join(lines), encoding='utf-8')
    print(f'  wrote {out_path.name}  ({len(blocks)} blocks)')
    return 1


# ---------------------------------------------------------------------------
# FNT_SYS.BIN (15 menu/UI string tables)
# ---------------------------------------------------------------------------

def _fnt_sys_section_bounds(data: bytes) -> list[tuple[int, int]]:
    pointers = list(struct.unpack('>31I', data[:124]))
    bounds = []
    base_file_off = 0x7C
    for i, ptr in enumerate(pointers):
        next_ptr = pointers[i + 1] if i + 1 < len(pointers) else None
        if next_ptr is None:
            length = len(data) - base_file_off
        else:
            length = next_ptr - ptr
        bounds.append((base_file_off, length))
        base_file_off += length
    return bounds


def _split_fnt_sys_records(section_bytes: bytes, count: int) -> list[bytes]:
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


def dump_fntsys(out_dir: Path, tile_map: dict[int, str], img: bytes) -> int:
    data = _extract(img, ISO_FNT_SYS)
    bounds = _fnt_sys_section_bounds(data)
    written = 0
    for pair_idx, (off_sec_idx, data_sec_idx) in enumerate(FNT_SYS_PAIRS, start=1):
        _, off_length = bounds[off_sec_idx]
        record_count = off_length // 2
        off, length = bounds[data_sec_idx]
        section_bytes = data[off:off + length]
        records = _split_fnt_sys_records(section_bytes, record_count)
        lines = [HEADER]
        for rec in records:
            lines.append(decode_entry(rec, tile_map) + '\n')
        out_path = out_dir / f'fntsys{pair_idx}.txt'
        out_path.write_text(''.join(lines), encoding='utf-8')
        print(f'  wrote {out_path.name}  ({len(records)} entries)')
        written += 1
    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('scenarios', nargs='*',
                    help='scen001 … scen125 (D00 only; omit for all)')
    ap.add_argument('--out', type=Path, default=DEFAULT_OUT,
                    help=f'output directory (default: {DEFAULT_OUT})')
    ap.add_argument('--only', choices=('d00', 'plot', 'fntsys'),
                    help='restrict to one artifact (default: all three)')
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    tile_map = build_tile_decode_map()
    img = _load_patched_iso()
    print(f'Loaded patched ISO: {PATCHED_ISO.name} ({len(img):,} bytes)')

    if args.scenarios:
        only_scen = [int(s.replace('scen', '').lstrip('0') or '0')
                     for s in args.scenarios]
        if args.only and args.only != 'd00':
            print('ERROR: cannot combine positional scenarios with --only != d00',
                  file=sys.stderr)
            return 1
        args.only = 'd00'
    else:
        only_scen = None

    total = 0
    if args.only in (None, 'd00'):
        total += dump_d00(args.out, tile_map, img, only_scen)
    if args.only in (None, 'plot'):
        total += dump_plot(args.out, tile_map, img)
    if args.only in (None, 'fntsys'):
        total += dump_fntsys(args.out, tile_map, img)

    print(f'Wrote {total} EN script files to {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
