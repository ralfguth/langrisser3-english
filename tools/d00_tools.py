#!/usr/bin/env python3
"""
d00_tools.py - Parse, encode, and rebuild D00.DAT for Langrisser III Saturn.

D00.DAT structure (all integers big-endian):
  Header:
    uint32  section_count
    uint32[section_count]  (sector, size) pairs

  Each section at sector*2048:
    0x00: uint32  text_block_off   (offset to text/dialogue block within section)
    0x04: uint32  constant 0x40    (header size)
    0x08-0x3F:    section header fields
    0x40+:        script bytecode
    text_block_off+: text block (pointer table + sub-offset lists + text area)

  Text block:
    17 x uint32 pointers (0x44 bytes)
    Pointer [16] (at offset 0x40) -> text area

  Text area (at text_block_off + pointer[16]):
    uint32  total_text_size
    uint16  offset_table_size  (= 4 + 2*(entry_count+1))
    uint16[entry_count]  entry offsets (relative to text_area_start)
    uint16  sentinel value (always 0x00A4 = 164)
    entry data (2-byte tile codes + control codes)

  Control codes (word >= 0xF000):
    0xFFFF  string terminator
    0xFFFE  end of dialogue message
    0xFFFC  newline within text box
    0xFFFD  scroll/pause
    0xFFFB  wait for button press
    0xF600  name variable (followed by 0x0000 = player name)
"""

import math
import re
import struct
from pathlib import Path

# Sector size within D00.DAT (2048 byte logical sectors)
USER_SIZE = 2048

# The sentinel value that always appears as the last uint16 in the offset table
OFFSET_TABLE_SENTINEL = 164  # 0x00A4


# ---------------------------------------------------------------------------
# D00.DAT parsing
# ---------------------------------------------------------------------------

class D00Section:
    """Represents one scenario section in D00.DAT."""
    def __init__(self):
        self.index = 0
        self.sector = 0
        self.size = 0
        self.byte_offset = 0
        self.pre_text_data = b''    # Everything before the text area (preserved as-is)
        self.text_block_off = 0     # Offset to text block within section
        self.text_area_rel = 0      # Offset of text area relative to text block
        self.text_area_offset = 0   # Absolute byte offset of text area in D00.DAT
        self.text_size = 0          # Total size of text area
        self.offset_table_size = 0
        self.entry_count = 0        # Number of real text entries
        self.entries = []           # list of bytes (raw entry data)


def parse_d00(data: bytes) -> list:
    """Parse D00.DAT into list of D00Section."""
    num_sections = struct.unpack_from('>I', data, 0)[0]
    sections = []

    for i in range(num_sections):
        sec = D00Section()
        sec.index = i
        off = 4 + i * 8
        sec.sector = struct.unpack_from('>I', data, off)[0]
        sec.size = struct.unpack_from('>I', data, off + 4)[0]
        sec.byte_offset = sec.sector * USER_SIZE

        start = sec.byte_offset

        # text_block_off: offset from section start to text block
        sec.text_block_off = struct.unpack_from('>I', data, start)[0]

        # Pointer[16] at text_block + 0x40: offset from text block to text area
        sec.text_area_rel = struct.unpack_from(
            '>I', data, start + sec.text_block_off + 0x40)[0]

        text_area_abs = start + sec.text_block_off + sec.text_area_rel
        sec.text_area_offset = text_area_abs

        # Save everything before text area (section header, scripts, text block pointers)
        sec.pre_text_data = data[start:text_area_abs]

        # Parse text area header
        sec.text_size = struct.unpack_from('>I', data, text_area_abs)[0]
        sec.offset_table_size = struct.unpack_from('>H', data, text_area_abs + 4)[0]

        # Entry count: the offset table has entry_count offsets + 1 sentinel (0x00A4)
        # offset_table_size = 4 + 2 * (entry_count + 1)
        raw_count = (sec.offset_table_size - 4) // 2
        sec.entry_count = raw_count - 1  # subtract the sentinel

        # Read entry offsets (relative to text_area_abs)
        entry_offsets = []
        for j in range(sec.entry_count):
            entry_offsets.append(
                struct.unpack_from('>H', data, text_area_abs + 6 + j * 2)[0])

        # Extract entries using offset boundaries
        sec.entries = []
        for j in range(sec.entry_count):
            e_start = text_area_abs + entry_offsets[j]
            if j + 1 < sec.entry_count:
                e_end = text_area_abs + entry_offsets[j + 1]
            else:
                e_end = text_area_abs + sec.text_size
            sec.entries.append(data[e_start:e_end])

        sections.append(sec)

    return sections


def decode_entry_to_text(entry: bytes, tile_char_map: dict) -> str:
    """Decode raw entry bytes to human-readable text using tile->char map."""
    parts = []
    i = 0
    while i < len(entry) - 1:
        word = struct.unpack_from('>H', entry, i)[0]
        i += 2

        if word >= 0xF000:
            parts.append(f'<${word:04X}>')
            if word == 0xF600 and i < len(entry) - 1:
                param = struct.unpack_from('>H', entry, i)[0]
                parts.append(f'<${param:04X}>')
                i += 2
        elif word in tile_char_map:
            parts.append(tile_char_map[word])
        else:
            parts.append(f'<${word:04X}>')

    return ''.join(parts)


# ---------------------------------------------------------------------------
# Text encoding (English text -> tile codes)
# ---------------------------------------------------------------------------

def encode_text_to_entry(text: str, char_tile_map: dict,
                         bigram_tile_map: dict = None) -> bytes:
    """Encode a text string with escape sequences into raw entry bytes.

    Handles:
    - <$XXXX> escape sequences (control codes, raw tile codes)
    - [diehardt's name] -> F600 0000
    - Bigram pairs via bigram_tile_map (if provided)
    - Regular characters via char_tile_map
    - Unsupported characters are silently dropped

    When bigram_tile_map is provided, regular text segments are encoded using
    greedy left-to-right bigram matching: if (char[i], char[i+1]) exists in
    bigram_tile_map, emit that tile and advance by 2; otherwise fall back to
    single-char lookup in char_tile_map.
    """
    # First, segment the text into control codes and regular text chunks.
    # This ensures control codes are never part of bigram pairs.
    segments = []  # list of ('ctrl', bytes) or ('text', str)
    i = 0
    current_text = []

    while i < len(text):
        # Check for [diehardt's name] variable
        if text[i:].lower().startswith("[diehardt's name]"):
            if current_text:
                segments.append(('text', ''.join(current_text)))
                current_text = []
            segments.append(('ctrl', struct.pack('>HH', 0xF600, 0x0000)))
            i += 17
            continue

        # Check for escape sequence <$XXXX>
        if text[i:i+2] == '<$':
            end = text.find('>', i + 2)
            if end != -1:
                if current_text:
                    segments.append(('text', ''.join(current_text)))
                    current_text = []
                ctrl_bytes = bytearray()
                hex_str = text[i+2:end].strip()
                try:
                    for j in range(0, len(hex_str), 4):
                        part = hex_str[j:j+4].ljust(4, '0')
                        ctrl_bytes.extend(struct.pack('>H', int(part, 16)))
                except ValueError:
                    pass
                segments.append(('ctrl', bytes(ctrl_bytes)))
                i = end + 1
                continue

        current_text.append(text[i])
        i += 1

    if current_text:
        segments.append(('text', ''.join(current_text)))

    # Now encode each segment
    result = bytearray()

    for seg_type, seg_data in segments:
        if seg_type == 'ctrl':
            result.extend(seg_data)
        else:
            # Encode regular text segment
            s = seg_data.replace('...', '…')
            j = 0
            while j < len(s):
                # Try bigram if available and there's a next character
                if bigram_tile_map is not None and j + 1 < len(s):
                    pair = (s[j], s[j+1])
                    if pair in bigram_tile_map:
                        result.extend(struct.pack('>H', bigram_tile_map[pair]))
                        j += 2
                        continue

                # Single character fallback
                if s[j] in char_tile_map:
                    result.extend(struct.pack('>H', char_tile_map[s[j]]))
                # Skip unmapped chars
                j += 1

    return bytes(result)


# ---------------------------------------------------------------------------
# Script file parsing
# ---------------------------------------------------------------------------

def parse_script_file(path: Path) -> list:
    """Parse an Akari Dawn format script file into list of text entries.

    Each entry is one or more lines joined together, terminated by <$FFFF> or <$FFFE>.
    Lines ending with <$FFFC> (newline) or <$FFFD> (scroll) are intermediate
    and get joined with the following line.

    Header lines (starting with 'Langrisser' or 'Cyber') are skipped.
    """
    text = path.read_text(encoding='utf-8')
    entries = []
    current_parts = []

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('Langrisser') or line.startswith('Cyber'):
            continue

        current_parts.append(line)

        # Entry terminators: FFFF or FFFE
        if line.endswith('<$FFFF>') or line.endswith('<$FFFE>'):
            full = ''.join(current_parts)
            entries.append(full)
            current_parts = []

    # Handle remaining parts (missing terminator)
    if current_parts:
        full = ''.join(current_parts)
        if not (full.endswith('<$FFFF>') or full.endswith('<$FFFE>')):
            full += '<$FFFF>'
        entries.append(full)

    return entries


# ---------------------------------------------------------------------------
# D00.DAT text area building
# ---------------------------------------------------------------------------

def build_text_area(entry_bytes_list: list) -> bytes | None:
    """Build a complete text area from list of encoded entry byte strings.

    Returns None if total size exceeds uint16 offset range (65535 bytes).

    Layout:
        +0x00: uint32 BE - total text area size
        +0x04: uint16 BE - offset table size (4 + 2*(entry_count+1))
        +0x06: uint16 BE[] - entry offsets (relative to byte 0)
        +0x06+2*N: uint16 sentinel (0x00A4)
        ...: 10-byte constant gap (always 008000ac00c800a5ffff)
        ...: entry data
    """
    # Constant gap that appears between offset table and entry data in all sections
    TEXT_AREA_GAP = bytes.fromhex('008000ac00c800a5ffff')

    num_entries = len(entry_bytes_list)
    # offset_table_size includes: 4 base + 2 bytes per entry + 2 for sentinel
    offset_table_size = 4 + 2 * (num_entries + 1)
    # Header before entry data: offset table + gap
    header_size = 6 + 2 * (num_entries + 1) + len(TEXT_AREA_GAP)

    entry_offsets = []
    current = header_size
    for entry in entry_bytes_list:
        entry_offsets.append(current)
        current += len(entry)

    total_size = current

    # Check uint16 overflow
    if total_size > 65535 or any(off > 65535 for off in entry_offsets):
        return None

    result = bytearray()
    result += struct.pack('>I', total_size)
    result += struct.pack('>H', offset_table_size)
    for off in entry_offsets:
        result += struct.pack('>H', off)
    result += struct.pack('>H', OFFSET_TABLE_SENTINEL)
    result += TEXT_AREA_GAP
    for entry in entry_bytes_list:
        result += entry

    return bytes(result)


# ---------------------------------------------------------------------------
# D00.DAT in-place patching (safe - no sector layout changes)
# ---------------------------------------------------------------------------

def patch_d00_inplace(original_d00: bytes, sections: list,
                      new_text_areas: dict) -> tuple:
    """Patch D00.DAT in-place: replace text areas within allocated space.

    Uses the real allocated space per section (gap between sector offsets
    of adjacent sections), not just sec.size.  This accounts for sector
    padding that the original D00.DAT builder left between sections.

    For each section with a new text area:
    - If new text fits -> replace text bytes, zero-fill remaining
    - If too large -> skip (keep JP original)

    Returns: (patched_bytes, num_patched, num_skipped)
    """
    result = bytearray(original_d00)
    patched = 0
    skipped = 0

    for sec_idx, new_text in new_text_areas.items():
        sec = sections[sec_idx]
        text_start = sec.text_area_offset

        # Available space = allocated end - text area start
        # Allocated end = next section's byte offset (or end of D00.DAT)
        if sec_idx + 1 < len(sections):
            allocated_end = sections[sec_idx + 1].byte_offset
        else:
            allocated_end = len(original_d00)
        available = allocated_end - text_start

        if len(new_text) <= available:
            result[text_start:text_start + len(new_text)] = new_text
            remaining = available - len(new_text)
            if remaining > 0:
                result[text_start + len(new_text):text_start + available] = b'\x00' * remaining
            patched += 1
        else:
            skipped += 1

    return bytes(result), patched, skipped


# ---------------------------------------------------------------------------
# D00.DAT full rebuild (changes sector layout - larger output)
# ---------------------------------------------------------------------------

def rebuild_d00(sections: list, new_text_areas: dict = None) -> bytes:
    """Rebuild D00.DAT from parsed sections.

    Relocates sections to accommodate size changes.
    Updates section table and internal pointers.
    """
    if new_text_areas is None:
        new_text_areas = {}

    num_sections = len(sections)
    section_blobs = []

    # Reserve space for header (section table)
    header_size = 4 + num_sections * 8
    first_section_offset = math.ceil(header_size / USER_SIZE) * USER_SIZE
    current_offset = first_section_offset

    for i in range(num_sections):
        sec = sections[i]
        pre_text = bytearray(sec.pre_text_data)

        if i in new_text_areas:
            text_area = new_text_areas[i]
        else:
            text_area = build_text_area(sec.entries)

        # Update pointer[16] in text block to point to the text area
        # pointer[16] is at text_block_off + 0x40 relative to section start
        new_text_area_rel = len(pre_text) - sec.text_block_off  # offset from text block
        # But pre_text = data[section_start : text_area_abs]
        # And text_block is at section_start + text_block_off
        # So len(pre_text) - text_block_off = text_area_abs - (section_start + text_block_off)
        # = original text_area_rel (unchanged since pre_text size doesn't change)
        struct.pack_into('>I', pre_text, sec.text_block_off + 0x40, new_text_area_rel)

        section_data = bytes(pre_text) + text_area
        padded = math.ceil(len(section_data) / USER_SIZE) * USER_SIZE
        section_data = section_data + b'\x00' * (padded - len(section_data))

        sector_num = current_offset // USER_SIZE
        section_blobs.append({
            'sector': sector_num,
            'size': len(bytes(pre_text)) + len(text_area),  # actual data size
            'data': section_data,
        })
        current_offset += padded

    # Build final D00.DAT
    result = bytearray()
    result += struct.pack('>I', num_sections)
    for blob in section_blobs:
        result += struct.pack('>I', blob['sector'])
        result += struct.pack('>I', blob['size'])

    # Pad header to sector boundary
    padded_header = math.ceil(len(result) / USER_SIZE) * USER_SIZE
    result += b'\x00' * (padded_header - len(result))

    for blob in section_blobs:
        result += blob['data']

    return bytes(result)


# ---------------------------------------------------------------------------
# High-level insertion
# ---------------------------------------------------------------------------

def insert_translations(sections: list, scripts_dir: Path,
                        char_tile_map: dict, bigram_tile_map: dict = None,
                        verbose: bool = False) -> tuple:
    """Insert English translations into D00.DAT sections.

    Returns (dict of section_index -> new text area bytes, stats dict).
    """
    new_text_areas = {}
    stats = {
        'translated': 0,
        'skipped': 0,
        'entry_count_mismatches': [],
        'errors': [],
    }

    for sec in sections:
        scen_num = sec.index + 1

        # Find translation file
        script_path = None
        for pattern in [f'scen{scen_num:03d}E.txt', f'scen{scen_num:03d}e.txt']:
            candidate = scripts_dir / pattern
            if candidate.exists():
                script_path = candidate
                break

        if script_path is None:
            stats['skipped'] += 1
            continue

        text_entries = parse_script_file(script_path)
        if not text_entries:
            stats['skipped'] += 1
            continue

        # Encode entries
        encoded_entries = []
        for text in text_entries:
            encoded = encode_text_to_entry(text, char_tile_map, bigram_tile_map)
            # Ensure entry ends with a control code terminator
            if len(encoded) >= 2:
                last_word = struct.unpack_from('>H', encoded, len(encoded) - 2)[0]
                if last_word < 0xFFF0:
                    encoded += b'\xff\xff'
            else:
                encoded = b'\xff\xff'
            encoded_entries.append(encoded)

        # Match entry count with original section
        jp_count = sec.entry_count
        en_count = len(encoded_entries)

        if en_count < jp_count:
            while len(encoded_entries) < jp_count:
                encoded_entries.append(b'\xff\xff')
        elif en_count > jp_count:
            stats['entry_count_mismatches'].append({
                'section': sec.index,
                'jp_count': jp_count,
                'en_count': en_count,
            })
            encoded_entries = encoded_entries[:jp_count]

        text_area = build_text_area(encoded_entries)
        if text_area is None:
            stats['errors'].append(
                f'scen{scen_num:03d}: text area overflow (>65535 bytes), keeping JP')
            stats['skipped'] += 1
            continue

        new_text_areas[sec.index] = text_area
        stats['translated'] += 1

    return new_text_areas, stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Usage: d00_tools.py <d00.dat> [--dump]')
        sys.exit(1)

    d00_path = Path(sys.argv[1])
    data = d00_path.read_bytes()
    sections = parse_d00(data)

    print(f'D00.DAT: {len(data):,} bytes, {len(sections)} sections')

    for sec in sections:
        print(f'  Section {sec.index}: {sec.entry_count} entries, '
              f'text_size={sec.text_size:,}')
