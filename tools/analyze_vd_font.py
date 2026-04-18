#!/usr/bin/env python3
"""
analyze_vd_font.py - Reverse-engineer VermillionDesserts' ENFONT2.BIN tile map.

Reads the VD font binary, extracts left/right half-glyphs from each tile,
and compares against all known glyph bitmaps from font_tools.py to identify
what character(s) each tile contains.

This is a READ-ONLY analysis script. It does not modify any files.
"""

import sys
import os

# Add parent dir so we can import font_tools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from font_tools import (
    _LETTER_GLYPHS, _DIGIT_TILES, _PUNCT_GLYPHS,
    _APOSTROPHE_GLYPH, _BLANK_GLYPH,
    _UC_STANDALONE_TILES,
    BIGRAM_TILE_MAP, CHAR_TILE_MAP,
    visualize_tile,
)

VD_FONT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'patches', 'vd_font.bin'
)

TILE_SIZE = 32
TILE_COUNT = 1691


def load_font(path):
    with open(path, 'rb') as f:
        data = f.read()
    assert len(data) == TILE_COUNT * TILE_SIZE, \
        f"Expected {TILE_COUNT * TILE_SIZE} bytes, got {len(data)}"
    return data


def extract_left_half(tile_data):
    """Extract left 8px half (even bytes) from a 32-byte tile."""
    return bytes(tile_data[i * 2] for i in range(16))


def extract_right_half(tile_data):
    """Extract right 8px half (odd bytes) from a 32-byte tile."""
    return bytes(tile_data[i * 2 + 1] for i in range(16))


def build_glyph_db():
    """Build a database of all known 16-byte half-glyphs -> character name."""
    db = {}
    # Blank
    db[_BLANK_GLYPH] = ' '
    # Letters a-z, A-Z
    for ch, glyph in _LETTER_GLYPHS.items():
        db[glyph] = ch
    # Punctuation (: ; , . ? !)
    for ch, glyph in _PUNCT_GLYPHS.items():
        db[glyph] = ch
    # Apostrophe
    db[_APOSTROPHE_GLYPH] = "'"
    return db


def build_fullwidth_db():
    """Build a database of full 32-byte tiles -> character name."""
    db = {}
    # Digits
    for ch, tile in _DIGIT_TILES.items():
        db[tile] = ch
    # Uppercase standalone
    for ch, tile in _UC_STANDALONE_TILES.items():
        db[tile] = ch
    # Blank tile
    db[b'\x00' * 32] = '<blank>'
    return db


def hamming_distance(a, b):
    """Count differing bytes between two byte strings."""
    return sum(1 for x, y in zip(a, b) if x != y)


def find_closest_glyph(glyph, glyph_db, threshold=2):
    """Find the closest matching glyph if exact match fails.
    Returns (char, distance) or (None, None)."""
    best_ch = None
    best_dist = 999
    for known, ch in glyph_db.items():
        d = hamming_distance(glyph, known)
        if d < best_dist:
            best_dist = d
            best_ch = ch
    if best_dist <= threshold:
        return best_ch, best_dist
    return None, None


def analyze():
    print(f"Loading VD font from: {VD_FONT_PATH}")
    font = load_font(VD_FONT_PATH)
    print(f"Loaded {len(font)} bytes = {len(font) // TILE_SIZE} tiles\n")

    glyph_db = build_glyph_db()
    fullwidth_db = build_fullwidth_db()

    # Build our reverse bigram map: tile_index -> (left, right)
    our_bigram_reverse = {}
    for (l, r), idx in BIGRAM_TILE_MAP.items():
        our_bigram_reverse[idx] = (l, r)
    our_char_reverse = {}
    for ch, idx in CHAR_TILE_MAP.items():
        our_char_reverse[idx] = ch

    # Results
    vd_map = {}  # tile_index -> result dict
    blank_tiles = []
    matched_tiles = []
    unmatched_tiles = []
    fullwidth_matched = []
    half_matched = []  # only one half matched
    diff_from_ours = []  # VD tile matches glyphs but differs from our bigram map

    for tile_idx in range(TILE_COUNT):
        offset = tile_idx * TILE_SIZE
        tile_data = font[offset:offset + TILE_SIZE]

        result = {
            'tile_idx': tile_idx,
            'left_char': None,
            'right_char': None,
            'fullwidth_char': None,
            'is_blank': False,
            'match_type': 'unknown',
        }

        # Check blank
        if tile_data == b'\x00' * 32:
            result['is_blank'] = True
            result['match_type'] = 'blank'
            blank_tiles.append(tile_idx)
            vd_map[tile_idx] = result
            continue

        # Check full-width match (digits, UC standalone)
        if tile_data in fullwidth_db:
            result['fullwidth_char'] = fullwidth_db[tile_data]
            result['match_type'] = 'fullwidth_exact'
            fullwidth_matched.append(tile_idx)
            matched_tiles.append(tile_idx)
            vd_map[tile_idx] = result
            continue

        # Extract halves and try matching
        left_half = extract_left_half(tile_data)
        right_half = extract_right_half(tile_data)

        left_ch = glyph_db.get(left_half)
        right_ch = glyph_db.get(right_half)

        if left_ch is not None and right_ch is not None:
            result['left_char'] = left_ch
            result['right_char'] = right_ch
            result['match_type'] = 'bigram_exact'
            matched_tiles.append(tile_idx)

            # Check if this differs from our map
            our_pair = our_bigram_reverse.get(tile_idx)
            if our_pair is not None and (left_ch, right_ch) != our_pair:
                diff_from_ours.append((tile_idx, (left_ch, right_ch), our_pair))

            vd_map[tile_idx] = result
            continue

        # Try fuzzy match for half-glyphs
        if left_ch is None:
            left_ch_fuzzy, left_dist = find_closest_glyph(left_half, glyph_db)
        else:
            left_ch_fuzzy, left_dist = left_ch, 0
        if right_ch is None:
            right_ch_fuzzy, right_dist = find_closest_glyph(right_half, glyph_db)
        else:
            right_ch_fuzzy, right_dist = right_ch, 0

        if left_ch is not None or right_ch is not None:
            result['left_char'] = left_ch
            result['right_char'] = right_ch
            result['match_type'] = 'half_match'
            half_matched.append(tile_idx)
            matched_tiles.append(tile_idx)
            vd_map[tile_idx] = result
            continue

        # Try fullwidth fuzzy
        best_fw = None
        best_fw_dist = 999
        for known_tile, ch in fullwidth_db.items():
            d = hamming_distance(tile_data, known_tile)
            if d < best_fw_dist:
                best_fw_dist = d
                best_fw = ch
        if best_fw_dist <= 4:
            result['fullwidth_char'] = f"{best_fw}~{best_fw_dist}"
            result['match_type'] = 'fullwidth_fuzzy'
            matched_tiles.append(tile_idx)
            vd_map[tile_idx] = result
            continue

        # Try fuzzy both halves
        if left_ch_fuzzy is not None and right_ch_fuzzy is not None:
            result['left_char'] = f"{left_ch_fuzzy}~{left_dist}"
            result['right_char'] = f"{right_ch_fuzzy}~{right_dist}"
            result['match_type'] = 'bigram_fuzzy'
            matched_tiles.append(tile_idx)
            vd_map[tile_idx] = result
            continue

        result['match_type'] = 'unknown'
        unmatched_tiles.append(tile_idx)
        vd_map[tile_idx] = result

    # ===== REPORT =====
    print("=" * 80)
    print("VD FONT ANALYSIS REPORT")
    print("=" * 80)

    print(f"\nTotal tiles: {TILE_COUNT}")
    print(f"Blank tiles: {len(blank_tiles)}")
    print(f"Matched tiles: {len(matched_tiles)}")
    print(f"  - Full-width exact: {len(fullwidth_matched)}")
    print(f"  - Bigram exact (both halves): {len([t for t in range(TILE_COUNT) if vd_map[t]['match_type'] == 'bigram_exact'])}")
    print(f"  - Half match (one side only): {len(half_matched)}")
    print(f"  - Fuzzy matches: {len([t for t in range(TILE_COUNT) if vd_map[t]['match_type'] in ('bigram_fuzzy', 'fullwidth_fuzzy')])}")
    print(f"Unmatched (unknown): {len(unmatched_tiles)}")

    # Tiles 0-50 detail
    print("\n" + "=" * 80)
    print("TILE MAP: tiles 0-50 (most important range)")
    print("=" * 80)
    for i in range(min(51, TILE_COUNT)):
        r = vd_map[i]
        if r['is_blank']:
            desc = "<blank>"
        elif r['fullwidth_char']:
            desc = f"FW:{r['fullwidth_char']}"
        elif r['left_char'] is not None and r['right_char'] is not None:
            lc = r['left_char']
            rc = r['right_char']
            desc = f"[{lc}|{rc}]"
        elif r['left_char'] is not None:
            desc = f"[{r['left_char']}|???]"
        elif r['right_char'] is not None:
            desc = f"[???|{r['right_char']}]"
        else:
            desc = f"<unknown:{r['match_type']}>"

        # Show what our map says this tile should be
        our_label = ""
        if i in our_char_reverse:
            our_label = f"  (our char: '{our_char_reverse[i]}')"
        elif i in our_bigram_reverse:
            l, r2 = our_bigram_reverse[i]
            our_label = f"  (our bigram: '{l}{r2}')"

        print(f"  Tile {i:4d}: {desc:30s}{our_label}")

    # Extended range tiles 0-100
    print("\n" + "=" * 80)
    print("TILE MAP: tiles 51-100")
    print("=" * 80)
    for i in range(51, min(101, TILE_COUNT)):
        r = vd_map[i]
        if r['is_blank']:
            desc = "<blank>"
        elif r['fullwidth_char']:
            desc = f"FW:{r['fullwidth_char']}"
        elif r['left_char'] is not None and r['right_char'] is not None:
            lc = r['left_char']
            rc = r['right_char']
            desc = f"[{lc}|{rc}]"
        elif r['left_char'] is not None:
            desc = f"[{r['left_char']}|???]"
        elif r['right_char'] is not None:
            desc = f"[???|{r['right_char']}]"
        else:
            desc = f"<unknown:{r['match_type']}>"

        our_label = ""
        if i in our_char_reverse:
            our_label = f"  (our char: '{our_char_reverse[i]}')"
        elif i in our_bigram_reverse:
            l, r2 = our_bigram_reverse[i]
            our_label = f"  (our bigram: '{l}{r2}')"

        print(f"  Tile {i:4d}: {desc:30s}{our_label}")

    # Tiles where VD differs from our bigram map
    print("\n" + "=" * 80)
    print("TILES WHERE VD CONTENT DIFFERS FROM OUR BIGRAM MAP")
    print("=" * 80)
    if diff_from_ours:
        for tile_idx, vd_pair, our_pair in diff_from_ours:
            vd_str = f"[{vd_pair[0]}|{vd_pair[1]}]"
            our_str = f"[{our_pair[0]}|{our_pair[1]}]"
            print(f"  Tile {tile_idx:4d}: VD={vd_str:12s}  OURS={our_str:12s}")
    else:
        print("  (none found)")

    # Show all tiles that match our char map exactly
    print("\n" + "=" * 80)
    print("CHAR TILE MAP VERIFICATION (tiles 0-42)")
    print("=" * 80)
    for ch, idx in sorted(CHAR_TILE_MAP.items(), key=lambda x: x[1]):
        if idx > 42:
            continue
        r = vd_map[idx]
        if r['is_blank']:
            vd_content = "<blank>"
        elif r['fullwidth_char']:
            vd_content = f"FW:{r['fullwidth_char']}"
        elif r['left_char'] is not None and r['right_char'] is not None:
            vd_content = f"[{r['left_char']}|{r['right_char']}]"
        else:
            vd_content = f"<{r['match_type']}>"
        match_ok = "OK" if (
            (ch == ' ' and r['is_blank']) or
            (r['fullwidth_char'] == ch) or
            (r['left_char'] == ch and r['right_char'] == ' ')
        ) else "DIFF"
        print(f"  Tile {idx:3d} = '{ch}': VD has {vd_content:20s} [{match_ok}]")

    # Show blank tile locations
    print("\n" + "=" * 80)
    print(f"BLANK TILES ({len(blank_tiles)} total)")
    print("=" * 80)
    # Group consecutive blanks
    if blank_tiles:
        ranges = []
        start = blank_tiles[0]
        prev = blank_tiles[0]
        for t in blank_tiles[1:]:
            if t == prev + 1:
                prev = t
            else:
                ranges.append((start, prev))
                start = t
                prev = t
        ranges.append((start, prev))
        for s, e in ranges:
            if s == e:
                print(f"  {s}")
            else:
                print(f"  {s}-{e} ({e - s + 1} tiles)")

    # Show unmatched tiles
    print("\n" + "=" * 80)
    print(f"UNMATCHED TILES ({len(unmatched_tiles)} total)")
    print("=" * 80)
    if unmatched_tiles:
        # Group consecutive
        ranges = []
        start = unmatched_tiles[0]
        prev = unmatched_tiles[0]
        for t in unmatched_tiles[1:]:
            if t == prev + 1:
                prev = t
            else:
                ranges.append((start, prev))
                start = t
                prev = t
        ranges.append((start, prev))
        for s, e in ranges:
            if s == e:
                print(f"  {s}")
            else:
                print(f"  {s}-{e} ({e - s + 1} tiles)")

        # Visualize first few unmatched
        print(f"\n  Visualizing first 10 unmatched tiles:")
        for tile_idx in unmatched_tiles[:10]:
            offset = tile_idx * TILE_SIZE
            tile_data = font[offset:offset + TILE_SIZE]
            print()
            print(visualize_tile(tile_data, f"tile {tile_idx}"))
    else:
        print("  (none)")

    # CWX range analysis (1500-1620)
    print("\n" + "=" * 80)
    print("CWX RANGE ANALYSIS (tiles 1500-1620)")
    print("=" * 80)
    for i in range(1500, min(1621, TILE_COUNT)):
        r = vd_map[i]
        if r['is_blank']:
            desc = "<blank>"
        elif r['fullwidth_char']:
            desc = f"FW:{r['fullwidth_char']}"
        elif r['left_char'] is not None and r['right_char'] is not None:
            desc = f"[{r['left_char']}|{r['right_char']}]"
        elif r['left_char'] is not None:
            desc = f"[{r['left_char']}|???]"
        elif r['right_char'] is not None:
            desc = f"[???|{r['right_char']}]"
        else:
            desc = f"<unknown:{r['match_type']}>"
        print(f"  Tile {i:4d}: {desc}")

    # Summary of VD tile map for known bigrams
    print("\n" + "=" * 80)
    print("COMPLETE VD BIGRAM MAP (tiles with both halves identified)")
    print("=" * 80)
    bigram_count = 0
    for i in range(TILE_COUNT):
        r = vd_map[i]
        if r['match_type'] == 'bigram_exact':
            l = r['left_char']
            rc = r['right_char']
            # Only print non-space bigrams or important ones
            if l != ' ' or rc != ' ':
                bigram_count += 1
    print(f"  Total bigram tiles identified: {bigram_count}")

    # Build VD's reverse map to compare structure
    print("\n" + "=" * 80)
    print("VD LOWERCASE BIGRAM GROUPS (first letter -> tile range)")
    print("=" * 80)
    lc_groups = {}
    for i in range(TILE_COUNT):
        r = vd_map[i]
        if r['match_type'] == 'bigram_exact' and r['left_char'] is not None:
            l = r['left_char']
            if l.islower() and l.isalpha():
                if l not in lc_groups:
                    lc_groups[l] = []
                lc_groups[l].append((i, r['right_char']))

    for ch in sorted(lc_groups.keys()):
        tiles = lc_groups[ch]
        if tiles:
            start = tiles[0][0]
            end = tiles[-1][0]
            rights = ''.join(rc if rc != ' ' else '_' for _, rc in tiles)
            print(f"  '{ch}': tiles {start}-{end} ({len(tiles)} tiles): {rights}")

    print("\n" + "=" * 80)
    print("VD UPPERCASE BIGRAM GROUPS (first letter -> tile range)")
    print("=" * 80)
    uc_groups = {}
    for i in range(TILE_COUNT):
        r = vd_map[i]
        if r['match_type'] == 'bigram_exact' and r['left_char'] is not None:
            l = r['left_char']
            if l.isupper() and l.isalpha():
                if l not in uc_groups:
                    uc_groups[l] = []
                uc_groups[l].append((i, r['right_char']))

    for ch in sorted(uc_groups.keys()):
        tiles = uc_groups[ch]
        if tiles:
            start = tiles[0][0]
            end = tiles[-1][0]
            rights = ''.join(rc if rc != ' ' else '_' for _, rc in tiles)
            print(f"  '{ch}': tiles {start}-{end} ({len(tiles)} tiles): {rights}")


if __name__ == '__main__':
    analyze()
