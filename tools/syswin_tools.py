#!/usr/bin/env python3
"""syswin_tools.py — disembark LANG/BATTLE/SYSWIN.BIN (battle-window UI text).

SYSWIN.BIN holds the battle UI strings (Orders / Begin Battle / Move / Attack /
Unit1..8 / Yes / No / ...). This module makes that text script-driven from
``scripts/en/syswinE.txt`` so we own the UI patch instead of shipping 0.2 patch bytes.

Format (big-endian throughout — Saturn/SH-2), see
``archive/docs/20260606_syswin_format_re.md``:

  0x00            : 30 × uint32 window pointers, load base 0x00258000.
                    win[i] -> file offset (value - 0x258000).  win[0..2] frame
                    the text region; all 30 are left untouched.
  win[0]..win[1]  : uint16 offset table — word-offset of each record in win[1].
  win[1]..win[2]  : record stream. Each record is a list of tile-ids into the
                    SYSTEM font FNT_SYS.BIN (NOT the dialogue FONT.BIN),
                    terminated by 0xFFFF. One record per syswinE.txt line.

The JP records decode via the FNT_SYS char map to clean Japanese (命令, 戦闘開始,
はい, いいえ, ロード中です), proving syswin renders with FNT_SYS.BIN. So a syswin
*encoder* must map characters through ``fnt_sys_tools`` (the regenerated FNT_SYS
tile ids), and that font must actually contain the needed glyphs. Our FNT_SYS has
single-char Latin but NO Latin bigrams, while the win[1]..win[2] budget is tight
(JP fills it to the word). Single-char English overflows the budget, so a correct
disembark is COUPLED to fnt_sys (Phase 4): it needs Latin *bigram* glyphs added to
FNT_SYS (as 0.2 patch shipped) before syswin English records can both fit and render.
parse/build below are font-agnostic (tile-ids in, tile-ids out) and round-trip the
JP byte-exactly; encode_syswin is intentionally NOT implemented until the fnt_sys
dependency is resolved. The window pointers are fixed, so win[1] must end at/before
win[2]; growing past it would require shifting every window and is refused.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

LOAD_BASE = 0x00258000
N_WINDOW_PTRS = 30
TERMINATOR = 0xFFFF


@dataclass
class SysWin:
    """Parsed SYSWIN.BIN: the immutable shell + the editable record list."""
    raw: bytes                 # full original buffer (shell preserved on rebuild)
    win0: int                  # file offset of the offset table
    win1: int                  # file offset of the record stream
    win2: int                  # file offset of the next window (record budget end)
    records: list[list[int]]   # one tile-id list per UI string (no terminator)


def _window_offsets(data: bytes) -> list[int]:
    """The 30 window pointers as file offsets (value - load base)."""
    return [
        struct.unpack_from('>I', data, i * 4)[0] - LOAD_BASE
        for i in range(N_WINDOW_PTRS)
    ]


def parse_syswin(data: bytes) -> SysWin:
    """Parse SYSWIN.BIN into its window frame + record list."""
    offs = _window_offsets(data)
    win0, win1, win2 = offs[0], offs[1], offs[2]

    n_entries = (win1 - win0) // 2
    table = [struct.unpack_from('>H', data, win0 + 2 * i)[0] for i in range(n_entries)]

    # Parse FFFF-terminated tile-id records in the win1..win2 stream.
    records: list[list[int]] = []
    off = win1
    cur: list[int] = []
    while off < win2 - 1:
        v = struct.unpack_from('>H', data, off)[0]
        off += 2
        if v == TERMINATOR:
            records.append(cur)
            cur = []
        else:
            cur.append(v)

    # Sanity: the offset table must equal the record word-offsets.
    rebuilt = _record_word_offsets(records)
    if table != rebuilt:
        raise ValueError(
            f'syswin offset table mismatch: file={table[:6]}... '
            f'derived={rebuilt[:6]}... (records={len(records)}, table={n_entries})'
        )
    return SysWin(raw=bytes(data), win0=win0, win1=win1, win2=win2, records=records)


def _record_word_offsets(records: list[list[int]]) -> list[int]:
    """Word offset of each record within the stream (each record = ids + 1 term)."""
    offsets = []
    w = 0
    for rec in records:
        offsets.append(w)
        w += len(rec) + 1   # + the FFFF terminator
    return offsets


def build_syswin(sw: SysWin, records: list[list[int]] | None = None) -> bytes:
    """Rebuild a full SYSWIN.BIN, splicing a new record list into the shell.

    With ``records=None`` this round-trips the parsed file byte-exactly.
    The record count must stay constant (the offset-table size is fixed by the
    window pointers), and the stream must not exceed the win[1]..win[2] budget.
    """
    if records is None:
        records = sw.records

    n_table = (sw.win1 - sw.win0) // 2
    if len(records) != n_table:
        raise ValueError(
            f'syswin needs exactly {n_table} records (offset-table size is '
            f'fixed by the window pointers); got {len(records)}'
        )

    table = _record_word_offsets(records)
    table_bytes = b''.join(struct.pack('>H', off) for off in table)

    stream = bytearray()
    for rec in records:
        for tid in rec:
            stream += struct.pack('>H', tid)
        stream += struct.pack('>H', TERMINATOR)

    budget = sw.win2 - sw.win1
    if len(stream) > budget:
        raise ValueError(
            f'syswin record stream is {len(stream)} bytes but the budget is '
            f'{budget} (win1=0x{sw.win1:X}..win2=0x{sw.win2:X}); shorten the EN '
            f'strings — the window pointers are fixed and cannot be shifted'
        )

    out = bytearray(sw.raw)
    out[sw.win0:sw.win1] = table_bytes
    # Stream region: new records, then zero-fill any leftover up to win2.
    out[sw.win1:sw.win2] = bytes(stream) + b'\x00' * (budget - len(stream))
    return bytes(out)


def encode_syswin(jp_baseline: bytes, script_path: Path,
                  bigram_override: dict = None) -> bytes:
    """Build SYSWIN.BIN from scripts/en/syswinE.txt over the JP shell.

    One script line per record (43 lines). Blank lines map to EMPTY records
    (just the FFFF terminator) — the JP placeholder records each carry a
    0x0000 full-width-space tile, but an unused/spacer slot renders the same
    blank with no glyph. Emptying them reclaims 2 bytes/blank, which is the
    headroom English needs: the win[1]..win[2] byte region is a FIXED physical
    budget shared by ALL records (it ends at the next window pointer), but the
    per-item limit is its on-screen menu-box width, not its JP byte size. So
    redistributing the blank-record padding lets longer English labels fit
    (e.g. 配置 -> 'Placement', 5 tiles = same box width as 'Commander').
    Text encodes through the same FNTSYS maps the fnt_sys encoder uses
    (half-width bigrams; syswin renders with FNT_SYS glyphs). Replaces the
    0.2 patch-derived SYSWIN_OVERLAY blob (which drew 'Loading.……', 'BeginBattle',
    zenkaku Unit digits, and ate one record terminator).
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from d00_tools import encode_text_to_entry
    from font_tools import FNTSYS_CHAR_TILE_MAP, FNTSYS_BIGRAM_TILE_MAP
    # bigram_override = the RELOCATED fntsys bigram map for the new-font build.
    _sw_bigram = bigram_override if bigram_override is not None else FNTSYS_BIGRAM_TILE_MAP

    sw = parse_syswin(jp_baseline)
    lines = script_path.read_text(encoding='utf-8').splitlines()
    if len(lines) != len(sw.records):
        raise ValueError(
            f'{script_path.name} has {len(lines)} lines but syswin holds '
            f'{len(sw.records)} records (blank lines count — one per record)'
        )

    records: list[list[int]] = []
    for line, jp_rec in zip(lines, sw.records):
        if not line.strip():
            records.append([])   # empty record (FFFF only) — reclaims padding
            continue
        raw = encode_text_to_entry(line, dict(FNTSYS_CHAR_TILE_MAP),
                                   bigram_tile_map=_sw_bigram)
        if raw.endswith(b'\xff\xff'):
            raw = raw[:-2]
        records.append([
            int.from_bytes(raw[i:i + 2], 'big') for i in range(0, len(raw), 2)
        ])
    return build_syswin(sw, records)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('usage: syswin_tools.py <SYSWIN.BIN>  (round-trip self-check)')
        raise SystemExit(2)
    data = Path(sys.argv[1]).read_bytes()
    sw = parse_syswin(data)
    rt = build_syswin(sw)
    print(f'records: {len(sw.records)}  win0=0x{sw.win0:X} win1=0x{sw.win1:X} '
          f'win2=0x{sw.win2:X}')
    print(f'round-trip byte-exact: {rt == data}')
