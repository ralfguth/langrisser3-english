"""Stat-tail bigram coverage — the zenkaku-fallback eradication for
item/spell descriptions (archive/docs/20260611_desc_stat_bigram_plan.md).

Centered full-width tiles (digits 7-16, uppercase 17-42) are EXPLICIT
zenkaku only: a half-width letter/digit that the greedy encoder cannot
pair must fall back to a half-width [char,space] tile, never a centered
one (memory feedback_zenkaku_centered_vs_standalone). These tests lock:

1. the stat-vocabulary pair set exists in BIGRAM_TILE_MAP;
2. the greedy walk over the canonical stat tails emits exactly the
   expected tile sequence (byte-exact vs encode_text_to_entry);
3. half-width digit singles fall back to the (d,' ') tile while zenkaku
   ０-９/Ａ-Ｚ keep the centered tiles — the "differentiate" rule;
4. every record of fntsys13/fntsys15 encodes with ZERO centered-tile
   emissions (the user-visible defect this work removes);
5. new tiles only occupy slots cleared by the free-slot audit
   (BLANK_GAP rows of the user CSV, dead-kanji tail 1667-1690,
   unsourced 1617-1620/1633);
6. glyph data for new tiles is the standard half-glyph interleave.
"""

import re
import struct
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import font_tools as ft  # noqa: E402
from d00_tools import encode_text_to_entry  # noqa: E402

# FNT_SYS surface maps: dialogue maps + digit pairs + fragment reuse.
# Dialogue (CHAR_TILE_MAP/BIGRAM_TILE_MAP) gets the letter pairs only —
# numbers in prose keep the centered zenkaku-style digits (see the
# dialogue-safety tests below).
CHAR = ft.FNTSYS_CHAR_TILE_MAP
BIG = ft.FNTSYS_BIGRAM_TILE_MAP

# ---------------------------------------------------------------------------
# 1. Pair coverage
# ---------------------------------------------------------------------------

# The hand-curated stat-bigram pair set (EVEN/ODD/SIGN/DIGIT/MISC -> ALL_NEW_PAIRS)
# and its position/sequence tests were removed by the Part 6 data-driven swap
# (2026-06-27): the data-driven font only carries the pairs the FINAL fntsys/scen
# text actually produces (e.g. "RANGE", not "RNG"), packed at fresh positions, so
# the fixed list and its tile-index assertions no longer apply. Stat-label
# coverage is now guarded by the zero-centered-fallback tests below + by
# test_fntsys_no_zenkaku_fallback / test_no_bigram_fallback.

# Pre-rendered fragments of our font reused by mapping only (no glyph
# written); they sit in the grid-spaced range 1500-1620.
FRAGMENT_REUSE_MAPS = {
    ('L', 'V'): 1528,
    ('H', 'P'): 1529,
    ('M', 'P'): 1530,
    ('0', '%'): 1568,
}


def test_fragment_reuse_maps():
    for pair, tile in FRAGMENT_REUSE_MAPS.items():
        assert BIG.get(pair) == tile, (
            f"{pair} must map to pre-rendered fragment tile {tile}, "
            f"got {BIG.get(pair)}"
        )


# ---------------------------------------------------------------------------
# 2. Byte-exact greedy walk over the canonical stat tails
# ---------------------------------------------------------------------------

def _tiles(text):
    """Encode plain text, return the emitted tile-id list."""
    raw = encode_text_to_entry(text, CHAR, BIG)
    return list(struct.unpack(f'>{len(raw)//2}H', raw))


# B()/C()/WALK_CASES/test_greedy_walk removed (Part 6 swap): the byte-exact tile
# sequences were keyed to the old hand-curated stat positions and used pairs the
# data-driven font no longer carries (e.g. RNG). _tiles (above) is kept for the
# zero-centered-fallback tests below, which validate the real fntsys stat text.


# ---------------------------------------------------------------------------
# 3. Differentiate rule: half-width fallback vs explicit zenkaku
# ---------------------------------------------------------------------------

def test_fntsys_digit_fallback_is_digit_space_tile():
    for d in '0123456789':
        assert CHAR[d] == BIG[(d, ' ')], (
            f"single half-width '{d}' must fall back to its (d,' ') tile"
        )
        assert not (7 <= CHAR[d] <= 16), (
            f"single half-width '{d}' still maps to centered tile {CHAR[d]}"
        )


def test_zenkaku_keep_centered_tiles():
    for i in range(10):
        assert CHAR[chr(0xFF10 + i)] == 7 + i      # ０-９ centered digits
    for i in range(26):
        assert CHAR[chr(0xFF21 + i)] == 17 + i     # Ａ-Ｚ centered uppercase


# ---------------------------------------------------------------------------
# Dialogue numbers: the scen/plot surface now renders numbers HALF-WIDTH too.
# The number-bigram slice gives COMPLETE 00-99 coverage (+ ?N + space/number
# boundaries), so there is no half/full mixing the old zenkaku-only rule
# guarded against. Full-width '０'-'９' (-> 7-16) stay centered, so SCENARIO
# titles remain zenkaku. (archive/docs/20260625_font_bin_grow_spike.md)
# ---------------------------------------------------------------------------

def test_dialogue_ascii_digits_are_half_width():
    """ASCII '0'-'9' -> half-width 201-210; full-width '０'-'９' stay centered
    (7-16) so SCENARIO titles remain zenkaku."""
    for i in range(10):
        assert ft.CHAR_TILE_MAP[str(i)] == 201 + i
        assert ft.CHAR_TILE_MAP[chr(0xFF10 + i)] == 7 + i


# test_dialogue_map_has_the_number_bigrams removed (Part 6 swap): the complete
# 00-99 set was a dead grow-font artifact. Engine-rendered numbers use the
# centered digits (7-16); script/template numbers pair only for the values that
# actually occur. See [[reference_engine_number_rendering]].


def test_dialogue_map_has_no_fragment_reuse():
    # The ban is on the 0.2 patch-drawn fragment TILES (provenance debt, 0.2 patch
    # style), not on the pair keys: dialogue may map the same pair to a
    # tile WE drew (e.g. (H,P)->1583, our Eagle interleave, 2026-06-12).
    for pair, frag_tile in FRAGMENT_REUSE_MAPS.items():
        assert ft.BIGRAM_TILE_MAP.get(pair) != frag_tile, (
            f"fragment tile {frag_tile} for {pair} leaked into the "
            f"dialogue map (0.2 patch-drawn glyph, fnt_sys-only reuse)"
        )


def test_dialogue_number_walk_is_half_width():
    """'5000 years' -> (5,0)(0,0)( ,y)... : all half-width number bigrams, no
    centered zenkaku digit (7-16)."""
    raw = encode_text_to_entry("5000 years", ft.CHAR_TILE_MAP,
                               ft.BIGRAM_TILE_MAP)
    tiles = list(struct.unpack(f'>{len(raw)//2}H', raw))
    assert tiles[:2] == [ft.BIGRAM_TILE_MAP[('5', '0')],
                         ft.BIGRAM_TILE_MAP[('0', '0')]]
    assert tiles[2] == ft.BIGRAM_TILE_MAP[(' ', 'y')]
    assert all(not (7 <= t <= 16) for t in tiles), f"zenkaku digit in {tiles}"


def test_halfwidth_uppercase_unchanged_for_now():
    # Full (X,' ') coverage is Phase C (FONT.BIN rebuild); until then the
    # A-Z singles keep the centered tiles. This test documents the boundary
    # so Phase C flips it deliberately.
    for i in range(26):
        assert CHAR[chr(65 + i)] == 17 + i


def test_digits_not_right_blank():
    # Dialogue digit singles are CENTERED tiles (full-width, no blank
    # half) — the space-skip rule must NOT eat the space after them.
    # On the FNT_SYS surface digit+space is a real (d,' ') BIGRAM, which
    # carries right-blank through the bigram path, not this set.
    from d00_tools import RIGHT_BLANK_STANDALONE_CHARS
    for d in '0123456789':
        assert d not in RIGHT_BLANK_STANDALONE_CHARS


# ---------------------------------------------------------------------------
# 4. Zero centered emissions across fntsys13/fntsys15
# ---------------------------------------------------------------------------

CODE_RE = re.compile(r'<\$[0-9A-Fa-f]{4,}>')


def _assert_no_centered(path):
    bad = []
    for ln, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        text = line.replace('<$FFFF>', '')
        if not text.strip():
            continue
        if any(ord(c) >= 0x3000 for c in text):
            continue  # explicit zenkaku record (none expected in 13/15)
        for seg in CODE_RE.split(text):
            for t in _tiles(seg):
                if 7 <= t <= 42:
                    bad.append((ln, seg, t))
    assert not bad, (
        f"{path.name}: centered-tile fallbacks remain "
        f"(line, segment, tile): {bad[:10]} (+{max(0, len(bad)-10)} more)"
    )


def test_fntsys13_zero_centered_fallbacks():
    _assert_no_centered(PROJ / 'scripts/en/fntsys13E.txt')


def test_fntsys15_zero_centered_fallbacks():
    _assert_no_centered(PROJ / 'scripts/en/fntsys15E.txt')


# ---------------------------------------------------------------------------
# Sections 5 (audit-cleared slot discipline) and 6 (per-pair interleave check)
# removed by the Part 6 data-driven swap: both iterated the hand-curated
# ALL_NEW_PAIRS at the old audit-cleared positions. The data-driven packing owns
# slot allocation (build_bigram_layout: only necessary pairs, off the preserved
# set — test_new_font_bigram_layout) and composes every FRESH bigram as the
# half-glyph interleave by construction (test_bigram_map_tiles_match_generated_font
# confirms none is blank), so glyph correctness now holds for ALL pairs, not just
# the stat sample.
# ---------------------------------------------------------------------------
