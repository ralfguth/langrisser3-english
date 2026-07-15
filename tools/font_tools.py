#!/usr/bin/env python3
"""
font_tools.py - Tile maps for Langrisser III Saturn English translation (0.2-patch font).

Defines CHAR_TILE_MAP and BIGRAM_TILE_MAP that map characters and character pairs
to tile indices in the 0.2-patch English font (ENFONT2.BIN).

Tile layout follows 0.2 patch's v0.2 translation patch tile map, which 0.2 patch
adopted. 0.2 patch's font has specific differences from 0.2 patch's original documentation:
  - LC bigram position 27 is period (.) not apostrophe (')
  - Tiles 43-45 are full-width lowercase a, m, p (not custom slots)
  - Apostrophe bigrams at tiles 1491-1500 (10 pairs: o' n' s' t' u' y' 'r 's 't 'v)
  - Space+letter bigrams at tiles 1435-1487 (52 pairs)
  - Punctuation bigrams at tiles 907-910 (?? ?! !! !?)
  - Double-quote at tile 1470

FONT.BIN format: 1691 tiles x 32 bytes each (16x16 1bpp, MSB=leftmost).
The English font GROWS past 1691 with appended bigram tiles (growth proven
in-game 2026-06-25 — archive/docs/20260625_font_bin_grow_spike.md).
"""

import re
import string
from pathlib import Path

# ---------------------------------------------------------------------------
# Tile layout (tile index assignments for bigram groups)
# ---------------------------------------------------------------------------

# Lowercase bigram groups: each letter has a consecutive block of tile slots.
# Groups with UI offsets (m, p, y) span more than 31 slots to fit 31 right chars.
_LC_STARTS = {
    'a': 46,  'b': 77,  'c': 108, 'd': 139, 'e': 170,
    'f': 214, 'g': 245, 'h': 276, 'i': 335, 'j': 374,
    'k': 405, 'l': 436, 'm': 467, 'n': 500, 'o': 531,
    'p': 562, 'q': 594, 'r': 625, 's': 656, 't': 687,
    'u': 718, 'v': 749, 'w': 780, 'x': 811, 'y': 842,
    'z': 875,
}

# 0.2 patch's right-char sequence for LC bigrams.
# Position 27 is PERIOD (.), not apostrophe — this matches 0.2 patch's actual font.
_LC_RIGHT_FULL = [' '] + list('abcdefghijklmnopqrstuvwxyz') + ['.', ',', '?', '!']

# UI/decoration tiles at specific offsets within bigram groups.
# These tiles are used by the game engine and must NOT be overwritten.
_LC_UI_OFFSETS = {
    'm': {15, 22},   # tiles 482, 489
    'p': {4},        # tile 566
    'v': {17},       # tile 766 — UI tile, vq bigram does not exist
    'y': {18, 19},   # tiles 860, 861
}

# Characters absent from specific LC groups (UI tile occupies their slot
# and 0.2 patch's font has no replacement tile for that bigram).
_LC_MISSING_CHARS = {
    'v': {'q'},  # tile 766 is UI; vq bigram does not exist in 0.2-patch font
}

# Uppercase bigram groups: variable size, right chars from analysis.
_UC_GROUPS = {
    'A': (914,  [' ','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'B': (941,  ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'C': (967,  ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w',' ','y','z']),
    'D': (993,  ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'E': (1019, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','x','y','z']),
    'F': (1045, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','u','v','w','x','y','z']),
    'G': (1071, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'H': (1097, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y']),
    'I': (1122, [' ','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'J': (1149, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'K': (1175, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'L': (1201, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'M': (1227, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'N': (1253, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','y']),
    'O': (1278, [' ','a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'P': (1305, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'Q': (1331, ['a','e','h','i','o','u','w']),
    'R': (1338, ['a','e','h','i','l','n','o','u','y']),
    'S': (1347, ['a','e','h','i','k','l','m','n','o','p','q','r','t','u','v','w','y']),
    'T': (1364, ['a','e','h','i','o','r','w','y']),
    'U': (1372, ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']),
    'V': (1398, ['a','e','h','i','l','o','r','u','y']),
    'W': (1407, ['a','e','h','i','o','r','u','y']),
    'X': (1415, ['a','e','i','o','u','y']),
    'Y': (1421, ['a','e','g','h','i','o','u']),
    'Z': (1428, ['a','e','h','i','o','u','y']),
}

_UC_UI_OFFSETS = {
    'E': {22},   # tile 1041
    'F': {19},   # tile 1064
    'N': {23},   # tile 1276
}

# ---------------------------------------------------------------------------
# 0.2 patch special tile indices (present in 0.2 patch's ENFONT2.BIN font)
# ---------------------------------------------------------------------------

ELLIPSIS_TILE = 906          # … two-dot ellipsis (tile 906)
DQUOTE_TILE = 1470           # " double-quote (tile 1470)

# Apostrophe bigrams — one group (the font has no standalone ' tile, so every
# apostrophe is encoded as a 2-char tile we draw via _interleave). Two index
# ranges, same group: 1491-1499 (original) + 1621-1626 (kanji-area additions
# that unlocked I'll/I'm/I'd/who's/he's). All drawn by us; disjoint keys.
_APOSTROPHE_BIGRAMS = {
    ('d', "'"): 1491, ('n', "'"): 1492, ('s', "'"): 1493,
    ('t', "'"): 1494, ('u', "'"): 1495, ('y', "'"): 1496,
    ("'", 'r'): 1497, ("'", 's'): 1498, ("'", 't'): 1499,
    ('I', "'"): 1621,   # I'll, I'm, I'd
    ("'", 'l'): 1622,   # I'll, he'll, she'll, we'll, they'll
    ("'", 'm'): 1623,   # I'm
    ("'", 'd'): 1624,   # I'd, he'd, she'd, we'd, they'd
    ('o', "'"): 1625,   # who's, who'd
    ('e', "'"): 1626,   # he's (when greedy encoder consumes e alone)
}

# 0.2 patch space+letter bigrams (tiles 1435-1487)
# Encode " a" through " z" and " A" through " Z" as single tiles.
_SPACE_LETTER_BIGRAMS = {}
for _i, _ch in enumerate('abcdefghijklmnopqrstuvwxyz'):
    _SPACE_LETTER_BIGRAMS[(' ', _ch)] = 1435 + _i       # 1435-1460
for _i, _ch in enumerate('ABCDEFGHI'):
    _SPACE_LETTER_BIGRAMS[(' ', _ch)] = 1461 + _i       # 1461-1469
# tile 1470 = DQUOTE_TILE (not a space+letter bigram)
_SPACE_LETTER_BIGRAMS[(' ', 'J')] = 1471
_SPACE_LETTER_BIGRAMS[(' ', 'K')] = 1472
_SPACE_LETTER_BIGRAMS[(' ', 'L')] = 1473
for _i, _ch in enumerate('MNOPQRSTUVWXYZ'):
    _SPACE_LETTER_BIGRAMS[(' ', _ch)] = 1474 + _i       # 1474-1487

# 0.2 patch punctuation double-bigrams (tiles 907-910)
_PUNCT_BIGRAMS = {
    ('?', '?'): 907, ('?', '!'): 908, ('!', '!'): 909, ('!', '?'): 910,
}

# 0.2 patch special bigrams (already in 0.2-patch font at these tile indices)
_SPECIAL_BIGRAMS = {
    ("'", 'v'): 1500,
    # 0.2 patch-area name-input umlaut bigrams. Tiles pre-rendered in the
    # original font for the name-input grid screen — reused by the
    # encoder for character/place names that carry diaeresis.
}

# Custom umlaut bigrams in the kanji area (slots 1659-1664). Built by
# interleaving our letter glyphs with our umlaut half-glyphs. Placed
# outside the 0.2 patch range (1500-1620) because the engine renders 0.2 patch-area
# tiles with name-input-grid spacing (visible gap between adjacent
# tiles) which is wrong for dialogue text. The 0.2 patch slots themselves
# remain available for menu/UI usage (Eagle-modified glyphs).
_CUSTOM_UMLAUT_BIGRAMS = {
    ('m', 'ü'): 1659,   # "Altemüller"
    ('g', 'ü'): 1660,   # "Rigüler"
    ('h', 'ä'): 1661,   # "Diehärte"
    ('ä', 'r'): 1662,   # "härte" tail
    ('B', 'ö'): 1663,   # "Böser"
    ('ö', 's'): 1664,   # "Böser" tail
    # Umlaut-LEFT bigrams — needed when text leading parity shifts the
    # umlaut to an odd position and the encoder picks (prev, umlaut)
    # FROM the right side, leaving the umlaut orphan. Greedy then has
    # no choice but standalone tile 1658 → in-game "Rigü ler" gap.
    ('ü', 'l'): 1665,   # "Rigüler" / "Altemüller" tail (orphan ü + l)
}

# All 0.2 patch pre-existing tile indices — the 1500-1620 range is used by 0.2 patch menu
# patches (a0lang.bin, syswin.bin, prog files) for stat labels, menu text, etc.
_GRID_SPACED_RANGE = set(range(1500, 1621))


# ---------------------------------------------------------------------------
# Embedded glyph bitmaps (8px wide, 16 rows, 1 byte/row = 16 bytes each)
# Reference data extracted from 0.2 patch v0.2 font. Used by tests to verify
# glyph data integrity, not by the build pipeline.
# ---------------------------------------------------------------------------

_LETTER_GLYPHS = {
    'a': bytes.fromhex('000000000000780c7ccccccc76000000'),
    'b': bytes.fromhex('000000e060607c6666666676dc000000'),
    'c': bytes.fromhex('0000000000007cc6c0c0c0c67c000000'),
    'd': bytes.fromhex('0000001c0c0c7cccccccccdc76000000'),
    'e': bytes.fromhex('0000000000007cc6c6fec0c67c000000'),
    'f': bytes.fromhex('0000001c363230783030303078000000'),
    'g': bytes.fromhex('00000000000076cccccccccc7c0ccc78'),
    'h': bytes.fromhex('000000e060607c6666666666e6000000'),
    'i': bytes.fromhex('0000001818003818181818183c000000'),
    'j': bytes.fromhex('0000000606000e06060606060666663c'),
    'k': bytes.fromhex('000000e0606066666c786c66e6000000'),
    'l': bytes.fromhex('0000003818181818181818183c000000'),
    'm': bytes.fromhex('000000000000ecfed6d6d6c6c6000000'),
    'n': bytes.fromhex('000000000000dc666666666666000000'),
    'o': bytes.fromhex('0000000000007cc6c6c6c6c67c000000'),
    'p': bytes.fromhex('000000000000dc66666666667c6060f0'),
    'q': bytes.fromhex('00000000000076cccccccccc7c0c0c1e'),
    'r': bytes.fromhex('000000000000dc7666606060f0000000'),
    's': bytes.fromhex('0000000000007cc6c07c06c67c000000'),
    't': bytes.fromhex('000000103030fc30303030361c000000'),
    'u': bytes.fromhex('000000000000cccccccccccc76000000'),
    'v': bytes.fromhex('000000000000c6c6c6c66c3810000000'),
    'w': bytes.fromhex('000000000000c6c6d6d6d6fe6c000000'),
    'x': bytes.fromhex('000000000000c6ee7c387ceec6000000'),
    'y': bytes.fromhex('000000000000c6c6c6c6c6c67e0c1870'),
    'z': bytes.fromhex('000000000000fe8c183060c2fe000000'),
    'A': bytes.fromhex('00000010387ceec6c6c6fec6c6000000'),
    'B': bytes.fromhex('000000fc6666667c66666666fc000000'),
    'C': bytes.fromhex('0000003c66c2c0c0c0c0c2663c000000'),
    'D': bytes.fromhex('000000f86c6666666666666cf8000000'),
    'E': bytes.fromhex('000000fe6662687868606266fe000000'),
    'F': bytes.fromhex('000000fe6662687868606060f0000000'),
    'G': bytes.fromhex('0000003c66c2c0c0cec6c66e3a000000'),
    'H': bytes.fromhex('000000c6c6c6c6fec6c6c6c6c6000000'),
    'I': bytes.fromhex('0000003c18181818181818183c000000'),
    'J': bytes.fromhex('0000001e0c0c0c0c0ccccccc78000000'),
    'K': bytes.fromhex('000000e6666c6c786c6c6666e6000000'),
    'L': bytes.fromhex('000000f06060606060606266fe000000'),
    'M': bytes.fromhex('000000c6eefefed6d6d6c6c6c6000000'),
    'N': bytes.fromhex('000000c6e6e6f6f6dedececec6000000'),
    'O': bytes.fromhex('0000007cc6c6c6c6c6c6c6c67c000000'),
    'P': bytes.fromhex('000000fc666666667c606060f0000000'),
    'Q': bytes.fromhex('000000386cc6c6c6c6c6de7e3c0c0e00'),
    'R': bytes.fromhex('000000fc666666667c6c6666f6000000'),
    'S': bytes.fromhex('0000007cc6c6c0701c06c6c67c000000'),
    'T': bytes.fromhex('0000007e7e5a1818181818183c000000'),
    'U': bytes.fromhex('000000c6c6c6c6c6c6c6c6c67c000000'),
    'V': bytes.fromhex('000000c6c6c6c6c6c6c67c3810000000'),
    'W': bytes.fromhex('000000c6c6c6d6d6d6d6fe6c6c000000'),
    'X': bytes.fromhex('000000c6c66c6c38386c6cc6c6000000'),
    'Y': bytes.fromhex('000000666666667e3c1818183c000000'),
    'Z': bytes.fromhex('000000fec6860c183060c2c6fe000000'),
}

# Full 32-byte tiles for digits (they span the full 16px width)
_DIGIT_TILES = {
    '0': bytes.fromhex('000000000000038006c00c600ce00de00f600e600c6006c00380000000000000'),
    '1': bytes.fromhex('00000000000001800380078001800180018001800180018003c0000000000000'),
    '2': bytes.fromhex('00000000000007c00c60006000c00180030006000c600c600fe0000000000000'),
    '3': bytes.fromhex('00000000000007e0046000c0018003c0006000600060066003c0000000000000'),
    '4': bytes.fromhex('00000000000001c001c003c003c006c006c00cc00fe000c001e0000000000000'),
    '5': bytes.fromhex('0000000000000fc00c000c000f800cc00060006008600cc00780000000000000'),
    '6': bytes.fromhex('00000000000003c006000c000f800ec00c600c600c6006c00380000000000000'),
    '7': bytes.fromhex('0000000000000fe00c60006000c000c001800180030003000300000000000000'),
    '8': bytes.fromhex('00000000000007c00c600c600c6007c00c600c600c600c6007c0000000000000'),
    '9': bytes.fromhex('000000000000038006c00c600c600c6006e003e0006000c00780000000000000'),
}

# 8w half-glyphs of digits — used by 0.2 patch-range bigram overrides for tiles
# like (' ', '2'), ('+', '8'), ('1', '5'), etc. that pair a digit with
# another half-glyph in a 16x16 cell.
_DIGIT_HALF_GLYPHS = {
    '0': bytes.fromhex('000000386cc6cedef6e6c66c38000000'),
    '1': bytes.fromhex('0000001838781818181818183c000000'),
    '2': bytes.fromhex('0000007cc6060c183060c6c6fe000000'),
    '3': bytes.fromhex('0000007e460c183c060606663c000000'),
    '4': bytes.fromhex('0000001c1c3c3c6c6cccfe0c1e000000'),
    '5': bytes.fromhex('000000fcc0c0f8cc060686cc78000000'),
    '6': bytes.fromhex('0000003c60c0f8ecc6c6c66c38000000'),
    '7': bytes.fromhex('000000fec6060c0c1818303030000000'),
    '8': bytes.fromhex('0000007cc6c6c67cc6c6c6c67c000000'),
    '9': bytes.fromhex('000000386cc6c6c66e3e060c78000000'),
}

# Lowercase umlauts (a/o/u-diaeresis) — appear in 0.2 patch-range bigrams.
_UMLAUT_HALF_GLYPHS = {
    'ä': bytes.fromhex('000000cccc00780c7ccccccc76000000'),
    'ö': bytes.fromhex('000000c6c6007cc6c6c6c6c67c000000'),
    'ü': bytes.fromhex('000000cccc00cccccccccccc76000000'),
}

_PUNCT_GLYPHS = {
    ':': bytes.fromhex('00000000000018180000001818000000'),
    ';': bytes.fromhex('00000000000018180000001818300000'),
    ',': bytes.fromhex('00000000000000000000001818300000'),
    '.': bytes.fromhex('00000000000000000000001818000000'),
    '?': bytes.fromhex('0000007cc6c60c0c1818001818000000'),
    '!': bytes.fromhex('000000183c3c3c181818001818000000'),
}

# Extended half-width punctuation glyphs (8px left, blank right).
# Script coverage audit showed these chars appear in scripts but had no tile.
# Installed at tile slots 1627+ (kanji area, previously JP glyphs).
_EXTRA_PUNCT_GLYPHS = {
    '-': bytes.fromhex('00000000000000007e7e000000000000'),
    '+': bytes.fromhex('00000000000018187e7e181800000000'),
    '(': bytes.fromhex('00000c181830303030303018180c0000'),
    ')': bytes.fromhex('00003018180c0c0c0c0c0c1818300000'),
    '/': bytes.fromhex('00000006060c0c181830306060000000'),
    # Half-width asterisk. No longer used as a STANDALONE tile (the '*' char
    # maps to the JP full-width star at tile 489 — see build_char_tile_map),
    # but still needed as a half-glyph for the 0.2 patch UI bigrams "**"/"n*"/"* "
    # (tiles 1570-1572, e.g. "****Caution****").
    '*': bytes.fromhex('00001092543854921000000000000000'),
    '%': bytes.fromhex('000000e6a6ec0c181830376567000000'),
    '[': bytes.fromhex('0000003c30303030303030303c000000'),
    ']': bytes.fromhex('0000003c0c0c0c0c0c0c0c0c3c000000'),
    "'": bytes.fromhex('00000018183000000000000000000000'),
    '&': bytes.fromhex('000000386c6c3876dcdccccc76000000'),
    # Bullet for ・-style bullet points. Glyph mirrors the right-half
    # bullet used in the (" ", "•") bigram at tile 1656.
    '•': bytes.fromhex('00000000000000183c3c180000000000'),
}

# Full-width punctuation glyphs (32 bytes = full 16x16 tile, not interleaved
# with a blank half). Used when a char must span the entire tile cell to
# match JP visual width — e.g. '-' in "SCENARIO-NN" must mirror JP ‐ which
# centers the hyphen across the full 16-pixel cell.
_FULL_WIDTH_PUNCT_GLYPHS = {
    # 8-pixel horizontal bar centered on rows 7-8 (cols 4-11). Mirrors JP
    # ‐ at tile 0x0174 (single-row hyphen) but doubled for stroke weight.
    '-': bytes.fromhex(
        '00000000000000000000000000000000'   # rows 0-7
        '0FF0'                               # row 8: cols 4-11
        '0FF0'                               # row 9: cols 4-11 (double thickness)
        '000000000000000000000000'           # rows 10-15
    ),
    # 2x2 dot centered at cols 7-8, rows 7-8. Mirrors JP ・ at tile 0x00D9
    # exactly (same pixel positions). Standalone left-half glyph was off-
    # center; full-width version sits where the eye expects it.
    '•': bytes.fromhex(
        '00000000000000000000'               # rows 0-4 (10 bytes)
        '03c0'                               # row  5: cols 6-9  (..####..)
        '07e0' '07e0' '07e0' '07e0'          # rows 6-9: cols 5-10 (.######.)
        '03c0'                               # row 10: cols 6-9  (..####..)
        '00000000000000000000'               # rows 11-15 (10 bytes)
    ),
}

# Tile slot assignments for extended punctuation (kanji area, safe to overwrite)
_EXTRA_PUNCT_TILES = {
    '-': 1627,
    '+': 1628,
    '(': 1629,
    ')': 1631,   # 1630 is blanked (orphan slot); ')' lives at 1631
    '/': 1632,
    '%': 1634,
    '[': 1635,
    ']': 1636,
    "'": 1637,
    '&': 1638,
    '•': 1657,   # standalone bullet (kanji slot at font tail)
    'ü': 1658,   # standalone u-diaeresis (Rigüler in non-"gü" contexts)
}

# Formation-icon glyphs (fntsys1 records 98-102, referenced as (X) in the scen001
# tutorial). These are JP-font glyphs we PRESERVE verbatim — generate_english_font
# never repaints tiles 0x014A-0x014E — so the encoder maps the readable glyph
# straight to its JP slot instead of forcing an absolute <$014A> control code into
# the script. CSV truth: font_tile_map_complete.csv rows 330-334 (Formation
# SQUARE/COLUMN/LINE/DIAGONAL-L/DIAGONAL-R). When the font is refactored these
# indices may move; tests/test_fntsys_formation.py validates each glyph→tile
# mapping still lands on the expected (nonzero, JP-preserved) formation glyph.
_FORMATION_GLYPH_TILES = {
    '囗': 0x014A,   # SQUARE  (basic formation)
    '｜': 0x014B,   # COLUMN  (vertical)
    '―': 0x014C,   # LINE    (horizontal)
    '＼': 0x014D,   # DIAGONAL-LEFT
    '／': 0x014E,   # DIAGONAL-RIGHT
}

# Extra bigram tiles — top frequency pairs missing from 0.2-patch font.
# Installed in kanji area tiles 1639+. Encoder uses these automatically
# (via BIGRAM_TILE_MAP), reducing fallback singles on scream/shout SFX
# and stat-abbreviation contexts.
_EXTRA_BIGRAM_TILES = {
    # Doubled letters (SFX: GYAAA, GOOOO, BOOOOHH, BUURR)
    ('A', 'A'): 1639,
    ('O', 'O'): 1640,
    ('U', 'U'): 1641,
    ('H', 'H'): 1642,
    # Uppercase + exclamation (scream endings)
    ('A', '!'): 1643,
    ('H', '!'): 1644,
    ('N', '!'): 1645,
    # SFX prefixes (GUAA, GOON, GAAA, GYAA, YAAA, AHAHA)
    ('G', 'U'): 1646,
    ('G', 'O'): 1647,
    ('G', 'A'): 1648,
    ('G', 'Y'): 1649,
    ('Y', 'A'): 1650,
    ('A', 'H'): 1651,
    # Stat abbreviations
    ('A', 'T'): 1652,
    ('D', 'F'): 1653,
    # Quote + space bigrams — eliminates visual gap that standalone " leaves
    (' ', '"'): 1654,   # space+dquote — opening quote in " quoted text"
    ('"', ' '): 1655,   # dquote+space — closing quote before whitespace
    # All-caps bigram drawn in OUR EagleIII style at a free kanji slot (NOT the
    # 0.2 patch 1276/1656 copies, which are 0.2 patch-style / collide with space-bullet).
    # Fixes "NPC" rendering as 3 full-width centered letters: NPC -> (N,P)+(C, ).
    ('N', 'P'): 1666,
    # Dialogue emphasis "*GRIN*!" (scen107, JP ニヤリ！): GR + IN(311).
    # Slot 1582 is an UNMAPPED dead-kanji slot (CSV empty-source); the old
    # "1500-1620 grid-spacing in dialogue" caveat is OBSOLETE per the user
    # note of 2026-06-09 (20260609_fntsys_systems_and_encoder.md) — it was
    # a 0.2 patch-binary artifact, and engine+font now build from JP originals.
    ('G', 'R'): 1582,
    # "HP" in dialogue prose (scen001 tutorial "regain some HP,"; scen038
    # stat-up "X's HP rose by 1!") — stat abbreviations are ASCII
    # half-width everywhere (user 2026-06-12). Slot 1583 = UNMAPPED
    # dead-kanji sibling of 1582. "MP" needs no pair: every occurrence
    # sits in ( ,M)(P, ) parity. No (P,'!') pair on purpose — it would
    # half-pair the tail of "500P!"/"ZAPP!" mid-word (scen039/041).
    ('H', 'P'): 1583,
}

# Stat-tail bigrams (2026-06-11, archive/docs/20260611_desc_stat_bigram_plan.md).
# Item/spell descriptions carry stat tails (ATK+6, DEF+1 RNG+5, ...) whose
# unpaired uppercase letters and digits fell back to the CENTERED full-width
# tiles (7-42) — those are explicit-zenkaku-only. This set covers the
# all-caps stat vocabulary in BOTH greedy parities (a token lands odd after
# a 2-digit number, whose last tile has no right-blank to eat the space).
# Slots come from the free-slot audit: CSV BLANK_GAP rows (blank in the JP
# font itself — zero-risk), the dead-kanji tail 1667-1690, and unsourced
# 1617-1620/1633. fnt_sys keyboard (lookup tiles 0-86, ADV/BAK/END
# 1488-1490) and scen107's full-width （） 369/373 stay untouched.
_STAT_BIGRAM_TILES = {
    (' ', '/'): 211,    # " /m.res"-style tail annotations
    # --- even-parity letter pairs, BLANK_GAP 307-329 ---
    ('D', 'E'): 307, ('F', '+'): 308, ('F', '-'): 309, ('F', ' '): 310,
    ('I', 'N'): 311, ('T', '+'): 312, ('T', ' '): 313,
    ('R', 'N'): 314, ('G', '+'): 315,
    ('M', 'O'): 316, ('V', '+'): 317, ('V', '-'): 318,
    ('M', 'R'): 319, ('E', 'S'): 320, ('S', '+'): 321, ('S', '-'): 322,
    ('A', 'R'): 323, ('E', 'A'): 324, ('A', '+'): 325,
    ('P', '+'): 326, ('P', ' '): 327,
    ('S', 'T'): 328, ('R', '+'): 329,
    # --- odd-parity pairs, BLANK_GAP 366-368 + 911-912, unsourced 1617-1620 ---
    ('V', 'I'): 366, ('T', 'K'): 367, ('E', 'F'): 368,
    ('N', 'T'): 911, ('N', 'G'): 912,
    ('O', 'V'): 1617, ('R', 'E'): 1618, ('T', 'R'): 1619, ('I', 'T'): 1620,
    ('d', '-'): 1633,   # odd-parity "( A)mod-2" — d orphaned before '-'
    # --- BLANK_GAP 43/45 + dead full-width-& 913: word-body gaps found in
    # the description sweep (rule: word-body bigrams must not be missing) ---
    ('T', 'u'): 43,     # "Turn undead" (fntsys13/15 spell prose)
    ('V', ' '): 45,     # "Halve MOV /max 50" — V before space
    ('S', 'c'): 913,    # "Scathach" (fntsys10/13 + scen031 dialogue)
    # --- ATK family, dead-kanji tail 1687-1690 ---
    ('K', '+'): 1687, ('K', '-'): 1688, ('R', ' '): 1689, ('K', ' '): 1690,
}

# Digit-involving pairs are FNT_SYS-SURFACE-ONLY (FNTSYS_BIGRAM_TILE_MAP).
# In dialogue/plot, numbers keep the centered zenkaku-style digits 7-16 —
# partial pair coverage would otherwise mix half- and full-width INSIDE a
# number the set doesn't cover ("5000" -> centered,centered,centered,[0 ]).
# In the FNT_SYS string sections (descriptions, labels, spell lists) the
# number inventory is closed (single digits, 10-13,15,25,30,50) so the
# coverage is total and every stat tail renders uniformly half-width.
_DIGIT_PAIR_TILES = {
    # (d,' ') half-width standalones, BLANK_GAP 201-210. Also the FNT_SYS
    # single-digit fallback; explicit zenkaku ０-９ keep centered 7-16.
    **{(str(d), ' '): 201 + d for d in range(10)},
    # sign+digit and digit pairs, dead-kanji tail 1667-1686
    **{('+', str(d)): 1666 + d for d in range(1, 10)},      # 1667-1675
    ('-', '1'): 1676, ('-', '2'): 1677, ('-', '4'): 1678, ('5', '0'): 1679,
    ('1', '0'): 1680, ('1', '1'): 1681, ('1', '2'): 1682, ('1', '3'): 1683,
    ('1', '5'): 1684, ('2', '5'): 1685, ('3', '0'): 1686,
    # FNT_SYS-only letter pairs in the grid-spaced range (1500-1620 of
    # OUR font): the engine's DIALOGUE pipeline renders these tile indices
    # with name-input-grid spacing, so pairs here are fnt_sys-only —
    # FNT_SYS boxes render them normally (fntsys15 proves it today).
    ('K', ','): 1575,   # "ATK,DEF" — fntsys15 spell-list only
    ('R', 'A'): 1576,   # "RANGE+N" — fntsys13 staff/bow tails (user call:
    ('E', '+'): 1577,   # spell out RANGE instead of RNG; always even-parity)
    ('L', 'O'): 1578,   # LOAD — battle map + prep menu labels, half-width
    ('A', 'D'): 1579,   #   caps (zenkaku is explicit-only, never fallback)
    ('S', 'A'): 1580,   # SAVE
    ('V', 'E'): 1581,
}

# Number bigrams (data-driven complete set, slice 1 — archive/docs/
# 20260625_font_bin_grow_spike.md). Half-width digit pairs + secret-chapter ?N +
# space-led number boundaries, so numbers never fall back to the centered zenkaku
# digits (7-16) or pad with a <$0000> filler. APPENDED past tile 1691 (the font
# grows; growth proven in-game). DIALOGUE surface (added to BIGRAM_TILE_MAP).
# digit+space (the right boundary) reuses the existing half-width standalone
# digit tiles 201-210, so no new tile is needed for that case.
_NUMBER_BIGRAM_PAIRS = (
    [(a, b) for a in '0123456789' for b in '0123456789']   # 00..99
    + [('?', d) for d in '0123456789']                     # ?0..?9 (secret chapters)
    + [(' ', d) for d in '0123456789']                     # space+digit (left boundary)
)
_NUMBER_BIGRAM_TILES = {p: 1691 + i for i, p in enumerate(_NUMBER_BIGRAM_PAIRS)}
_NUMBER_TAIL_TILES = {(str(d), ' '): 201 + d for d in range(10)}  # digit+space

# Pre-rendered fragments of OUR font reused by MAPPING ONLY — glyphs
# already sit in the 1500-1620 grid-spaced range (drawn in the 0.2 patch era;
# Eagle restyle queued for the FONT.BIN rebuild). No tile is written.
# FNT_SYS-surface-only (grid-spaced range, above).
_STAT_FRAGMENT_MAPS = {
    ('L', 'V'): 1528,
    ('H', 'P'): 1529,
    ('M', 'P'): 1530,
    ('0', '%'): 1568,
}

# Comma glyph used in bigram right-halves (same shape as standalone)
_COMMA_GLYPH_BIGRAM = bytes.fromhex('00000000000000000000001818300000')

_APOSTROPHE_GLYPH = bytes.fromhex('00000018183000000000000000000000')

_BLANK_GLYPH = b'\x00' * 16

# Full 32-byte standalone uppercase tiles (tiles 17-42)
_UC_STANDALONE_TILES = {
    'A': bytes.fromhex('0000000000000100038007c00ee00c600c600c600fe00c600c60000000000000'),
    'B': bytes.fromhex('0000000000000fc006600660066007c006600660066006600fc0000000000000'),
    'C': bytes.fromhex('00000000000003c006600c200c000c000c000c000c20066003c0000000000000'),
    'D': bytes.fromhex('0000000000000f8006c006600660066006600660066006c00f80000000000000'),
    'E': bytes.fromhex('0000000000000fe0066006200680078006800600062006600fe0000000000000'),
    'F': bytes.fromhex('0000000000000fe0066006200680078006800600060006000f00000000000000'),
    'G': bytes.fromhex('00000000000003c006600c200c000c000ce00c600c6006e003a0000000000000'),
    'H': bytes.fromhex('0000000000000c600c600c600c600fe00c600c600c600c600c60000000000000'),
    'I': bytes.fromhex('00000000000003c00180018001800180018001800180018003c0000000000000'),
    'J': bytes.fromhex('00000000000001e000c000c000c000c000c00cc00cc00cc00780000000000000'),
    'K': bytes.fromhex('0000000000000e60066006c006c0078006c006c0066006600e60000000000000'),
    'L': bytes.fromhex('0000000000000f00060006000600060006000600062006600fe0000000000000'),
    'M': bytes.fromhex('0000000000000c600ee00fe00fe00d600d600d600c600c600c60000000000000'),
    'N': bytes.fromhex('0000000000000c600e600e600f600f600de00de00ce00ce00c60000000000000'),
    'O': bytes.fromhex('00000000000007c00c600c600c600c600c600c600c600c6007c0000000000000'),
    'P': bytes.fromhex('0000000000000fc0066006600660066007c00600060006000f00000000000000'),
    'Q': bytes.fromhex('000000000000038006c00c600c600c600c600c600de007e003c000c000e00000'),
    'R': bytes.fromhex('0000000000000fc0066006600660066007c006c0066006600f60000000000000'),
    'S': bytes.fromhex('00000000000007c00c600c600c00070001c000600c600c6007c0000000000000'),
    'T': bytes.fromhex('00000000000007e007e005a001800180018001800180018003c0000000000000'),
    'U': bytes.fromhex('0000000000000c600c600c600c600c600c600c600c600c6007c0000000000000'),
    'V': bytes.fromhex('0000000000000c600c600c600c600c600c600c6007c003800100000000000000'),
    'W': bytes.fromhex('0000000000000c600c600c600d600d600d600d600fe006c006c0000000000000'),
    'X': bytes.fromhex('0000000000000c600c6006c006c00380038006c006c00c600c60000000000000'),
    'Y': bytes.fromhex('000000000000066006600660066007e003c001800180018003c0000000000000'),
    'Z': bytes.fromhex('0000000000000fe00c60086000c00180030006000c200c600fe0000000000000'),
}

_ELLIPSIS_TILE_DATA = bytes.fromhex(
    # Three dots at rows 11-12 to align with period glyph baseline.
    # Previously at rows 12-13 — visibly below the text baseline.
    '00000000000000000000000000000000000000000000318c318c000000000000'
)
_DQUOTE_TILE_DATA = bytes.fromhex(
    '0000360036001200240000000000000000000000000000000000000000000000'
)

# ---------------------------------------------------------------------------
# 0.2-patch non-bigram tiles (menus, UI, gaps)
# These tiles are referenced by 0.2 patch menu patches (prog_3, syswin, etc.)
# and must be present in the font for menus to display correctly.
# ---------------------------------------------------------------------------



# Name-entry keyboard buttons (fntsys14 rows reference tiles 1488-1490).
# OUR art (2026-06-11, replaces the 0.2 patch stacked-letter ADV/BAK/END):
# ADV = right arrow, BAK = left arrow (EagleIII arrowheads, extended
# shaft), END = condensed "END" text in a single 16x16 tile.
_NAME_ENTRY_BUTTON_TILES = {
    1488: bytes.fromhex('00000000000000000008000c000e7ffe'
                        '000e000c000800000000000000000000'),  # ADV →
    1489: bytes.fromhex('00000000000000001000300070007ffe'
                        '70003000100000000000000000000000'),  # BAK ←
    1490: bytes.fromhex('00000000000000007a2e4329432972a9'
                        '426942697a2e00000000000000000000'),  # END
}


# Gap tiles between bigram groups — blank in 0.2-patch font, kanji in JP font.
# Must be blanked to avoid rendering kanji artifacts.
_BLANK_GAP_TILES = [
    *range(201, 212), *range(307, 330), *range(366, 369), 911, 912,
]


# ---------------------------------------------------------------------------
# Build tile maps
# ---------------------------------------------------------------------------

def build_char_tile_map() -> dict:
    """Build single char -> tile_index mapping.

    Only includes characters that have valid glyphs in 0.2 patch's font.
    """
    m = {}
    m[' '] = 0
    m[':'] = 1
    m[';'] = 2
    m[','] = 3
    m['.'] = 4
    m['?'] = 5
    m['!'] = 6
    # Dialogue/plot digit singles keep the centered tiles (JP zenkaku
    # style); the FNT_SYS surface remaps them to (d,' ') half-width
    # (FNTSYS_CHAR_TILE_MAP below).
    for i in range(10):
        m[str(i)] = 7 + i
    # A-Z singles still fall back to the centered tiles; full (X,' ')
    # coverage is the FONT.BIN-rebuild phase (see 20260611 plan, Phase C).
    for i in range(26):
        m[chr(65 + i)] = 17 + i  # A-Z

    # Lowercase: use "X + space" bigram tile (first tile in each LC group)
    for ch, start in _LC_STARTS.items():
        m[ch] = start

    m['…'] = ELLIPSIS_TILE
    m['"'] = DQUOTE_TILE

    # Extended punctuation (installed in kanji area tiles 1627-1638)
    for ch, idx in _EXTRA_PUNCT_TILES.items():
        m[ch] = idx

    # Formation icons — JP-preserved glyphs at 0x014A-0x014E (see dict comment)
    for ch, idx in _FORMATION_GLYPH_TILES.items():
        m[ch] = idx

    # '*' renders as the JP full-width star ＊ (the same star drawn in the
    # objectives-header on the scenario-start screen). Tile 489 carries that
    # glyph in the JP FONT.BIN and is preserved verbatim by generate_english_font
    # (it lands on an 'm'-group UI offset the bigram generator skips), so we
    # map '*' straight to it instead of drawing a separate asterisk.
    m['*'] = 489

    # Full-width (zenkaku) aliases, mirroring the JP SCENARIO title line.
    # For now they reuse our existing half-width tiles; later those tiles may be
    # redrawn as true full-width glyphs. The zenkaku space '　' (U+3000) is a
    # distinct char from ASCII ' ', so it survives the leading-space trim and
    # forms no (' ', X) bigram — that is why the JP layout uses it for padding.
    m['　'] = 0                          # 　 ideographic space → blank tile
    for i in range(10):
        m[chr(0xFF10 + i)] = 7 + i           # ０-９ → digit tiles 7-16
    for i in range(26):
        m[chr(0xFF21 + i)] = 17 + i          # Ａ-Ｚ → uppercase tiles 17-42
    m['‐'] = 372                        # ‐ JP full-width hyphen (preserved)
    m['？'] = 5                          # ？ full-width question mark (SCENARIO-?N)

    return m


def build_bigram_tile_map() -> dict:
    """Build (left_char, right_char) -> tile_index mapping.

    Only includes bigrams that have valid glyphs in 0.2 patch's font.
    """
    m = {}

    # Lowercase bigrams — use range(33) to accommodate groups with UI offsets
    # (m has 2, p has 1, v has 1, y has 2). Groups without UI offsets stop
    # early when all right chars are assigned.
    for left, base in _LC_STARTS.items():
        ui_offsets = _LC_UI_OFFSETS.get(left, set())
        missing = _LC_MISSING_CHARS.get(left, set())
        right_chars = [c for c in _LC_RIGHT_FULL if c not in missing]
        char_idx = 0
        for ri in range(33):
            if ri in ui_offsets:
                continue
            if char_idx >= len(right_chars):
                break
            m[(left, right_chars[char_idx])] = base + ri
            char_idx += 1

    # Uppercase bigrams
    for left, (base, rights) in _UC_GROUPS.items():
        ui_offsets = _UC_UI_OFFSETS.get(left, set())
        char_idx = 0
        ri = 0
        while char_idx < len(rights):
            if ri in ui_offsets:
                ri += 1
                continue
            m[(left, rights[char_idx])] = base + ri
            char_idx += 1
            ri += 1

    # Apostrophe bigrams (1491-1499 + 1621-1626, one group)
    m.update(_APOSTROPHE_BIGRAMS)
    m.update(_SPECIAL_BIGRAMS)  # 'v at 1500

    # Space+letter bigrams (1435-1487)
    m.update(_SPACE_LETTER_BIGRAMS)

    # Punctuation bigrams (907-910)
    m.update(_PUNCT_BIGRAMS)

    # Extra bigram tiles (SFX pairs, stat labels, quote+space) in kanji area
    m.update(_EXTRA_BIGRAM_TILES)

    # Stat-tail letter bigrams (audited free slots) — dialogue-safe
    m.update(_STAT_BIGRAM_TILES)

    # Custom umlaut bigrams (slots 1659-1664, kanji area)
    m.update(_CUSTOM_UMLAUT_BIGRAMS)

    # Number bigrams (slice 1) — appended past 1691; digit+space reuses 201-210
    m.update(_NUMBER_BIGRAM_TILES)
    m.update(_NUMBER_TAIL_TILES)

    # Validate no tile index collisions (two pairs sharing a slot)
    seen = {}
    for pair, tile_idx in m.items():
        if tile_idx in seen:
            raise ValueError(
                f"Tile slot {tile_idx} collision: {seen[tile_idx]} and {pair}"
            )
        seen[tile_idx] = pair

    return m


CHAR_TILE_MAP = build_char_tile_map()
# Dialogue ASCII digits render HALF-WIDTH (201-210), not centered zenkaku, now
# that the number bigrams give complete 00-99 coverage (no half/full mixing).
# Full-width '０'-'９' (-> 7-16) are untouched, so SCENARIO titles stay zenkaku.
for _d in range(10):
    CHAR_TILE_MAP[str(_d)] = 201 + _d
BIGRAM_TILE_MAP = build_bigram_tile_map()

# Apostrophe + hyphen completion: when the letter before a ' or - lands at odd
# greedy parity it would fall to a standalone tile (blank right half) and spread
# the mark ("Freya 's", "Class - Up", stutters "N- no"). Adding every missing
# (letter,punct)/(punct,letter) pair lets them pair tight. Appended at fresh
# tiles past the number region; composed in generate_english_font.
_PUNCT_FAMILY_TILES = {}
_next_free = max(BIGRAM_TILE_MAP.values()) + 1
for _p in ("'", "-"):
    for _c in string.ascii_lowercase + string.ascii_uppercase:
        for _pair in ((_c, _p), (_p, _c)):
            if _pair not in BIGRAM_TILE_MAP:
                _PUNCT_FAMILY_TILES[_pair] = _next_free
                _next_free += 1
BIGRAM_TILE_MAP.update(_PUNCT_FAMILY_TILES)

# ---------------------------------------------------------------------------
# Data-driven completion: add a tile for every half-width pair the FINAL scripts
# pair 2-chars-at-a-time (the engine's fixed-column layout), so nothing falls
# back to a centered zenkaku single or a blank gap. Boundaries (never a bigram):
# control codes, [tokens], * • and any full-width/zenkaku char. Same algorithm as
# tools/bigram_histogram.py; tests/test_no_bigram_fallback.py enforces MISSING==0.
# ---------------------------------------------------------------------------
_HALF_GLYPH_CHARS = ({' ', "'"} | set(_LETTER_GLYPHS) | set(_PUNCT_GLYPHS)
                     | set(_EXTRA_PUNCT_GLYPHS) | set(_DIGIT_HALF_GLYPHS)
                     | set(_UMLAUT_HALF_GLYPHS))
_BIGRAM_BOUNDARY = re.compile(r"<\$[0-9A-Fa-f]*>|\[[^\]]*\]|[✻…*•【】]|[　‐-―！-｠]")


def script_bigram_pairs(script_dir):
    """Every (a,b) the final scripts pair 2-chars-at-a-time. Control codes,
    [tokens], * • and full-width/zenkaku chars are boundaries; a trailing odd
    char pairs with space. The single source of truth for which half-width
    bigrams the font must contain (umlauts ü/ä/ö stay composable)."""
    pairs = set()
    for p in sorted(Path(script_dir).glob("*.txt")):
        if p.name.startswith("_") or p.stem.endswith("_src"):
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            for seg in _BIGRAM_BOUNDARY.split(line.replace("...", "…")):
                for j in range(0, len(seg), 2):
                    a = seg[j]
                    b = seg[j + 1] if j + 1 < len(seg) else " "
                    pairs.add((a, b))
    return pairs


_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "en"
_SCRIPT_BIGRAM_TILES = {}
_next_free = max(BIGRAM_TILE_MAP.values()) + 1
try:
    _needed_pairs = script_bigram_pairs(_SCRIPTS_DIR)
except OSError:
    _needed_pairs = set()
for _a, _b in sorted(_needed_pairs):
    if (_a, _b) in BIGRAM_TILE_MAP:
        continue
    if _b == " " and _a in CHAR_TILE_MAP:        # trailing -> standalone (x + blank)
        continue
    if _a not in _HALF_GLYPH_CHARS or _b not in _HALF_GLYPH_CHARS:
        continue                                  # not composable -> needs a drawn glyph
    _SCRIPT_BIGRAM_TILES[(_a, _b)] = _next_free
    _next_free += 1
BIGRAM_TILE_MAP.update(_SCRIPT_BIGRAM_TILES)

# Total tile count of the GENERATED English font (JP base + all appended bigrams).
ENGLISH_FONT_TILES = max(BIGRAM_TILE_MAP.values()) + 1

TILE_CHAR_MAP = {v: k for k, v in CHAR_TILE_MAP.items()}


def build_fntsys_maps() -> tuple:
    """Per-surface encoder choice (see reference_font_consumer_map): the
    FNT_SYS string sections (descriptions, menu labels, spell lists) add
    the digit pairs and fragment reuse on top of the dialogue maps,
    and remap single half-width digits to their (d,' ') half-width tile.
    Glyphs are shared; only the encoding choice differs per surface.
    """
    char_m = dict(CHAR_TILE_MAP)
    for d in range(10):
        char_m[str(d)] = _DIGIT_PAIR_TILES[(str(d), ' ')]
    bigram_m = dict(BIGRAM_TILE_MAP)
    bigram_m.update(_DIGIT_PAIR_TILES)
    bigram_m.update(_STAT_FRAGMENT_MAPS)
    return char_m, bigram_m


FNTSYS_CHAR_TILE_MAP, FNTSYS_BIGRAM_TILE_MAP = build_fntsys_maps()


# ---------------------------------------------------------------------------
# Visualization (debug)
# ---------------------------------------------------------------------------

def visualize_tile(tile_data: bytes, label: str = '?') -> str:
    """Visualize a tile as ASCII art with a divider at column 8."""
    lines = [f'Tile for "{label}":']
    for row in range(16):
        word = (tile_data[row * 2] << 8) | tile_data[row * 2 + 1]
        left = ''
        right = ''
        for col in range(16):
            ch = '#' if word & (1 << (15 - col)) else '.'
            if col < 8:
                left += ch
            else:
                right += ch
        lines.append(left + '|' + right)
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Font generation — build English font at build time from JP FONT.BIN
# ---------------------------------------------------------------------------

def _interleave(left_glyph: bytes, right_glyph: bytes) -> bytes:
    """Interleave two 16-byte half-glyphs into a 32-byte tile (MSB left)."""
    result = bytearray(32)
    for i in range(16):
        result[i * 2] = left_glyph[i]
        result[i * 2 + 1] = right_glyph[i]
    return bytes(result)


def _render_glyph_centered(glyph: bytes) -> bytes:
    """Render an 8x16 glyph in cols 4-11 of a 16x16 tile (centered).

    Used for the 0.2 patch menu range (1500-1620), where each hand-drawn tile
    held a single char positioned roughly mid-cell. Mirroring that
    position with Eagle III keeps in-game tabular layout intact —
    binaries reference tile_code expecting the char to occupy the
    centred slot, not the standard bigram left half.
    """
    tile = bytearray(32)
    for r in range(16):
        b = glyph[r]
        tile[r * 2]     = (b >> 4) & 0x0F
        tile[r * 2 + 1] = (b << 4) & 0xF0
    return bytes(tile)


def _render_tight_bigram(left_glyph: bytes, right_glyph: bytes,
                          shift: int = 2) -> bytes:
    """Render two 8x16 glyphs side-by-side with tight kerning.

    Eagle III glyphs have natural 1-2 pixel right padding for legibility.
    Standard `_interleave` puts left in cols 0-7, right in cols 8-15 —
    leaving 2-3 visible pixels of whitespace between them, which makes
    "Sc" in [Sc]enario read as "S cenario" in-game.

    `_render_tight_bigram` shifts the right glyph LEFT by `shift` pixels
    (default 2), bitwise-OR'ing into the left half when they touch.
    """
    tile = bytearray(32)
    for r in range(16):
        combined = (left_glyph[r] << 8) | (right_glyph[r] << shift)
        tile[r * 2] = (combined >> 8) & 0xFF
        tile[r * 2 + 1] = combined & 0xFF
    return bytes(tile)


# 0.2 patch tile range overrides — when populated, these tile slots get
# Eagle III re-rasterized at build time instead of 0.2 patch hand-drawn bytes.
# Format:
#   tile_idx → ('center', 'a')           single char centred (cols 4-11)
#   tile_idx → ('left',   'X')           single char on left half (cols 0-7)
#   tile_idx → ('bigram', 'P', 'C')      8x16 bigram (cols 0-7 + 8-15)
#   tile_idx → ('bigram', 'S', 'c'[, shift])  tight-kerned bigram
#
# LC alphabet (1585-1610): each centres its char in cols 4-9 ('center' mode).
# This dict is the COMPLETE source for the 1500-1620 menu/stat range — every
# slot is composed from our half-glyphs (center/left/bigram). The old
# 0.2-patch hand-drawn byte blobs were deleted; nothing falls back to them.
# Composite slots (1611-1620) are stat-icon composites built as tight bigrams.
_MENU_GLYPHS: dict[int, tuple] = {}
for _i, _ch in enumerate('abcdefghijklmnopqrstuvwxyz'):
    _MENU_GLYPHS[1585 + _i] = ('center', _ch)

# UC range identifications — the character each menu slot holds is locked
# by the curated truth CSV (tests/tile_audit_truth.csv, test_tile_audit_truth).
# Bigram pairs use tight_bigram so adjacent Eagle III glyphs touch
# without the natural 1-2 px padding that vanilla _interleave leaves.
_MENU_GLYPHS.update({
    # 'v ligature for "You've" / "I've" / etc.
    1500: ('bigram', "'", 'v'),

    # Audio menu (PCM/BGM)
    1501: ('bigram', 'P', 'C'),   # "[PC][M ]" PCM
    1502: ('bigram', 'B', 'G'),   # "[BG][M ]" BGM
    1503: ('left', 'M'),                # "M " left half (PCM/BGM/RAM)

    # Misc bigrams from menus
    1504: ('bigram', 'S', 'c'),   # Scenario / Screen
    1505: ('bigram', 'T', 'u'),   # Turn

    # Name-input grid composites 1506-1512 (UC + lc-umlaut for name screen)
    1506: ('bigram', 'J', 'ü'),
    1507: ('bigram', 'm', 'ü'),
    1508: ('bigram', 'g', 'ü'),
    1509: ('bigram', 'T', 'ü'),
    1510: ('bigram', 'T', 'ü'),
    1511: ('bigram', 'T', 'ü'),
    1512: ('bigram', 'T', 'ü'),   # 1509-1512 byte-identical in 0.2 patch

    1513: ('bigram', 'P', '!'),         # "Insufficient M[P!]" — image shows P with !

    1514: ('bigram', 'R', 'A'),   # Backup [RA][M ] = RAM (all caps)

    # Stat-name menu bigrams 1515-1523
    1515: ('bigram', '(', 'A'),
    1516: ('bigram', 'T', '+'),
    1517: ('bigram', '2', '0'),
    1518: ('bigram', '%', ','),
    1519: ('bigram', 'F', '-'),
    1520: ('bigram', '4', '0'),
    1521: ('bigram', '%', ')'),
    1522: ('bigram', 'A', '+'),
    1523: ('bigram', 'D', '+'),

    # Stat labels 1524-1532
    1524: ('bigram', 'A', 'T'),   # ATK
    1525: ('bigram', 'D', 'F'),   # DEF
    1526: ('bigram', 'I', 'N'),
    1527: ('left', 'T'),                # "T "
    1528: ('bigram', 'L', 'V'),
    1529: ('bigram', 'H', 'P'),
    1530: ('bigram', 'M', 'P'),
    1531: ('bigram', 'S', 'T'),
    1532: ('left', 'R'),                # "R "

    # 1533-1540 linear from entry 19 of user's list.
    1533: ('bigram', 'J', 'ä'),
    1534: ('bigram', 'j', 'ä'),
    1535: ('bigram', 'ä', 'l'),
    1536: ('bigram', 'ö', 'l'),
    1537: ('bigram', ' ', '2'),
    1538: ('bigram', '-', '3'),
    1539: ('bigram', '-', 'b'),
    1540: ('bigram', '-', 'd'),
    # 1541 was missing from user's list but the audit PNG clearly shows
    # "-h" here (between "-d" at 1540 and "-m" at 1542). Adding it.
    1541: ('bigram', '-', 'h'),
    1542: ('bigram', '-', 'm'),
    1543: ('bigram', '-', 's'),
    1544: ('bigram', 'd', '-'),
    1545: ('bigram', 'i', '-'),
    1546: ('bigram', 'l', '-'),
    1547: ('bigram', 'n', '-'),
    1548: ('bigram', 'r', '-'),
    1549: ('bigram', 'w', '-'),
    1550: ('bigram', ' ', '7'),
    1551: ('bigram', '5', '%'),
    1552: ('bigram', ' ', '/'),
    1553: ('bigram', '/', ' '),
    1554: ('bigram', ' ', '-'),
    1555: ('bigram', '1', '5'),
    1556: ('bigram', '+', '8'),
    1557: ('bigram', '+', '1'),
    1558: ('bigram', '2', ' '),
    1559: ('bigram', ' ', '+'),
    1560: ('bigram', '5', ' '),
    1561: ('bigram', '3', '0'),
    1562: ('bigram', '-', '5'),
    1563: ('bigram', '0', ' '),
    1564: ('bigram', '%', ' '),
    1565: ('bigram', '1', ' '),

    # 1566 left V (audit dist=0 vs ('V',' '), user-confirmed)
    1566: ('left', 'V'),

    # 1567-1574
    1567: ('bigram', ' ', '5'),
    1568: ('bigram', '0', '%'),
    1569: ('bigram', ' ', '1'),
    1570: ('bigram', '*', '*'),
    1571: ('bigram', 'n', '*'),
    1572: ('bigram', '*', ' '),
    1573: ('bigram', 'e', '-'),
    1574: ('bigram', 'a', '-'),

    # 1611-1616 from user's separate list
    1611: ('bigram', 'h', 'ä'),
    1612: ('bigram', 'ä', 'r'),
    1613: ('bigram', 'B', 'ö'),
    1614: ('bigram', 'ö', 's'),
    1615: ('bigram', 'R', '.'),
    1616: ('bigram', 'A', '.'),
    # 1617-1620: user has no audit.png; left as 0.2 patch hand-drawn
})


def generate_english_font(jp_font: bytes) -> bytes:
    """Generate English font by overwriting tiles in the JP FONT.BIN.

    Takes the raw JP FONT.BIN (54112 bytes = 1691 tiles x 32 bytes) and
    overwrites ONLY tiles mapped by the encoder (CHAR_TILE_MAP / BIGRAM_TILE_MAP).
    UI tiles, 0.2 patch range (1500-1620 except space+digit), and unmapped kanji are
    left untouched.

    Returns a complete 54112-byte font ready to be patched into the ISO.
    """
    TILE_SIZE = 32
    EXPECTED_SIZE = 1691 * TILE_SIZE

    if len(jp_font) != EXPECTED_SIZE:
        raise ValueError(
            f"Expected {EXPECTED_SIZE} bytes (1691 tiles), got {len(jp_font)}"
        )

    font = bytearray(jp_font)

    def write_tile(idx, data):
        font[idx * TILE_SIZE:(idx + 1) * TILE_SIZE] = data

    # Build glyph lookup for bigram interleaving
    half_glyphs = {}
    half_glyphs[' '] = _BLANK_GLYPH
    half_glyphs.update({ch: g for ch, g in _LETTER_GLYPHS.items()})
    half_glyphs.update({ch: g for ch, g in _PUNCT_GLYPHS.items()})
    half_glyphs.update({ch: g for ch, g in _EXTRA_PUNCT_GLYPHS.items()})
    half_glyphs.update({ch: g for ch, g in _DIGIT_HALF_GLYPHS.items()})
    half_glyphs.update({ch: g for ch, g in _UMLAUT_HALF_GLYPHS.items()})
    half_glyphs["'"] = _APOSTROPHE_GLYPH

    # Bigram comma uses a shifted-up variant
    bigram_right_glyphs = dict(half_glyphs)
    bigram_right_glyphs[','] = _COMMA_GLYPH_BIGRAM

    # --- Tile 0: blank (space) ---
    write_tile(0, b'\x00' * TILE_SIZE)

    # --- Tiles 1-6: standalone punctuation (left half + blank right) ---
    for ch, idx in [(':', 1), (';', 2), (',', 3), ('.', 4), ('?', 5), ('!', 6)]:
        write_tile(idx, _interleave(_PUNCT_GLYPHS[ch], _BLANK_GLYPH))

    # --- Tiles 7-16: full-width digits ---
    for i in range(10):
        write_tile(7 + i, _DIGIT_TILES[str(i)])

    # --- Tiles 17-42: full-width uppercase ---
    for i in range(26):
        write_tile(17 + i, _UC_STANDALONE_TILES[chr(65 + i)])

    # --- Tile 43: blank (previously JP kanji leftover) ---
    write_tile(43, b'\x00' * TILE_SIZE)

    # --- Tile 44: "'s " — COMPACT possessive (left half) + trailing space ---
    # 8-bit-loadable slot for SH-2 `mov #0x2C, Rn`, used by both the stat-up
    # template ("[Name]'s Level ...") and the item-use message ("[Name]'s
    # [Item] was used!") in prog_3.bin.
    #
    # Redesigned 2026-06-14 (user): the possessive 's no longer spans a whole
    # bigram. It is drawn COMPACT in the LEFT half — apostrophe touching the
    # top-left corner, the s shifted right to touch col 7 — so the RIGHT half is
    # an 8px trailing SPACE. This puts the post-'s separator INSIDE the tile,
    # fixing the item-use glue ("Tiaris'sMagic Herb" -> "Tiaris's Magic Herb")
    # with no 2nd low slot. Stays at index 44 (<= 0x7F, sign-safe; see
    # reference_engine_immediate_tile_constraint).
    #
    # NOTE: the gap now lives in the tile, so the stat-up suffix's own leading
    # space (" Level") would DOUBLE the gap in those messages — handled in the
    # fntsys suffix if playtest shows it (see prog3_statup_template).
    _s_possessive = bytearray(b >> 1 for b in _LETTER_GLYPHS['s'])  # s -> cols 1-7
    _s_possessive[2] |= 0xC0   # apostrophe, top-left corner
    _s_possessive[3] |= 0xC0
    _s_possessive[4] |= 0x80
    write_tile(44, _interleave(bytes(_s_possessive), _BLANK_GLYPH))

    # --- Tile 45: blank (previously JP kanji leftover) ---
    write_tile(45, b'\x00' * TILE_SIZE)

    # --- Tiles 46-905: LC bigrams ---
    for left, base in _LC_STARTS.items():
        ui_offsets = _LC_UI_OFFSETS.get(left, set())
        missing = _LC_MISSING_CHARS.get(left, set())
        right_chars = [c for c in _LC_RIGHT_FULL if c not in missing]
        char_idx = 0
        for ri in range(33):
            if ri in ui_offsets:
                continue
            if char_idx >= len(right_chars):
                break
            right_ch = right_chars[char_idx]
            left_g = half_glyphs[left]
            right_g = bigram_right_glyphs[right_ch]
            write_tile(base + ri, _interleave(left_g, right_g))
            char_idx += 1

    # --- Tile 906: ellipsis ---
    write_tile(906, _ELLIPSIS_TILE_DATA)

    # --- Tiles 907-910: punctuation bigrams ---
    for (left, right), idx in _PUNCT_BIGRAMS.items():
        write_tile(idx, _interleave(half_glyphs[left], half_glyphs[right]))

    # --- Tiles 914-1435: UC bigrams ---
    for left, (base, rights) in _UC_GROUPS.items():
        ui_offsets = _UC_UI_OFFSETS.get(left, set())
        char_idx = 0
        ri = 0
        while char_idx < len(rights):
            if ri in ui_offsets:
                ri += 1
                continue
            right_ch = rights[char_idx]
            left_g = half_glyphs[left]
            right_g = bigram_right_glyphs[right_ch]
            write_tile(base + ri, _interleave(left_g, right_g))
            char_idx += 1
            ri += 1

    # --- Tiles 1435-1487: space+letter bigrams ---
    for (left, right), idx in _SPACE_LETTER_BIGRAMS.items():
        write_tile(idx, _interleave(_BLANK_GLYPH, half_glyphs[right]))

    # --- Tile 1470: double-quote ---
    write_tile(1470, _DQUOTE_TILE_DATA)

    # --- Apostrophe bigrams (1491-1499 + 1621-1626, one group) ---
    for (left, right), idx in _APOSTROPHE_BIGRAMS.items():
        left_g = half_glyphs[left]
        right_g = half_glyphs[right]
        write_tile(idx, _interleave(left_g, right_g))

    # --- Tile 1500: 'v special bigram ---
    for (left, right), idx in _SPECIAL_BIGRAMS.items():
        write_tile(idx, _interleave(half_glyphs[left], half_glyphs[right]))

    # --- Stat-tail + digit bigrams (audited free slots) ---
    # _STAT_FRAGMENT_MAPS reuse pre-rendered 0.2 patch tiles and are NOT drawn.
    for (left, right), idx in {**_STAT_BIGRAM_TILES, **_DIGIT_PAIR_TILES}.items():
        left_g = half_glyphs[left]
        right_g = bigram_right_glyphs[right]
        write_tile(idx, _interleave(left_g, right_g))

    # --- Tiles 1659-1664: custom umlaut bigrams (kanji area) ---
    # Same composition as the regular (X, u/a/o) bigrams + umlaut dots.
    # Lives outside 0.2 patch range (1500-1620) where the engine renders with
    # name-input-grid spacing that produces visible gaps in dialogue.
    for (left, right), idx in _CUSTOM_UMLAUT_BIGRAMS.items():
        write_tile(idx, _interleave(half_glyphs[left], half_glyphs[right]))

    # --- Tiles 1627-1638: extended punctuation (installed in kanji area) ---
    # 11 chars that appeared in scripts but had no glyph: - + ( ) / * % [ ] ' &
    # Chars listed in _FULL_WIDTH_PUNCT_GLYPHS get the full 32-byte tile
    # directly (no interleave with blank half) so they span the full cell.
    for ch, idx in _EXTRA_PUNCT_TILES.items():
        if ch in _FULL_WIDTH_PUNCT_GLYPHS:
            write_tile(idx, _FULL_WIDTH_PUNCT_GLYPHS[ch])
        elif ch in _UMLAUT_HALF_GLYPHS:
            write_tile(idx, _interleave(_UMLAUT_HALF_GLYPHS[ch], _BLANK_GLYPH))
        else:
            write_tile(idx, _interleave(_EXTRA_PUNCT_GLYPHS[ch], _BLANK_GLYPH))

    # --- Tiles 1639-1655: extra bigrams (SFX + stat abbrevs + quote pairs) ---
    # Half-width double-quote glyph extracted from _DQUOTE_TILE_DATA (rows 1-4).
    dquote_half = bytes.fromhex('00363612240000000000000000000000')
    extra_bigram_glyphs = {
        # doubled letters
        ('A', 'A'): (_LETTER_GLYPHS['A'], _LETTER_GLYPHS['A']),
        ('O', 'O'): (_LETTER_GLYPHS['O'], _LETTER_GLYPHS['O']),
        ('U', 'U'): (_LETTER_GLYPHS['U'], _LETTER_GLYPHS['U']),
        ('H', 'H'): (_LETTER_GLYPHS['H'], _LETTER_GLYPHS['H']),
        # letter + exclamation
        ('A', '!'): (_LETTER_GLYPHS['A'], _PUNCT_GLYPHS['!']),
        ('H', '!'): (_LETTER_GLYPHS['H'], _PUNCT_GLYPHS['!']),
        ('N', '!'): (_LETTER_GLYPHS['N'], _PUNCT_GLYPHS['!']),
        # SFX prefixes
        ('G', 'U'): (_LETTER_GLYPHS['G'], _LETTER_GLYPHS['U']),
        ('G', 'O'): (_LETTER_GLYPHS['G'], _LETTER_GLYPHS['O']),
        ('G', 'A'): (_LETTER_GLYPHS['G'], _LETTER_GLYPHS['A']),
        ('G', 'Y'): (_LETTER_GLYPHS['G'], _LETTER_GLYPHS['Y']),
        ('Y', 'A'): (_LETTER_GLYPHS['Y'], _LETTER_GLYPHS['A']),
        ('A', 'H'): (_LETTER_GLYPHS['A'], _LETTER_GLYPHS['H']),
        # stat abbreviations
        ('A', 'T'): (_LETTER_GLYPHS['A'], _LETTER_GLYPHS['T']),
        ('D', 'F'): (_LETTER_GLYPHS['D'], _LETTER_GLYPHS['F']),
        # all-caps (NPC) — EagleIII halves at free slot 1666
        ('N', 'P'): (_LETTER_GLYPHS['N'], _LETTER_GLYPHS['P']),
        # all-caps (GRIN) — dialogue emphasis, dead-kanji slot 1582
        ('G', 'R'): (_LETTER_GLYPHS['G'], _LETTER_GLYPHS['R']),
        # all-caps (HP) — dialogue stat abbreviation, dead-kanji slot 1583
        ('H', 'P'): (_LETTER_GLYPHS['H'], _LETTER_GLYPHS['P']),
        # quote+space pairs (same dquote glyph, different half)
        (' ', '"'): (_BLANK_GLYPH, dquote_half),
        ('"', ' '): (dquote_half, _BLANK_GLYPH),
    }
    for pair, idx in _EXTRA_BIGRAM_TILES.items():
        left_g, right_g = extra_bigram_glyphs[pair]
        write_tile(idx, _interleave(left_g, right_g))

    # --- Name-entry keyboard buttons (our ADV/BAK/END art) ---
    for idx, data in _NAME_ENTRY_BUTTON_TILES.items():
        write_tile(idx, data)

    # --- Tile 1276 (legacy <$04FC> position): redraw with OUR NP halves ---
    # The encoder's (N,P) lives at 1666; 1276 held an old NP copy. No
    # FNT_SYS/D00 stream references it, but raw 0x04FC hits in SYSWIN/
    # A0LANG/PROG_3 are unresolved — repainting in our style keeps any
    # hardcoded consumer rendering correctly with zero inherited pixels.
    write_tile(1276, _interleave(_LETTER_GLYPHS['N'], _LETTER_GLYPHS['P']))

    # --- Orphan engine-UI slots: blank (our zeros, NOT JP kanji) ---
    # 766="Uü" and 1041="Rü" were 0.2-patch umlaut bigrams, superseded by
    # our own at 1659+; 1630 was a 0.2-patch decoration. None has a text
    # consumer and the bigram generator skips them. The ONLY glyphs we
    # inherit from JP are the formations (_FORMATION_GLYPH_TILES) and the
    # star (*→tile 489); everything else is ours, so blank these three.
    for idx in (766, 1041, 1630):
        write_tile(idx, b'\x00' * TILE_SIZE)

    # --- Blank gap tiles (remove kanji from unused slots) ---
    # Slots claimed by the stat-tail/digit bigrams are no longer gaps.
    stat_slots = (set(_STAT_BIGRAM_TILES.values())
                  | set(_DIGIT_PAIR_TILES.values()))
    for idx in _BLANK_GAP_TILES:
        if idx in stat_slots:
            continue
        write_tile(idx, b'\x00' * TILE_SIZE)

    # --- Menu/stat glyphs (1500-1620): our Eagle III draws ---
    # The SOLE source for this range now — each slot is composed from our
    # half-glyphs (center/left/bigram), no inherited bytes.
    for idx, spec in _MENU_GLYPHS.items():
        mode = spec[0]
        if mode == 'center':
            ch = spec[1]
            write_tile(idx, _render_glyph_centered(half_glyphs[ch]))
        elif mode == 'left':
            ch = spec[1]
            write_tile(idx, _interleave(half_glyphs[ch], _BLANK_GLYPH))
        elif mode == 'bigram':
            l, r = spec[1], spec[2]
            write_tile(idx, _interleave(half_glyphs[l], bigram_right_glyphs[r]))
        elif mode == 'bigram':
            l, r = spec[1], spec[2]
            shift = spec[3] if len(spec) >= 4 else 2
            write_tile(idx, _render_tight_bigram(
                half_glyphs[l], bigram_right_glyphs[r], shift))
        else:
            raise ValueError(f'unknown 0.2 patch override mode {mode!r}')

    # --- Appended bigram tiles: GROW the font and compose each from the
    # half-width glyphs so it renders tight (never a centered zenkaku / blank
    # fallback). Two families so far: numbers (digit pairs + ?N + space-led
    # boundaries) and apostrophe/hyphen (letter<->' and letter<->-, fixing the
    # "Freya 's" / "Class - Up" / "N- no" gaps). Growth proven in-game 2026-06-25
    # (the loader loads the larger file, the renderer addresses tile*0x20
    # uncapped). half_glyphs has ' ', '?', "'", '-' and the letter/digit halves.
    if ENGLISH_FONT_TILES > len(font) // TILE_SIZE:
        font.extend(b'\x00' * (ENGLISH_FONT_TILES * TILE_SIZE - len(font)))
    for (a, b), idx in {**_NUMBER_BIGRAM_TILES, **_PUNCT_FAMILY_TILES,
                        **_SCRIPT_BIGRAM_TILES}.items():
        write_tile(idx, _interleave(half_glyphs[a], half_glyphs[b]))

    return bytes(font)


# ---------------------------------------------------------------------------
# Part 6 — data-driven production layout (promoted from new_font, 2026-06-26)
# ---------------------------------------------------------------------------
# Everything above builds the LEGACY combinatorial bigram layout: wider than
# needed and APPENDED past the 1691-tile render buffer (garbles in-game), with
# many unused tiles. It is retained as (a) the PRESERVED-tile oracle and (b) the
# glyph SOURCE for the rebuild. Below we re-allocate ONLY the necessary bigrams
# into reclaimed dead slots (<=1691, 100% utilization) and compose the FRESH
# region, then promote those as the production exports. Validated in-game by the
# LANG3_NEW_FONT=1 playtest (2026-06-26); guarded by the north-star tests in
# tests/test_font_full_utilization.py. (new_font.py is now a thin re-export.)

_legacy_generate_english_font = generate_english_font   # glyph source for preserved tiles
_LEGACY_BIGRAM_TILE_MAP = BIGRAM_TILE_MAP               # preserved-tile / waste oracle

NEW_FONT_TILES = 1691     # within the in-game render buffer (no garble)

# Region FIXED: engine-mandatory, binary-hardcoded (mov #imm + value+7).
FIXED_TILES = {0, 1, 44} | set(range(7, 17))
# Region KEPT-SPECIAL: low-band ASCII + scattered specials + menu/UI band.
KEPT_SPECIAL_TILES = (
    set(range(2, 7))               # punct : ; , . ? !  (low band 1 is FIXED)
    | set(range(17, 43))           # UC A-Z full-width (zenkaku; titles + keyboard)
    | {330, 331, 332, 333, 334}    # formation glyphs
    | {369, 373, 489, 906}         # full-width parens, star, ellipsis
    | set(range(1488, 1491))       # ADV/BAK/END keyboard buttons
    | set(range(1500, 1691))       # 0.2-patch menu/UI band + dead-kanji tail
)
_FRESH_LO, _FRESH_HI = 46, 1499
# Half-width SINGLE tiles the char map references inside the FRESH range: stay at
# position so the unchanged CHAR_TILE_MAP keeps rendering them (no spacing change).
CHAR_SINGLE_TILES = {t for t in CHAR_TILE_MAP.values()
                     if t is not None and _FRESH_LO <= t <= _FRESH_HI}
PRESERVED_TILES = FIXED_TILES | KEPT_SPECIAL_TILES | CHAR_SINGLE_TILES
DROPPED_TILES = {43, 45}   # parked low-band bigrams the rebuild drops (not engine)

# Half-width double-quote (mirrors the apostrophe's upper-left mark, doubled), so
# (space,") / (",x) / (x,") pair tight instead of the wide zenkaku " (tile 1470).
_DQUOTE_GLYPH = bytes.fromhex('0000006c6c480000' '0000000000000000')


def build_half_glyphs() -> dict:
    """char -> 16-byte half-width glyph used to compose the FRESH bigram tiles."""
    hg = {' ': _BLANK_GLYPH}
    hg.update(_LETTER_GLYPHS)
    hg.update(_PUNCT_GLYPHS)
    hg.update(_EXTRA_PUNCT_GLYPHS)
    hg.update(_DIGIT_HALF_GLYPHS)
    hg.update(_UMLAUT_HALF_GLYPHS)
    hg["'"] = _APOSTROPHE_GLYPH
    hg['"'] = _DQUOTE_GLYPH
    return hg


HALF_GLYPHS = build_half_glyphs()


def compose_bigram(a: str, b: str) -> bytes:
    """The 32-byte tile for the half-width pair (a, b): a's left half + b's right
    half, interleaved (the same composition the proven generator uses)."""
    return _interleave(HALF_GLYPHS[a], HALF_GLYPHS[b])


def necessary_bigrams() -> list:
    """Every composable half-width pair the final scripts pair 2-by-2 (data-driven),
    plus a (c, space) tile for EVERY composable char, so a trailing / before-boundary
    char always pairs with space instead of the wide centered zenkaku single."""
    pairs = set()
    for pair in script_bigram_pairs(str(_SCRIPTS_DIR)):
        a, b = pair
        if a in HALF_GLYPHS and b in HALF_GLYPHS:
            pairs.add(pair)
    for c in HALF_GLYPHS:
        if c != ' ':
            pairs.add((c, ' '))
    return sorted(pairs)


def _preserved_tile_for(pair):
    """If `pair` already renders at a PRESERVED tile, return it; else None -> needs
    a FRESH slot. (x, space) only redirects to x's preserved single when x is NOT
    composable; a composable char (incl. every uppercase) gets a FRESH half-width
    tile so a standalone "A"/"I"/"B" never falls to the wide centered zenkaku."""
    old = _LEGACY_BIGRAM_TILE_MAP.get(pair)
    if old is not None and old in PRESERVED_TILES:
        return old
    a, b = pair
    if b == " " and a not in HALF_GLYPHS:
        t = CHAR_TILE_MAP.get(a)
        if t in PRESERVED_TILES:
            return t
    return None


def build_bigram_layout() -> dict:
    """pair -> tile. Pairs that render at a preserved tile reuse it; the rest are
    data-driven FRESH bigrams packed densely from _FRESH_LO. Only NECESSARY pairs
    get a slot, so no FRESH tile is wasted (the no-waste north-star)."""
    layout = {}
    fresh = []
    for pair in necessary_bigrams():
        t = _preserved_tile_for(pair)
        if t is not None:
            layout[pair] = t
        else:
            fresh.append(pair)
    used = set(layout.values())
    nxt = _FRESH_LO
    for pair in fresh:
        while nxt in PRESERVED_TILES or nxt in used:
            nxt += 1
        if nxt > _FRESH_HI:
            raise ValueError("FRESH region overflow — necessary bigrams exceed 46..1499")
        layout[pair] = nxt
        used.add(nxt)
        nxt += 1
    return layout


def _data_driven_font_tile(font: bytes, i: int) -> bytes:
    return font[i * 32:(i + 1) * 32]


def _generate_data_driven_font(jp_font: bytes) -> bytes:
    """Preserved tiles at position (from the legacy generator) + the FRESH region
    composed data-driven from the half-glyph alphabet at their packed positions."""
    source = _legacy_generate_english_font(jp_font)
    out = bytearray(NEW_FONT_TILES * 32)
    for t in sorted(PRESERVED_TILES):
        if t < NEW_FONT_TILES:
            out[t * 32:(t + 1) * 32] = _data_driven_font_tile(source, t)
    for (a, b), t in BIGRAM_TILE_MAP.items():
        if t in PRESERVED_TILES:
            continue
        out[t * 32:(t + 1) * 32] = compose_bigram(a, b)
    # • bullet: small Eagle dot (half-width) instead of the wide centered circle.
    _bullet = CHAR_TILE_MAP.get('•')
    if _bullet is not None and _bullet < NEW_FONT_TILES:
        out[_bullet * 32:(_bullet + 1) * 32] = compose_bigram('•', ' ')
    # engine 's possessive (tile 0x2C): the normal [',s] bigram (s in the RIGHT
    # half), so the engine-injected stat-up suffix keeps its gap ("Freya's Level").
    out[0x2C * 32:0x2D * 32] = compose_bigram("'", "s")
    return bytes(out)


def _tile_region(t: int) -> str:
    if t in FIXED_TILES:
        return "FIXED"
    if t in KEPT_SPECIAL_TILES:
        return "KEPT"
    if t in DROPPED_TILES:
        return "DROPPED"
    return "FRESH"


def write_layout_csv(path: str) -> int:
    """Document every font tile: index, hex, region, glyph. Returns bigram count."""
    inv = {t: f"{a!r}+{b!r}" for (a, b), t in BIGRAM_TILE_MAP.items()}
    rows = ["tile_dec,tile_hex,region,glyph"]
    for t in range(NEW_FONT_TILES):
        rows.append(f"{t},{t:04X},{_tile_region(t)},{inv.get(t, '')}")
    Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8")
    return len(BIGRAM_TILE_MAP)


# --- Promote the data-driven layout as the production exports -----------------
BIGRAM_TILE_MAP = build_bigram_layout()
ENGLISH_FONT_TILES = NEW_FONT_TILES
generate_english_font = _generate_data_driven_font
TILE_CHAR_MAP = {v: k for k, v in CHAR_TILE_MAP.items()}

# Re-derive the FNT_SYS surface maps from the PACKED layout. build_fntsys_maps()
# ran once at module load against the LEGACY bigram positions; without this the
# fntsys encoder would emit stale tile indices (e.g. (D,E)->307) while the font
# now draws those glyphs at their packed positions (351) — garbled in-game.
FNTSYS_CHAR_TILE_MAP, FNTSYS_BIGRAM_TILE_MAP = build_fntsys_maps()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print(f'Single char map: {len(CHAR_TILE_MAP)} characters')
    print(f'Bigram map: {len(BIGRAM_TILE_MAP)} pairs')
    max_tile = max(
        max(CHAR_TILE_MAP.values()),
        max(BIGRAM_TILE_MAP.values()),
    )
    print(f'Max tile index: {max_tile}')

    lc_count = sum(1 for k in BIGRAM_TILE_MAP if k[0].islower())
    uc_count = sum(1 for k in BIGRAM_TILE_MAP if k[0].isupper())
    sp_count = sum(1 for k in BIGRAM_TILE_MAP if k[0] == ' ')
    apos_count = sum(1 for k in BIGRAM_TILE_MAP if "'" in k)
    print(f'  Lowercase bigrams: {lc_count}')
    print(f'  Uppercase bigrams: {uc_count}')
    print(f'  Space+char bigrams: {sp_count}')
    print(f'  Apostrophe bigrams: {apos_count}')
