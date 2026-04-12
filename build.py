#!/usr/bin/env python3
"""
build.py - Build Langrisser III English Translation Patch

Single-command build pipeline that:
1. Reads the Japanese disc image
2. Extracts FONT.BIN and D00.DAT
3. Generates English font tiles and patches FONT.BIN
4. Encodes English translation scripts into D00.DAT
5. Patches everything back into the ISO
6. Assembles final CD image with audio tracks

Usage:
    python3 build.py

Requires:
    - Japanese disc image at the configured JP_DIR path
    - Pillow (pip install Pillow)
    - English translation scripts in scripts/en/

Output:
    build/Langrisser_III_English.cue  (load this in emulator)
    build/tracks/track01.bin ... track22.bin
"""

import shutil
import sys
import time
from pathlib import Path

# Add tools directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / 'tools'))

from iso_tools import (
    build_file_index, extract_file_data, patch_file_in_iso,
    assemble_cd_image, SECTOR_SIZE
)
from d00_tools import (
    parse_d00, insert_translations, rebuild_d00, patch_d00_inplace
)
from font_tools import (
    CHAR_TILE_MAP, BIGRAM_TILE_MAP, generate_all_tiles, patch_font_bin,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPTS_DIR = SCRIPT_DIR / 'scripts' / 'en'
BUILD_DIR = SCRIPT_DIR / 'build'
PATCHES_DIR = SCRIPT_DIR / 'patches'  # Menu/UI translation patches

OUTPUT_CUE = BUILD_DIR / 'Langrisser_III_English.cue'

# Menu/UI patch files (same-size overlays onto JP originals)
MENU_PATCHES = {
    'A0LANG.BIN':              'a0lang.bin',         # Menu layout positions
    'LANG/FNT_SYS.BIN':       'fnt_sys.bin',        # System font (menus)
    'LANG/PROG_3.BIN':        'prog_3.bin',         # Skill names, layout
    'LANG/PROG_4.BIN':        'prog_4.bin',         # Unit class names
    'LANG/PROG_5.BIN':        'prog_5.bin',         # Item/equipment names
    'LANG/PROG_6.BIN':        'prog_6.bin',         # Battle text
    'LANG/BATTLE/SYSWIN.BIN': 'syswin.bin',         # Battle window UI
}

# Default JP disc location (can be overridden with --jp-iso)
_DEFAULT_JP_DIR = Path.home() / 'Jogos/emulacao/romsets/sega saturn/Langrisser III (Japan)'


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Build Langrisser III English Translation')
    parser.add_argument('--jp-iso', type=Path, default=None,
                        help='Path to Japanese disc directory (containing .cue and Track 01 .bin)')
    parser.add_argument('--font-only', action='store_true',
                        help='Only patch FONT.BIN, skip D00.DAT (for crash diagnosis)')
    parser.add_argument('--no-translate', action='store_true',
                        help='Rebuild D00.DAT with JP text only (test relocation)')
    args = parser.parse_args()

    # Resolve JP disc location
    jp_dir = args.jp_iso or _DEFAULT_JP_DIR
    jp_dir = Path(jp_dir)
    if not jp_dir.exists():
        print(f'ERROR: Japanese disc directory not found: {jp_dir}')
        print(f'  Use --jp-iso /path/to/disc/directory')
        return 1

    # Find Track 01 .bin (the data track)
    track01_candidates = list(jp_dir.glob('*rack*01*.bin')) + list(jp_dir.glob('*rack*1*.bin'))
    if not track01_candidates:
        track01_candidates = list(jp_dir.glob('*.bin'))
    jp_track01 = track01_candidates[0] if track01_candidates else None

    start_time = time.time()

    print('=' * 60)
    print('  Langrisser III - English Translation Build')
    if args.font_only:
        print('  ** FONT-ONLY MODE (no D00.DAT changes) **')
    elif args.no_translate:
        print('  ** NO-TRANSLATE MODE (D00.DAT relocated, JP text) **')
    print('=' * 60)
    print()

    # Validate inputs
    if not jp_track01 or not jp_track01.exists():
        print(f'ERROR: No Track 01 .bin found in: {jp_dir}')
        print(f'  Expected a .bin file like "Langrisser III (Japan) (Track 01).bin"')
        return 1

    if not args.font_only and not SCRIPTS_DIR.exists():
        print(f'ERROR: No translation scripts found in {SCRIPTS_DIR}')
        return 1

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # -- Step 1: Read Japanese ISO --
    print('[1/7] Reading Japanese ISO...')
    image = bytearray(jp_track01.read_bytes())
    print(f'  Track 01: {len(image):,} bytes ({len(image) // SECTOR_SIZE} sectors)')

    # -- Step 2: Extract key files --
    print('[2/7] Extracting game files...')
    file_index = build_file_index(image)

    font_entry = file_index.get('LANG/FONT.BIN')
    d00_entry = file_index.get('LANG/SCEN/D00.DAT')

    if not font_entry or not d00_entry:
        print('ERROR: Could not find FONT.BIN or D00.DAT in ISO')
        return 1

    font_data = extract_file_data(image, font_entry.extent, font_entry.size)
    d00_data = extract_file_data(image, d00_entry.extent, d00_entry.size)
    print(f'  FONT.BIN: {len(font_data):,} bytes ({len(font_data) // 32} tiles)')
    print(f'  D00.DAT:  {len(d00_data):,} bytes')

    # -- Step 3: Generate English font --
    print('[3/7] Generating English bigram font...')
    tiles = generate_all_tiles()
    new_font = patch_font_bin(font_data, tiles)
    print(f'  Generated {len(tiles)} tiles onto JP base ({len(new_font):,} bytes)')
    print(f'  Bigram map: {len(BIGRAM_TILE_MAP)} pairs, Single map: {len(CHAR_TILE_MAP)} chars')

    # -- Step 4: Parse D00.DAT --
    if not args.font_only:
        print('[4/7] Parsing D00.DAT...')
        sections = parse_d00(d00_data)
        total_entries = sum(s.entry_count for s in sections)
        print(f'  {len(sections)} sections, {total_entries:,} entries total')
    else:
        print('[4/7] Skipping D00.DAT parse (font-only mode)')

    # -- Step 5: Insert English translations --
    if not args.font_only and not args.no_translate:
        print('[5/7] Encoding English translations...')
        new_text_areas, stats = insert_translations(
            sections, SCRIPTS_DIR, CHAR_TILE_MAP, BIGRAM_TILE_MAP, verbose=False
        )

        print(f'  Translated: {stats["translated"]} sections')
        print(f'  Skipped:    {stats["skipped"]} sections')
        if stats['entry_count_mismatches']:
            print(f'  Entry count adjustments: {len(stats["entry_count_mismatches"])}')
        if stats['errors']:
            for err in stats['errors']:
                print(f'  WARNING: {err}')
    elif args.no_translate:
        print('[5/7] Skipping translations (no-translate mode)')
        new_text_areas = {}
    else:
        print('[5/7] Skipping translations (font-only mode)')

    # -- Step 6: Rebuild D00.DAT and patch ISO --
    print('[6/7] Rebuilding and patching ISO...')

    # Patch FONT.BIN into ISO (same size, in-place)
    patch_file_in_iso(image, font_entry, new_font)
    print(f'  FONT.BIN patched in place')

    # Patch CWX menu/UI files (all same size, in-place)
    if PATCHES_DIR.exists():
        patch_count = 0
        for iso_path, patch_filename in MENU_PATCHES.items():
            patch_file = PATCHES_DIR / patch_filename
            iso_entry = file_index.get(iso_path)
            if patch_file.exists() and iso_entry:
                patch_data = patch_file.read_bytes()
                if len(patch_data) == iso_entry.size:
                    patch_file_in_iso(image, iso_entry, patch_data)
                    patch_count += 1
                else:
                    print(f'  WARNING: {patch_filename} size mismatch, skipping')
        print(f'  Menu/UI patches: {patch_count} files (menus/UI/skills)')
    else:
        print(f'  WARNING: patches/ directory not found, menus remain Japanese')

    if not args.font_only:
        # Patch D00.DAT in-place (same size, no relocation)
        # Game uses direct sector access — D00.DAT MUST stay at original extent
        patched_d00, num_patched, num_skipped = patch_d00_inplace(
            d00_data, sections, new_text_areas
        )
        print(f'  D00.DAT: {num_patched} sections patched, {num_skipped} kept JP (too large)')
        print(f'  D00.DAT: {len(patched_d00):,} bytes (same as original)')

        # Write patched D00.DAT back into ISO at original location
        patch_file_in_iso(image, d00_entry, patched_d00)
    else:
        print(f'  D00.DAT: unchanged (font-only mode)')

    # Write patched track 01
    track01_path = BUILD_DIR / 'tracks' / 'track01.bin'
    track01_path.parent.mkdir(parents=True, exist_ok=True)
    track01_path.write_bytes(image)
    print(f'  Track 01: {len(image):,} bytes')

    # -- Step 7: Assemble CD image --
    print('[7/7] Assembling CD image...')
    assemble_cd_image(track01_path, jp_dir, OUTPUT_CUE)

    tracks = list((BUILD_DIR / 'tracks').glob('track*.bin'))
    audio_tracks = len(tracks) - 1

    elapsed = time.time() - start_time

    print()
    print('=' * 60)
    print('  BUILD COMPLETE')
    print('=' * 60)
    print(f'  Output:       {OUTPUT_CUE}')
    print(f'  Track 01:     {track01_path.stat().st_size:,} bytes')
    print(f'  Audio tracks: {audio_tracks}')
    print(f'  Build time:   {elapsed:.1f}s')
    print()
    print('  To play: load Langrisser_III_English.cue in')
    print('  RetroArch + Beetle Saturn (or Mednafen)')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
