#!/usr/bin/env python3
"""balloon_opcodes.py — Parse D00.DAT bytecode to extract balloon display opcodes
per script entry. Ports ~/translation_analysis/balloon_viewer/tiles/d00.go.

Each section's bytecode (section_start+0x40 to section_start+text_block_off)
contains structured event records at 56-byte stride. Each record contains:
  byte[1] = entry_idx, byte[3] = opcode

Opcodes determine balloon rendering:
  0xC4 = portrait + character name on line 1 (12 tiles wide)
  0xC0 = portrait continuation, no name       (12 tiles wide)
  0xBC = narration/system text                 (16 tiles wide)

Usage:
    from balloon_opcodes import parse_d00_opcodes, BalloonType
    opmap = parse_d00_opcodes(d00_data)
    info = opmap.get(section_idx, {}).get(entry_idx)
    if info: print(info.btype, info.opcode)
"""
import struct
from enum import IntEnum
from dataclasses import dataclass


OP_PORTRAIT_NAME = 0xC4
OP_PORTRAIT_CONT = 0xC0
OP_NARRATION     = 0xBC

EVENT_RECORD_STRIDE = 0x38   # 56 bytes
SECTOR_SIZE = 2048


class BalloonType(IntEnum):
    UNKNOWN    = 0
    PORTRAIT   = 1   # 12 tiles, name on line 1 (C4)
    PORT_CONT  = 2   # 12 tiles, no name (C0)
    NARRATION  = 3   # 16 tiles, no name (BC)


@dataclass
class EntryInfo:
    btype: BalloonType
    opcode: int


def parse_d00_opcodes(data: bytes) -> dict:
    """Return {section_idx: {entry_idx: EntryInfo}}."""
    if len(data) < 4:
        raise ValueError("d00 data too short")

    num_sections = struct.unpack_from('>I', data, 0)[0]
    if not (0 < num_sections <= 200):
        raise ValueError(f"invalid section count: {num_sections}")

    header_size = 4 + num_sections * 8
    if len(data) < header_size:
        raise ValueError("d00 header truncated")

    result = {}

    for i in range(num_sections):
        off = 4 + i * 8
        sector = struct.unpack_from('>I', data, off)[0]
        section_start = sector * SECTOR_SIZE

        if section_start + 0x44 > len(data):
            continue

        text_block_off = struct.unpack_from('>I', data, section_start)[0]
        if text_block_off <= 0x40:
            continue  # no bytecode

        text_area_rel_off = section_start + text_block_off + 0x40
        if text_area_rel_off + 6 > len(data):
            continue
        text_area_rel = struct.unpack_from('>I', data, text_area_rel_off)[0]
        text_area_abs = section_start + text_block_off + text_area_rel
        if text_area_abs + 6 > len(data):
            continue

        offset_table_size = struct.unpack_from('>H', data, text_area_abs + 4)[0]
        entry_count = (offset_table_size - 4) // 2 - 1

        bc_start = section_start + 0x40
        bc_end = min(section_start + text_block_off, len(data))
        bytecode = data[bc_start:bc_end]

        opcode_map = _scan_event_block(bytecode, entry_count)
        if opcode_map:
            result[i] = opcode_map

    return result


def _scan_event_block(bc: bytes, entry_count: int) -> dict:
    """Find event records: 00 XX 00 {C4|C0|BC} at 56-byte-aligned positions."""
    candidates = []   # (offset, entry_idx, opcode)

    for i in range(3, len(bc)):
        op = bc[i]
        if op in (OP_PORTRAIT_NAME, OP_PORTRAIT_CONT, OP_NARRATION) and bc[i - 1] == 0x00:
            entry_idx = bc[i - 2]
            if entry_idx < entry_count:
                candidates.append((i - 3, entry_idx, op))

    if not candidates:
        return {}

    # Validate: require candidates to align at EVENT_RECORD_STRIDE (56 bytes)
    # A real event block has multiple records at exactly this stride.
    valid_indices = set()
    for j, (off_j, _, _) in enumerate(candidates):
        for k, (off_k, _, _) in enumerate(candidates):
            if j == k:
                continue
            diff = abs(off_k - off_j)
            if diff > 0 and diff % EVENT_RECORD_STRIDE == 0:
                valid_indices.add(j)
                valid_indices.add(k)

    result = {}
    opcode_to_type = {
        OP_PORTRAIT_NAME: BalloonType.PORTRAIT,
        OP_PORTRAIT_CONT: BalloonType.PORT_CONT,
        OP_NARRATION:     BalloonType.NARRATION,
    }
    for j, (_, entry_idx, opcode) in enumerate(candidates):
        if j not in valid_indices:
            continue
        result[entry_idx] = EntryInfo(btype=opcode_to_type[opcode], opcode=opcode)

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    from pathlib import Path

    d00_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('build/d00_jp.dat')
    data = d00_path.read_bytes()
    opmap = parse_d00_opcodes(data)

    print(f'Parsed {len(opmap)} sections with opcodes')
    total_entries = sum(len(m) for m in opmap.values())
    print(f'Total event records: {total_entries}')
    print()

    # Summary per section
    for sec_idx in sorted(opmap.keys())[:10]:
        m = opmap[sec_idx]
        types = {t: 0 for t in BalloonType}
        for info in m.values():
            types[info.btype] = types.get(info.btype, 0) + 1
        print(f'  Section {sec_idx:>3}: {len(m):>4} entries  '
              f'portrait+name={types[BalloonType.PORTRAIT]:>3}  '
              f'cont={types[BalloonType.PORT_CONT]:>3}  '
              f'narration={types[BalloonType.NARRATION]:>3}')
