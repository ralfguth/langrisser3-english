#!/usr/bin/env python3
"""
dump_jp_scripts.py — Dump decoded JP scripts (D00, PLOT, FNT_SYS) to .txt files.

Reads JP binaries and decodes each entry's tile codes using the JP tile
map, writing one Akari-Dawn-style script file per artifact to
``scripts/jp/`` at a configurable output root:

- D00.DAT scenarios → ``scenNNNJ.txt`` (125 files)
- PLOT.DAT          → ``plotJ.txt``    (35 chapter recap blocks)
- FNT_SYS.BIN       → ``fntsysNJ.txt`` (15 menu/UI string tables)

D00 source: ``build/d00_jp.dat``. PLOT source: ``build/plot_jp.dat``.
FNT_SYS source: extracted from the JP ISO at
``~/Jogos/emulacao/romsets/sega-saturn/cue-bin/Langrisser III (Japan)/``
(also cached to ``build/fnt_sys_jp.bin``).

Usage::

    python3 tools/dump_jp_scripts.py                # all three artifacts
    python3 tools/dump_jp_scripts.py --only d00     # only D00 scenarios
    python3 tools/dump_jp_scripts.py --only plot
    python3 tools/dump_jp_scripts.py --only fntsys
    python3 tools/dump_jp_scripts.py scen042        # one D00 scenario
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from d00_tools import parse_d00
from iso_tools import build_file_index, extract_file_data
from plot_tools import parse_plot

JP_D00 = PROJ / 'build' / 'd00_jp.dat'
JP_PLOT = PROJ / 'build' / 'plot_jp.dat'
JP_FNT_SYS_CACHE = PROJ / 'build' / 'fnt_sys_jp.bin'
JP_ISO_TRACK = Path('/home/ralf/Jogos/emulacao/romsets/sega-saturn/cue-bin'
                    '/Langrisser III (Japan)'
                    '/Langrisser III (Japan) (3M) (Track 01).bin')
TILE_MAP_PATH = Path('/home/ralf/Jogos/emulacao/tools/lang3_translation_analisis/jp_tile_map.json')
DEFAULT_OUT = Path('/home/ralf/romhack/lang3_english_translation_project/scripts/jp')

HEADER = ''

# FNT_SYS section layout (per archive/docs/20260503_fnt_sys_format.md):
#   31 BE32 pointers at 0x00, sections begin at 0x7C.
# 15 string-table pairs (offset table, data table). Section 28 is the
# lookup table (336 bytes, non-text). Pair 14 skips it and uses 29/30.
FNT_SYS_PAIRS = [
    (0, 1), (2, 3), (4, 5), (6, 7), (8, 9),
    (10, 11), (12, 13), (14, 15), (16, 17), (18, 19),
    (20, 21), (22, 23), (24, 25), (26, 27), (29, 30),
]


def load_tile_map() -> dict[int, str]:
    return {int(k): v for k, v in json.loads(TILE_MAP_PATH.read_text()).items()}


def decode_entry(entry_bytes: bytes, tile_map: dict[int, str]) -> str:
    """Decode raw bytes to a JP text string with control codes as ``<$XXXX>``.

    F600 carries a parameter word that is also emitted as ``<$XXXX>``.
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


# ---------------------------------------------------------------------------
# D00.DAT (125 scenario scripts)
# ---------------------------------------------------------------------------

def dump_d00(out_dir: Path, tile_map: dict[int, str],
             only_scen: list[int] | None = None) -> int:
    sections = parse_d00(JP_D00.read_bytes())
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
            # Voice-only / terminator-less entries in JP D00 (e.g. just
            # `<$F702>`) are valid via the offset table but the
            # script parser needs FFFE/FFFF to separate entries. Add a
            # synthetic <$FFFE> so the txt round-trips through
            # parse_script_file with the same entry count as the binary.
            if not (decoded.endswith('<$FFFE>') or decoded.endswith('<$FFFF>')):
                decoded += '<$FFFE>'
            lines.append(decoded + '\n')
        out_path = out_dir / f'scen{n:03d}J.txt'
        out_path.write_text(''.join(lines), encoding='utf-8')
        print(f'  wrote {out_path.name}  ({section.entry_count} entries)')
        written += 1
    return written


# ---------------------------------------------------------------------------
# PLOT.DAT (35 chapter recap blocks)
# ---------------------------------------------------------------------------

def _decode_plot_block(raw: bytes, tile_map: dict[int, str]) -> str:
    """Decode a PlotBlock's raw bytes.

    First 4 bytes are ``FFF8 <block_id>``; emit as single ``<$FFF8000N>``
    code to mirror ``scripts/en/plotE.txt`` formatting. The rest decodes
    with the standard tile/control rules.
    """
    if len(raw) < 4:
        return ''
    marker, block_id = struct.unpack('>HH', raw[:4])
    parts = [f'<${marker:04X}{block_id:04X}>']
    parts.append(decode_entry(raw[4:], tile_map))
    return ''.join(parts)


def dump_plot(out_dir: Path, tile_map: dict[int, str]) -> int:
    if not JP_PLOT.exists():
        print(f'WARN: {JP_PLOT} not found — run build.py once to extract it',
              file=sys.stderr)
        return 0
    blocks = parse_plot(JP_PLOT.read_bytes())
    lines = [HEADER]
    for block in blocks:
        lines.append(_decode_plot_block(block.raw_bytes, tile_map) + '\n')
    out_path = out_dir / 'plotJ.txt'
    out_path.write_text(''.join(lines), encoding='utf-8')
    print(f'  wrote {out_path.name}  ({len(blocks)} blocks)')
    return 1


# ---------------------------------------------------------------------------
# FNT_SYS.BIN (15 menu/UI string tables)
# ---------------------------------------------------------------------------

def _load_jp_fnt_sys() -> bytes:
    """Return the JP FNT_SYS.BIN bytes, using a cached copy if present."""
    if JP_FNT_SYS_CACHE.exists():
        return JP_FNT_SYS_CACHE.read_bytes()
    if not JP_ISO_TRACK.exists():
        raise FileNotFoundError(f'JP ISO not found at {JP_ISO_TRACK}')
    img = JP_ISO_TRACK.read_bytes()
    idx = build_file_index(img)
    entry = idx.get('LANG/FNT_SYS.BIN')
    if not entry:
        raise RuntimeError('LANG/FNT_SYS.BIN missing from JP ISO')
    data = extract_file_data(img, entry.extent, entry.size)
    JP_FNT_SYS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    JP_FNT_SYS_CACHE.write_bytes(data)
    print(f'  cached {JP_FNT_SYS_CACHE.name} ({len(data):,} bytes)')
    return data


def _fnt_sys_section_bounds(data: bytes) -> list[tuple[int, int]]:
    """Return (file_offset, length) for each of the 31 sections.

    The 31 BE32 pointers at 0x00 are work-RAM addresses, monotonically
    increasing. Section i occupies the file range derived from the
    delta between consecutive pointers, starting at 0x7C.
    """
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
    """Take exactly ``count`` FFFF-terminated records from a data section.

    Cannot key off ``0x0000`` to detect end-of-table because that word is a
    valid in-record tile (full-width space ``　``). The record count comes
    from the paired offset table size (one BE16 offset per record).
    """
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


def dump_fntsys(out_dir: Path, tile_map: dict[int, str]) -> int:
    try:
        data = _load_jp_fnt_sys()
    except (FileNotFoundError, RuntimeError) as e:
        print(f'WARN: skipping FNT_SYS — {e}', file=sys.stderr)
        return 0

    bounds = _fnt_sys_section_bounds(data)
    written = 0
    for pair_idx, (off_sec_idx, data_sec_idx) in enumerate(FNT_SYS_PAIRS, start=1):
        # Record count = number of BE16 offsets in the paired offset table.
        _, off_length = bounds[off_sec_idx]
        record_count = off_length // 2
        off, length = bounds[data_sec_idx]
        section_bytes = data[off:off + length]
        records = _split_fnt_sys_records(section_bytes, record_count)
        lines = [HEADER]
        for rec in records:
            lines.append(decode_entry(rec, tile_map) + '\n')
        out_path = out_dir / f'fntsys{pair_idx}J.txt'
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

    if not TILE_MAP_PATH.exists():
        print(f'ERROR: tile map not found at {TILE_MAP_PATH}', file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    tile_map = load_tile_map()

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
        if JP_D00.exists():
            total += dump_d00(args.out, tile_map, only_scen)
        else:
            print(f'WARN: {JP_D00} not found — skipping D00', file=sys.stderr)
    if args.only in (None, 'plot'):
        total += dump_plot(args.out, tile_map)
    if args.only in (None, 'fntsys'):
        total += dump_fntsys(args.out, tile_map)

    print(f'Wrote {total} JP script files to {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
