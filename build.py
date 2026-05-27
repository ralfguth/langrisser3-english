#!/usr/bin/env python3
"""
build.py - Build Langrisser III English Translation Patch

Single-command build pipeline that:
1. Reads the Japanese disc image
2. Extracts FONT.BIN and D00.DAT
3. Generates English font from JP FONT.BIN + embedded glyph data
4. Encodes English translation scripts into D00.DAT
5. Rebuilds ISO with larger D00.DAT (sector-shifting)
6. Assembles final CD image with audio tracks

Usage:
    python3 build.py

Requires:
    - Japanese disc image at the configured JP_DIR path
    - English translation scripts in scripts/en/

Output:
    build/Langrisser_III_English.cue  (load this in emulator)
    build/track01.bin ... track22.bin
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
    rebuild_iso_inorder, rebuild_iso_batch, assemble_cd_image, SECTOR_SIZE
)
from d00_tools import (
    parse_d00, insert_translations, rebuild_d00
)
from font_tools import (
    CHAR_TILE_MAP, BIGRAM_TILE_MAP, generate_english_font,
)
from plot_tools import (
    encode_plot_script, parse_plot, round_trip_test as plot_round_trip,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BUILD_DIR = SCRIPT_DIR / 'build'
CACHE_DIR = SCRIPT_DIR / 'cache'   # JP baseline cache (gitignored)
PATCHES_DIR = SCRIPT_DIR / 'patches'  # Menu/UI translation patches

# Language metadata. The repo is dual-purpose: an English translation patch
# AND a framework for producing Langrisser III patches in any language.
# Each language has its own scripts/<code>/ directory and a display name
# used in the output filename.
LANGUAGES = {
    'en': 'English',
    # Add new languages here as their scripts/<code>/ dirs come online.
    # 'it': 'Italian',
    # 'pt': 'Portuguese',
    # 'es': 'Spanish',
}
DEFAULT_LANG = 'en'


def _resolve_canary_cue_name(lang_display: str) -> str:
    """Canary build filename = "Langrisser ({lang} {branch-name}).cue".
    Note: NO "III" in canary names (intentional — distinguishes WIP from
    canonical at a glance). Branch name comes from git; falls back to
    "canary" if git is unavailable.
    """
    import subprocess
    try:
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=str(SCRIPT_DIR), stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        branch = 'canary'
    return f'Langrisser ({lang_display} {branch}).cue'


def _resolve_canonical_cue_name(lang_display: str) -> str:
    """Canonical filename derived from the current git state.

    If HEAD == latest tag → "Langrisser III ({lang} v<TAG>).cue".
    Else → "Langrisser III ({lang} v<TAG>+).cue" (release-candidate
    naming for uncommitted/unreleased work past the tag).
    Falls back to "Langrisser III ({lang}).cue" if git is unavailable.

    To produce the v0.6.1 stable build from the official commit:
        git checkout v0.6.1 && python3 build.py
    """
    import subprocess
    try:
        latest_tag = subprocess.check_output(
            ['git', 'describe', '--tags', '--abbrev=0'],
            cwd=str(SCRIPT_DIR), stderr=subprocess.DEVNULL,
        ).decode().strip()
        head_tag = subprocess.check_output(
            ['git', 'tag', '--points-at', 'HEAD'],
            cwd=str(SCRIPT_DIR), stderr=subprocess.DEVNULL,
        ).decode().strip().splitlines()
        ver = latest_tag.lstrip('v')
        if latest_tag in head_tag:
            return f'Langrisser III ({lang_display} v{ver}).cue'
        return f'Langrisser III ({lang_display} v{ver}+).cue'
    except Exception:
        return f'Langrisser III ({lang_display}).cue'

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

# JP disc location is contributor-specific. Set the LANG3_JP_DIR env
# var in your shell config to avoid passing --jp-iso every run.
_JP_DIR_ENV = 'LANG3_JP_DIR'


def main():
    import argparse, os
    parser = argparse.ArgumentParser(description='Build Langrisser III English Translation')
    parser.add_argument(
        '--jp-iso', type=Path, default=None,
        help='Path to Japanese disc directory (containing .cue and Track 01 .bin). '
             f'Falls back to ${_JP_DIR_ENV} env var if not given.',
    )
    parser.add_argument(
        '--canary', action='store_true',
        help='Produce a canary build with branch-name suffix instead of the '
             'tag-derived canonical name. Use for WIP / non-release builds.',
    )
    parser.add_argument(
        '--lang', default=DEFAULT_LANG, choices=sorted(LANGUAGES.keys()),
        help=f'Translation language code (default: {DEFAULT_LANG}). Picks '
             f'scripts/<lang>/ as the source directory and shapes the output '
             f'filename. Add new entries to LANGUAGES at the top of this file.',
    )
    args = parser.parse_args()
    lang_display = LANGUAGES[args.lang]
    SCRIPTS_DIR = SCRIPT_DIR / 'scripts' / args.lang
    output_cue = BUILD_DIR / (
        _resolve_canary_cue_name(lang_display) if args.canary
        else _resolve_canonical_cue_name(lang_display)
    )

    # Resolve JP disc location: CLI flag → env var → error
    env_path = os.environ.get(_JP_DIR_ENV)
    jp_dir = args.jp_iso or (Path(env_path) if env_path else None)
    if jp_dir is None:
        print(f'ERROR: JP disc directory not configured.')
        print(f'  Either pass --jp-iso /path/to/disc/directory')
        print(f'  or set the {_JP_DIR_ENV} env var (e.g. in ~/.bashrc):')
        print(f'    export {_JP_DIR_ENV}="/path/to/Langrisser III (Japan)"')
        return 1
    jp_dir = Path(jp_dir)
    if not jp_dir.exists():
        print(f'ERROR: JP disc directory not found: {jp_dir}')
        return 1

    # Find Track 01 .bin (the data track)
    track01_candidates = list(jp_dir.glob('*rack*01*.bin')) + list(jp_dir.glob('*rack*1*.bin'))
    if not track01_candidates:
        track01_candidates = list(jp_dir.glob('*.bin'))
    jp_track01 = track01_candidates[0] if track01_candidates else None

    start_time = time.time()

    print('=' * 60)
    print('  Langrisser III - English Translation Build')
    print('  by Ralf Guth - https://github.com/ralfguth/langrisser3-english')
    print('=' * 60)
    print()

    # Validate inputs
    if not jp_track01 or not jp_track01.exists():
        print(f'ERROR: No Track 01 .bin found in: {jp_dir}')
        print(f'  Expected a .bin file like "Langrisser III (Japan) (Track 01).bin"')
        return 1

    if not SCRIPTS_DIR.exists():
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
    plot_entry = file_index.get('LANG/PLOT.DAT')

    if not font_entry or not d00_entry:
        print('ERROR: Could not find FONT.BIN or D00.DAT in ISO')
        return 1

    font_data = extract_file_data(image, font_entry.extent, font_entry.size)
    d00_data = extract_file_data(image, d00_entry.extent, d00_entry.size)
    print(f'  FONT.BIN: {len(font_data):,} bytes ({len(font_data) // 32} tiles)')
    print(f'  D00.DAT:  {len(d00_data):,} bytes')

    plot_data = None
    if plot_entry:
        plot_data = extract_file_data(image, plot_entry.extent, plot_entry.size)
        print(f'  PLOT.DAT: {len(plot_data):,} bytes')

    # Save JP D00.DAT and PLOT.DAT baselines to cache/ for consumption by
    # tests (test_d00, test_plot, test_entry_counts, test_control_code_parity)
    # and audit tools (translation_audit, semantic_audit, plot_audit,
    # signature_compare, dump_jp_scripts). cache/ is gitignored — keeps
    # build/ for release artifacts only.
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / 'd00_jp.dat').write_bytes(d00_data)
    if plot_data is not None:
        (CACHE_DIR / 'plot_jp.dat').write_bytes(plot_data)

    # -- Step 3: Generate English font --
    print('[3/7] Generating English font...')
    new_font = generate_english_font(font_data)
    print(f'  English font: {len(new_font):,} bytes ({len(new_font) // 32} tiles)')

    # -- Step 4: Parse D00.DAT --
    print('[4/7] Parsing D00.DAT...')
    sections = parse_d00(d00_data)
    total_entries = sum(s.entry_count for s in sections)
    print(f'  {len(sections)} sections, {total_entries:,} entries total')

    # -- Step 5: Insert English translations --
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

    # -- Step 6: Rebuild D00.DAT and patch ISO --
    print('[6/7] Rebuilding and patching ISO...')

    # Collect all files to patch. Same-size patches are applied in-place
    # via patch_file_in_iso. Files that grow are deferred to rebuild_iso_batch
    # which shifts subsequent sectors and updates all downstream dir records.
    grown_patches = []  # list of (iso_path, new_data) for files that grew

    # FONT.BIN: same size (generate_english_font preserves 1691-tile size)
    patch_file_in_iso(image, font_entry, new_font)
    print(f'  FONT.BIN patched in place')

    # CWX menu/UI files
    if PATCHES_DIR.exists():
        patch_same_size = 0
        patch_grown = 0
        for iso_path, patch_filename in MENU_PATCHES.items():
            patch_file = PATCHES_DIR / patch_filename
            iso_entry = file_index.get(iso_path)
            if not (patch_file.exists() and iso_entry):
                continue
            patch_data = patch_file.read_bytes()
            if len(patch_data) == iso_entry.size:
                patch_file_in_iso(image, iso_entry, patch_data)
                patch_same_size += 1
            else:
                # Defer — sector-shift audit confirmed no hardcoded LBA refs
                grown_patches.append((iso_path, patch_data))
                patch_grown += 1
        print(f'  Menu/UI patches: {patch_same_size} in-place, {patch_grown} deferred (grow)')
    else:
        print(f'  WARNING: patches/ directory not found, menus remain Japanese')

    # Rebuild D00.DAT (may grow)
    new_d00 = rebuild_d00(sections, new_text_areas)
    print(f'  D00.DAT: {len(d00_data):,} -> {len(new_d00):,} bytes')
    grown_patches.append(('LANG/SCEN/D00.DAT', new_d00))

    # Rebuild PLOT.DAT from scripts/en/plotE.txt (battle prep screens).
    # Without this, the JP-encoded PLOT.DAT is read through the EN font
    # mapping → mojibake on every battle prep narration.
    plot_script = SCRIPTS_DIR / 'plotE.txt'
    if plot_entry and plot_script.exists():
        # Sanity: JP PLOT.DAT must round-trip cleanly through our parser
        plot_round_trip(plot_data)
        new_plot = encode_plot_script(plot_script, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        print(f'  PLOT.DAT: {len(plot_data):,} -> {len(new_plot):,} bytes')
        if len(new_plot) == plot_entry.size:
            patch_file_in_iso(image, plot_entry, new_plot)
            print(f'    patched in place')
        else:
            grown_patches.append(('LANG/PLOT.DAT', new_plot))
    elif plot_entry:
        print(f'  PLOT.DAT: scripts/en/plotE.txt missing - leaving JP version (mojibake!)')

    # Batch: apply all grown patches (D00.DAT + any grown MENU_PATCHES) in
    # ascending extent order. Shifts downstream sectors and updates dir records.
    image = rebuild_iso_batch(image, file_index, grown_patches)
    print(f'  ISO rebuilt: {len(image):,} bytes ({len(image) // SECTOR_SIZE} sectors)')

    # Write patched track 01
    track01_path = BUILD_DIR / 'track01.bin'
    track01_path.parent.mkdir(parents=True, exist_ok=True)
    track01_path.write_bytes(image)
    print(f'  Track 01: {len(image):,} bytes')

    # -- Step 7: Assemble CD image --
    print('[7/7] Assembling CD image...')
    assemble_cd_image(track01_path, jp_dir, output_cue)

    tracks = list(BUILD_DIR.glob('track*.bin'))
    audio_tracks = len(tracks) - 1

    elapsed = time.time() - start_time

    print()
    print('=' * 60)
    print('  BUILD COMPLETE')
    print('=' * 60)
    print(f'  Cue:          {output_cue}')
    print(f'  Track 01:     {track01_path.stat().st_size:,} bytes')
    print(f'  Audio tracks: {audio_tracks}')
    print(f'  Build time:   {elapsed:.1f}s')
    print()
    print('  To play:')
    print(f'    load {output_cue.name}')
    print()
    print('  Patch by Ralf Guth')
    print('  https://github.com/ralfguth/langrisser3-english')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
