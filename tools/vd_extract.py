#!/usr/bin/env python3
"""
vd_extract.py - Extract VermillionDesserts' D00.DAT text into scripts/en/ files.

Builds a VD-specific tile decode map from CWX's original tile layout (which VD
follows), then decodes each entry. Our font_tools.py has custom extensions
(hyphen/colon/semicolon bigrams, etc.) that repurpose tile slots VD uses
differently, so we must NOT use our BIGRAM_TILE_MAP for decoding VD's D00.

Strips all <$FFFC> during extraction and writes to scripts/en/scen{NNN}E.txt
in Akari Dawn format (compatible with parse_script_file()).

Usage:
    python3 tools/vd_extract.py
"""

import re
import struct
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR / 'tools'))

from d00_tools import parse_d00, decode_entry_to_text
from font_tools import (
    _LC_STARTS, _LC_RIGHT_FULL, _LC_UI_OFFSETS,
    _UC_GROUPS, _UC_UI_OFFSETS,
    _CWX_SPECIAL_BIGRAMS, _CWX_SPACE_DIGIT_BIGRAMS,
)

PATCHES_DIR = SCRIPT_DIR / 'patches'
SCRIPTS_DIR = SCRIPT_DIR / 'scripts' / 'en'

VD_D00_PATH = PATCHES_DIR / 'vd_d00.dat'


def build_vd_decode_map():
    """Build VD-specific tile_index -> string decode map.

    Based on CWX's original tile layout which VD follows exactly.
    Does NOT include our custom extensions (hyphen/colon/semicolon/enye bigrams,
    standalone apostrophe, custom tiles at 43-45, 906, 911-913, 1439, etc.)
    that repurpose CWX tile slots.
    """
    m = {}

    # --- Single-char tiles (0-42) ---
    m[0] = ' '
    m[1] = ':'
    m[2] = ';'
    m[3] = ','
    m[4] = '.'
    m[5] = '?'
    m[6] = '!'
    for i in range(10):
        m[7 + i] = str(i)
    for i in range(26):
        m[17 + i] = chr(65 + i)  # A-Z

    # --- LC bigram groups ---
    # VD uses CWX layout with 31 right-chars per group, but position 27
    # is period (.) not apostrophe ('). VD's right-char sequence:
    #   [' ', a-z, '.', ',', '?', '!']
    vd_lc_right = [' '] + list('abcdefghijklmnopqrstuvwxyz') + ['.', ',', '?', '!']
    for left, base in _LC_STARTS.items():
        ui_offsets = _LC_UI_OFFSETS.get(left, set())
        char_idx = 0
        for ri in range(33):  # max group span (m group has 33 slots)
            tile_idx = base + ri
            if ri in ui_offsets:
                continue
            if char_idx >= len(vd_lc_right):
                break
            right = vd_lc_right[char_idx]
            m[tile_idx] = left + right
            char_idx += 1

    # --- UC bigram groups ---
    for left, (base, rights) in _UC_GROUPS.items():
        ui_offsets = _UC_UI_OFFSETS.get(left, set())
        char_idx = 0
        ri = 0
        while char_idx < len(rights):
            if ri in ui_offsets:
                ri += 1
                continue
            m[base + ri] = left + rights[char_idx]
            char_idx += 1
            ri += 1

    # --- VD space+letter bigrams (tiles 1435-1473) ---
    # Sequence: ' a' through ' z' (26), then ' A' through ' I' (9),
    # skip 1470, then ' J' through ' L' (3)
    for i, ch in enumerate('abcdefghijklmnopqrstuvwxyz'):
        m[1435 + i] = ' ' + ch  # 1435-1460
    for i, ch in enumerate('ABCDEFGHI'):
        m[1461 + i] = ' ' + ch  # 1461-1469
    # 1470: unknown (not a space+letter bigram in VD analysis)
    m[1471] = ' J'
    m[1472] = ' K'
    m[1473] = ' L'

    # --- CWX special bigrams (pre-existing in VD font) ---
    for (left, right), tile_idx in _CWX_SPECIAL_BIGRAMS.items():
        m[tile_idx] = left + right

    # --- CWX space+digit bigrams ---
    for (left, right), tile_idx in _CWX_SPACE_DIGIT_BIGRAMS.items():
        m[tile_idx] = left + right

    # --- CWX range stat/menu bigrams (identified from VD font analysis) ---
    cwx_menu_bigrams = {
        1501: 'PC', 1502: 'BG', 1503: 'M ', 1504: 'Sc', 1505: 'Tu',
        1513: 'P!', 1514: 'RA', 1524: 'AT', 1525: 'DF', 1526: 'IN',
        1527: 'T ', 1528: 'LV', 1529: 'HP', 1530: 'MP', 1531: 'ST',
        1532: 'R ',
    }
    m.update(cwx_menu_bigrams)

    # --- Punctuation/special bigrams from analysis ---
    # ?+? and ?+! and !+! and !+? (tiles 907-910, decoded from VD font)
    m[907] = '??'
    m[908] = '?!'
    m[909] = '!!'
    m[910] = '!?'

    # --- VD-specific tiles identified via context analysis ---
    # Full-width single lowercase chars (tiles 43-45)
    m[43] = 'a'
    m[44] = 'm'
    m[45] = 'p'

    # Two-dot ellipsis (tile 906, 4964 occurrences)
    m[906] = '…'

    # Double-quote (tile 1470, 230 occurrences)
    m[1470] = '"'

    # Space + uppercase M-Z (tiles 1474-1487)
    for i, ch in enumerate('MNOPQRSTUVWXYZ'):
        m[1474 + i] = ' ' + ch

    # Apostrophe bigrams (tiles 1491-1499)
    m[1491] = "o'"
    m[1492] = "n'"
    m[1493] = "s'"
    m[1494] = "t'"
    m[1495] = "u'"
    m[1496] = "y'"
    m[1497] = "'r"
    m[1498] = "'s"
    m[1499] = "'t"

    # CWX range single lowercase letters (tiles 1585-1610 = a-z)
    for i in range(26):
        m[1585 + i] = chr(ord('a') + i)

    return m


def extract_vd_scripts():
    """Extract VD D00.DAT text into scripts/en/ files."""
    if not VD_D00_PATH.exists():
        print(f'ERROR: VD D00.DAT not found at {VD_D00_PATH}')
        return 1

    d00_data = VD_D00_PATH.read_bytes()
    sections = parse_d00(d00_data)
    print(f'Parsed {len(sections)} sections from VD D00.DAT ({len(d00_data):,} bytes)')

    vd_decode_map = build_vd_decode_map()
    print(f'VD decode map: {len(vd_decode_map)} tile entries')

    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    total_entries = 0
    hex_codes = set()

    for sec in sections:
        scen_num = sec.index + 1
        lines = []
        lines.append(f'Langrisser III dumper [0x0000 to 0x0000]')
        lines.append('')
        lines.append('Cyber Warrior X')
        lines.append('')

        for entry_data in sec.entries:
            text = decode_entry_to_text(entry_data, vd_decode_map)

            # Replace <$FFFC> (newline within text box) with space
            text = text.replace('<$FFFC>', ' ')

            # Track unmapped tile codes (exclude control codes and F600 params)
            codes_in_text = re.findall(r'<\$([0-9A-Fa-f]{4})>', text)
            skip_next = False
            for hex_str in codes_in_text:
                code = int(hex_str, 16)
                if skip_next:
                    skip_next = False
                    continue
                if code == 0xF600:
                    skip_next = True  # next code is F600's parameter
                    continue
                if code >= 0xF000:
                    continue
                hex_codes.add(code)

            lines.append(text)

        total_entries += sec.entry_count

        out_path = SCRIPTS_DIR / f'scen{scen_num:03d}E.txt'
        out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f'Extracted {total_entries:,} entries across {len(sections)} files')
    print(f'VD-specific tile codes (as <$XXXX>): {len(hex_codes)}')
    if hex_codes:
        sorted_codes = sorted(hex_codes)
        print(f'  Range: {sorted_codes[0]:#06x} - {sorted_codes[-1]:#06x}')
        # Show all hex codes for analysis
        for code in sorted_codes:
            print(f'  {code:#06x} ({code})')
    print(f'Output: {SCRIPTS_DIR}/')
    return 0


if __name__ == '__main__':
    raise SystemExit(extract_vd_scripts())
