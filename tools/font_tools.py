#!/usr/bin/env python3
"""
font_tools.py - Tile maps for Langrisser III Saturn English translation (VD font).

Defines CHAR_TILE_MAP and BIGRAM_TILE_MAP that map characters and character pairs
to tile indices in VermillionDesserts' English font (ENFONT2.BIN / vd_font.bin).

Tile layout follows CyberWarriorX's v0.2 translation patch tile map, which VD
adopted. VD's font has specific differences from CWX's original documentation:
  - LC bigram position 27 is period (.) not apostrophe (')
  - Tiles 43-45 are full-width lowercase a, m, p (not custom slots)
  - Apostrophe bigrams at tiles 1491-1500 (10 pairs: o' n' s' t' u' y' 'r 's 't 'v)
  - Space+letter bigrams at tiles 1435-1487 (52 pairs)
  - Punctuation bigrams at tiles 907-910 (?? ?! !! !?)
  - Double-quote at tile 1470

FONT.BIN format: 1691 tiles x 32 bytes each (16x16 1bpp, MSB=leftmost).
"""

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

# VD's right-char sequence for LC bigrams.
# Position 27 is PERIOD (.), not apostrophe — this matches VD's actual font.
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
# and VD's font has no replacement tile for that bigram).
_LC_MISSING_CHARS = {
    'v': {'q'},  # tile 766 is UI; vq bigram does not exist in VD font
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
# VD special tile indices (present in VD's ENFONT2.BIN font)
# ---------------------------------------------------------------------------

ELLIPSIS_TILE = 906          # … two-dot ellipsis (tile 906)
DQUOTE_TILE = 1470           # " double-quote (tile 1470)

# VD apostrophe bigrams (tiles 1491-1500)
# These are the ONLY way to encode apostrophes — VD has no standalone ' tile.
# VD avoids "I'll"/"I'm"/"I'd" (uses "I will"/"I am" etc.) because there is
# no I' bigram and no standalone apostrophe in the font.
_VD_APOSTROPHE_BIGRAMS = {
    ('d', "'"): 1491, ('n', "'"): 1492, ('s', "'"): 1493,
    ('t', "'"): 1494, ('u', "'"): 1495, ('y', "'"): 1496,
    ("'", 'r'): 1497, ("'", 's'): 1498, ("'", 't'): 1499,
}

# VD space+letter bigrams (tiles 1435-1487)
# Encode " a" through " z" and " A" through " Z" as single tiles.
_VD_SPACE_LETTER_BIGRAMS = {}
for _i, _ch in enumerate('abcdefghijklmnopqrstuvwxyz'):
    _VD_SPACE_LETTER_BIGRAMS[(' ', _ch)] = 1435 + _i       # 1435-1460
for _i, _ch in enumerate('ABCDEFGHI'):
    _VD_SPACE_LETTER_BIGRAMS[(' ', _ch)] = 1461 + _i       # 1461-1469
# tile 1470 = DQUOTE_TILE (not a space+letter bigram)
_VD_SPACE_LETTER_BIGRAMS[(' ', 'J')] = 1471
_VD_SPACE_LETTER_BIGRAMS[(' ', 'K')] = 1472
_VD_SPACE_LETTER_BIGRAMS[(' ', 'L')] = 1473
for _i, _ch in enumerate('MNOPQRSTUVWXYZ'):
    _VD_SPACE_LETTER_BIGRAMS[(' ', _ch)] = 1474 + _i       # 1474-1487

# VD punctuation double-bigrams (tiles 907-910)
_VD_PUNCT_BIGRAMS = {
    ('?', '?'): 907, ('?', '!'): 908, ('!', '!'): 909, ('!', '?'): 910,
}

# CWX special bigrams (already in VD/CWX font at these tile indices)
_CWX_SPECIAL_BIGRAMS = {
    ("'", 'v'): 1500,
    # CWX-area name-input umlaut bigrams. Tiles pre-rendered in the
    # original font for the name-input grid screen — reused by the
    # encoder for character/place names that carry diaeresis.
}

# Custom umlaut bigrams in the kanji area (slots 1659-1664). Built by
# interleaving our letter glyphs with our umlaut half-glyphs. Placed
# outside the CWX range (1500-1620) because the engine renders CWX-area
# tiles with name-input-grid spacing (visible gap between adjacent
# tiles) which is wrong for dialogue text. The CWX slots themselves
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

# All CWX pre-existing tile indices — the 1500-1620 range is used by CWX menu
# patches (a0lang.bin, syswin.bin, prog files) for stat labels, menu text, etc.
_CWX_PREEXISTING_TILES = set(range(1500, 1621))

# Custom bigram tiles added to kanji area (tiles 1621+).
# These tiles are written by the build pipeline into vd_font.bin.
_CUSTOM_APOSTROPHE_BIGRAMS = {
    ('I', "'"): 1621,   # I'll, I'm, I'd
    ("'", 'l'): 1622,   # I'll, he'll, she'll, we'll, they'll
    ("'", 'm'): 1623,   # I'm
    ("'", 'd'): 1624,   # I'd, he'd, she'd, we'd, they'd
    ('o', "'"): 1625,   # who's, who'd
    ('e', "'"): 1626,   # he's (when greedy encoder consumes e alone)
}

# ---------------------------------------------------------------------------
# Embedded glyph bitmaps (8px wide, 16 rows, 1 byte/row = 16 bytes each)
# Reference data extracted from CWX v0.2 font. Used by tests to verify
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

# 8w half-glyphs of digits — used by CWX-range bigram overrides for tiles
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

# Lowercase umlauts (a/o/u-diaeresis) — appear in CWX-range bigrams.
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
    '*': bytes.fromhex('00001092543854921000000000000000'),  # JP-derived hand-drawn override (kept)
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
        '0000000000000000000000000000'       # rows 0-6 (14 bytes)
        '01800180'                           # rows 7-8: cols 7-8 (4 bytes)
        '0000000000000000000000000000'       # rows 9-15 (14 bytes)
    ),
}

# Tile slot assignments for extended punctuation (kanji area, safe to overwrite)
_EXTRA_PUNCT_TILES = {
    '-': 1627,
    '+': 1628,
    '(': 1629,
    ')': 1631,   # skip 1630 (used by _CWX_BETWEEN_TILES)
    '/': 1632,
    '*': 1633,
    '%': 1634,
    '[': 1635,
    ']': 1636,
    "'": 1637,
    '&': 1638,
    '•': 1657,   # standalone bullet (kanji slot at font tail)
    'ü': 1658,   # standalone u-diaeresis (Rigüler in non-"gü" contexts)
}

# Extra bigram tiles — top frequency pairs missing from VD/CWX font.
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
    # Bullet for win/lose condition bullet points (・ in JP scripts)
    (' ', '•'): 1656,   # space+bullet — used as " •Death of <$F600>"
}

# Comma glyph used in bigram right-halves (same shape as standalone)
_COMMA_GLYPH_BIGRAM = bytes.fromhex('00000000000000000000001818300000')

_APOSTROPHE_GLYPH = bytes.fromhex('00000018183000000000000000000000')

# Small centered bullet (4x4 filled square) used as right-half of " •" bigram.
_BULLET_GLYPH_BIGRAM = bytes.fromhex('00000000000000183c3c180000000000')

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
# CWX/VD non-bigram tiles (menus, UI, gaps)
# These tiles are referenced by CWX menu patches (prog_3, syswin, etc.)
# and must be present in the font for menus to display correctly.
# ---------------------------------------------------------------------------

# Game engine UI/decoration tiles (must not be overwritten by bigram generator)
_UI_TILES = {
    766: bytes.fromhex('0000000000000000000000008434844c848484848484844c84347a0400060004'),
    1041: bytes.fromhex('fe0082008000800080008400fc82849280928092809280928292fe6c00000000'),
    1276: bytes.fromhex('cef844446442644264425442544454784c404c404c4044404440c4e000000000'),
}

# CWX menu tiles: English text for stat labels, menus, battle UI
# Tiles 1501-1574: uppercase+symbol menu glyphs
# Tiles 1585-1616: lowercase menu glyphs
_CWX_MENU_TILES = {
    1501: bytes.fromhex('f838444442824282428042804480788040804080408240824044e03800000000'),
    1502: bytes.fromhex('f83884448282828082808480f880848e82828282828282828444f83800000000'),
    1503: bytes.fromhex('c6006c006c006c00540054005400440044004400440044004400ee0000000000'),
    1504: bytes.fromhex('3800440082008000800040002038184404820280028082824444383800000000'),
    1505: bytes.fromhex('fe00920092001000100010001084108410841084108410841084387a00000000'),
    1506: bytes.fromhex('3e00080008000848080008000884088408840884088488848884707a00000000'),
    1507: bytes.fromhex('0000000000000048000000006c84928492849284928492849284827a00000000'),
    1508: bytes.fromhex('00000000000000480000000034844c848484848484844c843484847a48003000'),
    1509: bytes.fromhex('fe00920092001048100010001084108410841084108410841084387a00000000'),
    1510: bytes.fromhex('fe00920092001048100010001084108410841084108410841084387a00000000'),
    1511: bytes.fromhex('fe00920092001048100010001084108410841084108410841084387a00000000'),
    1512: bytes.fromhex('fe00920092001048100010001084108410841084108410841084387a00000000'),
    1513: bytes.fromhex('f810441042104210421042104410781040104010401040004010e01000000000'),
    1514: bytes.fromhex('f838844482828282828282828482f8fe88828882848284828282828200000000'),
    1515: bytes.fromhex('083810441082208220822082208220fe20822082208220821082108208000000'),
    1516: bytes.fromhex('fe009200920010001010101010fe101010101000100010001000380000000000'),
    1517: bytes.fromhex('38384444828202820286028a029204a208c21082208240828044fe3800000000'),
    1518: bytes.fromhex('4200a200a400440008000800100010002000200044004a208a18840800000000'),
    1519: bytes.fromhex('fe00420040004000400044007cfe440040004000400040004000e00000000000'),
    1520: bytes.fromhex('0c381444148224824486448a8492fea204c20482048204820444043800000000'),
    1521: bytes.fromhex('4220a210a410440808080808100810082008200844084a088a10841000200000'),
    1522: bytes.fromhex('38004400820082008210821082fefe1082108200820082008200820000000000'),
    1523: bytes.fromhex('f8008400820082008210821082fe821082108200820082008400f80000000000'),
    1524: bytes.fromhex('38fe449282928210821082108210fe1082108210821082108210823800000000'),
    1525: bytes.fromhex('f8fe84428240824082408244827c824482408240824082408440f8e000000000'),
    1526: bytes.fromhex('fece1044106410641064105410541054104c104c104c10441044fec400000000'),
    1527: bytes.fromhex('fe00920092001000100010001000100010001000100010001000380000000000'),
    1528: bytes.fromhex('e082408240824082404440444044402840284028402842104210fe1000000000'),
    1529: bytes.fromhex('eef84444444244424442444244447c7844404440444044404440eee000000000'),
    1530: bytes.fromhex('c6f86c446c426c42544254425444447844404440444044404440eee000000000'),
    1531: bytes.fromhex('38fe449282928010801040102010181004100210021082104410383800000000'),
    1532: bytes.fromhex('f800840082008200820082008400f80088008800840084008200820000000000'),
    1533: bytes.fromhex('3e0008000800084808000800087808040804087c08848884888c707200000000'),
    1534: bytes.fromhex('000000000000004804000000047804040404047c04840484048c047244003800'),
    1535: bytes.fromhex('0030001000104810001000107810041004107c10841084108c10723800000000'),
    1536: bytes.fromhex('0030001000104410001000103810441082108210821082104410383800000000'),
    1537: bytes.fromhex('003800440082000200020002000200040008001000200040008000fe00000000'),
    1538: bytes.fromhex('003800440082000200020002fe02007c00020002000200820044003800000000'),
    1539: bytes.fromhex('008000800080008000800080feb800c4008200820082008200c400b800000000'),
    1540: bytes.fromhex('000200020002000200020002fe3a004600820082008200820046003a00000000'),
    1541: bytes.fromhex('008000800080008000800080feb800c400820082008200820082008200000000'),
    1542: bytes.fromhex('000000000000000000000000fe6c009200920092009200920092008200000000'),
    1543: bytes.fromhex('000000000000000000000000fe78008400800060001800040084007800000000'),
    1544: bytes.fromhex('0200020002000200020002003afe4600820082008200820046003a0000000000'),
    1545: bytes.fromhex('00000000000000001000000030fe100010001000100010001000380000000000'),
    1546: bytes.fromhex('30001000100010001000100010fe100010001000100010001000380000000000'),
    1547: bytes.fromhex('000000000000000000000000ccfe720042004200420042004200420000000000'),
    1548: bytes.fromhex('000000000000000000000000b8fe440040004000400040004000e00000000000'),
    1549: bytes.fromhex('00000000000000000000000082fe9200920092009200920092006c0000000000'),
    1550: bytes.fromhex('00fe000200020004000400040008000800080010001000100020002000000000'),
    1551: bytes.fromhex('fe4280a280a4804480088008f8100410022002200244024a848a788400000000'),
    1552: bytes.fromhex('0002000200040004000800080010001000200020004000400080008000000000'),
    1553: bytes.fromhex('0200020004000400080008001000100020002000400040008000800000000000'),
    1554: bytes.fromhex('00000000000000000000000000fe000000000000000000000000000000000000'),
    1555: bytes.fromhex('10fe3080508010801080108010f81004100210021002100210847c7800000000'),
    1556: bytes.fromhex('003800440082008210821044fe38104410820082008200820044003800000000'),
    1557: bytes.fromhex('001000300050001010101010fe10101010100010001000100010007c00000000'),
    1558: bytes.fromhex('3800440082000200020002000200040008001000200040008000fe0000000000'),
    1559: bytes.fromhex('00000000000000000010001000fe001000100000000000000000000000000000'),
    1560: bytes.fromhex('fe0080008000800080008000f800040002000200020002008400780000000000'),
    1561: bytes.fromhex('38384444828202820286028a02927ca202c20282028282824444383800000000'),
    1562: bytes.fromhex('00fe00800080008000800080fef8000400020002000200020084007800000000'),
    1563: bytes.fromhex('380044008200820086008a009200a200c2008200820082004400380000000000'),
    1564: bytes.fromhex('4200a200a400440008000800100010002000200044004a008a00840000000000'),
    1565: bytes.fromhex('10003000500010001000100010001000100010001000100010007c0000000000'),
    1566: bytes.fromhex('8200820082008200440044004400280028002800280010001000100000000000'),
    1567: bytes.fromhex('00fe0080008000800080008000f8000400020002000200020084007800000000'),
    1568: bytes.fromhex('384244a282a4824486088a089210a210c22082208244824a448a388400000000'),
    1569: bytes.fromhex('0010003000500010001000100010001000100010001000100010007c00000000'),
    1570: bytes.fromhex('000000001010101054543838fefe383854541010101000000000000000000000'),
    1571: bytes.fromhex('000000000010001000540038ccfe723842544210421042004200420000000000'),
    1572: bytes.fromhex('000000001000100054003800fe00380054001000100000000000000000000000'),
    1573: bytes.fromhex('00000000000000000000000038fe44008200fe00800082004400380000000000'),
    1574: bytes.fromhex('00000000000000000000000078fe040004007c00840084008c00720000000000'),
    1585: bytes.fromhex('00000000000000000000000007800040004007c00840084008c0072000000000'),
    1586: bytes.fromhex('0800080008000800080008000b800c4008200820082008200c400b8000000000'),
    1587: bytes.fromhex('0000000000000000000000000380044008200800080008200440038000000000'),
    1588: bytes.fromhex('00200020002000200020002003a004600820082008200820046003a000000000'),
    1589: bytes.fromhex('0000000000000000000000000380044008200fe0080008200440038000000000'),
    1590: bytes.fromhex('00c00120010001000100010007c0010001000100010001000100010000000000'),
    1591: bytes.fromhex('00000000000000000000000001a00260042004200420026001a0042002400180'),
    1592: bytes.fromhex('0800080008000800080008000b800c4008200820082008200820082000000000'),
    1593: bytes.fromhex('0000000000000000010000000300010001000100010001000100038000000000'),
    1594: bytes.fromhex('0000000000000000004000000040004000400040004000400040004004400380'),
    1595: bytes.fromhex('0400040004000400040004200440048005000600050004800440042000000000'),
    1596: bytes.fromhex('0300010001000100010001000100010001000100010001000100038000000000'),
    1597: bytes.fromhex('00000000000000000000000006c0092009200920092009200920082000000000'),
    1598: bytes.fromhex('0000000000000000000000000cc0072004200420042004200420042000000000'),
    1599: bytes.fromhex('0000000000000000000000000380044008200820082008200440038000000000'),
    1600: bytes.fromhex('0000000000000000000000000580064004200420042006400580040004000400'),
    1601: bytes.fromhex('000000000000000000000000034004c008400840084004c00340004000600040'),
    1602: bytes.fromhex('00000000000000000000000005c0022002000200020002000200070000000000'),
    1603: bytes.fromhex('00000000000000000000000003c004200400030000c00020042003c000000000'),
    1604: bytes.fromhex('01000100010001000100010007c001000100010001000100010000c000000000'),
    1605: bytes.fromhex('000000000000000000000000084008400840084008400840084007a000000000'),
    1606: bytes.fromhex('0000000000000000000000000820082004400440028002800100010000000000'),
    1607: bytes.fromhex('000000000000000000000000082009200920092009200920092006c000000000'),
    1608: bytes.fromhex('0000000000000000000000000820044002800100010002800440082000000000'),
    1609: bytes.fromhex('00000000000000000000000008200820082008200820082007e00020002007c0'),
    1610: bytes.fromhex('00000000000000000000000007e000200040008001000200040007e000000000'),
    1611: bytes.fromhex('800080008000804880008000b878c4048204827c82848284828c827200000000'),
    1612: bytes.fromhex('00000000000048000000000078b8044404407c40844084408c4072e000000000'),
    1613: bytes.fromhex('f80084008200824482008400f838844482828282828282828444f83800000000'),
    1614: bytes.fromhex('0000000000004400000000003878448482808260821882044484387800000000'),
    1615: bytes.fromhex('f800840082008200820082008400f80088008800840084108238821000000000'),
    1616: bytes.fromhex('3800440082008200820082008200fe0082008200820082108238821000000000'),
}

# CWX special tiles between apostrophe and space+letter groups
_CWX_BETWEEN_TILES = {
    1488: bytes.fromhex('0000380044007c004400440003c002200220022003c000110011000a000a0004'),
    1489: bytes.fromhex('0000f0008800f0008800f0000380044007c00440044000120014001800140012'),
    1490: bytes.fromhex('00007c004000700040007c000220032002a002600220001e001100110011001e'),
    1630: bytes.fromhex('00107c1000fefe1000107c1001ff00047c0401ff00047c8444c4444444047c1c'),
}

# Gap tiles between bigram groups — blank in VD font, kanji in JP font.
# Must be blanked to avoid rendering kanji artifacts.
_BLANK_GAP_TILES = [
    *range(201, 212), *range(307, 330), *range(366, 369), 911, 912,
]


# ---------------------------------------------------------------------------
# Build tile maps
# ---------------------------------------------------------------------------

def build_char_tile_map() -> dict:
    """Build single char -> tile_index mapping.

    Only includes characters that have valid glyphs in VD's font.
    """
    m = {}
    m[' '] = 0
    m[':'] = 1
    m[';'] = 2
    m[','] = 3
    m['.'] = 4
    m['?'] = 5
    m['!'] = 6
    for i in range(10):
        m[str(i)] = 7 + i
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

    return m


def build_bigram_tile_map() -> dict:
    """Build (left_char, right_char) -> tile_index mapping.

    Only includes bigrams that have valid glyphs in VD's font.
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

    # VD apostrophe bigrams (1491-1500)
    m.update(_VD_APOSTROPHE_BIGRAMS)
    m.update(_CWX_SPECIAL_BIGRAMS)  # 'v at 1500

    # VD space+letter bigrams (1435-1487)
    m.update(_VD_SPACE_LETTER_BIGRAMS)

    # VD punctuation bigrams (907-910)
    m.update(_VD_PUNCT_BIGRAMS)

    # Custom apostrophe bigrams (tiles 1621+, written into kanji area)
    m.update(_CUSTOM_APOSTROPHE_BIGRAMS)

    # Extra bigram tiles (SFX pairs, stat labels, quote+space) in kanji area
    m.update(_EXTRA_BIGRAM_TILES)

    # Custom umlaut bigrams (slots 1659-1664, kanji area)
    m.update(_CUSTOM_UMLAUT_BIGRAMS)

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
BIGRAM_TILE_MAP = build_bigram_tile_map()
TILE_CHAR_MAP = {v: k for k, v in CHAR_TILE_MAP.items()}


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

    Used for the CWX menu range (1500-1620), where each hand-drawn tile
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


# CWX tile range overrides — when populated, these tile slots get
# Eagle III re-rasterized at build time instead of CWX hand-drawn bytes.
# Format:
#   tile_idx → ('center', 'a')           single char centred (cols 4-11)
#   tile_idx → ('left',   'X')           single char on left half (cols 0-7)
#   tile_idx → ('bigram', 'P', 'C')      8x16 bigram (cols 0-7 + 8-15)
#   tile_idx → ('bigram', 'S', 'c'[, shift])  tight-kerned bigram
#
# LC alphabet (1585-1610): identified by visual inspection — each CWX
# tile centres its char in cols 4-9; we use 'center' mode to match.
# UC range (1501-1574) is partially identified; remaining slots fall
# back to CWX hand-drawn bytes via _CWX_MENU_TILES until audited.
# Composite slots (1488-1490, 1611-1620) are 3-diagonal stat-icon
# composites that have no Eagle III equivalent — left as CWX art.
_CWX_TILE_OVERRIDES: dict[int, tuple] = {}
for _i, _ch in enumerate('abcdefghijklmnopqrstuvwxyz'):
    _CWX_TILE_OVERRIDES[1585 + _i] = ('center', _ch)

# UC range identifications — multi-context evidence in
# build/cwx_decode_context.txt (regenerable via tools/cwx_tile_audit.py).
# Bigram pairs use tight_bigram so adjacent Eagle III glyphs touch
# without the natural 1-2 px padding that vanilla _interleave leaves.
_CWX_TILE_OVERRIDES.update({
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
    1512: ('bigram', 'T', 'ü'),   # 1509-1512 byte-identical in CWX

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
    # 1617-1620: user has no audit.png; left as CWX hand-drawn
})


def generate_english_font(jp_font: bytes) -> bytes:
    """Generate English font by overwriting tiles in the JP FONT.BIN.

    Takes the raw JP FONT.BIN (54112 bytes = 1691 tiles x 32 bytes) and
    overwrites ONLY tiles mapped by the encoder (CHAR_TILE_MAP / BIGRAM_TILE_MAP).
    UI tiles, CWX range (1500-1620 except space+digit), and unmapped kanji are
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

    # --- Tile 44: "'s" bigram (repurposed from JP kanji leftover) ---
    # 8-bit-loadable slot for SH-2 `mov #0x2C, Rn`, used by stat-up template
    # assembler in prog_3.bin to render "Dieharte's Level ..." correctly.
    write_tile(44, _interleave(_APOSTROPHE_GLYPH, _LETTER_GLYPHS['s']))

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
    for (left, right), idx in _VD_PUNCT_BIGRAMS.items():
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
    for (left, right), idx in _VD_SPACE_LETTER_BIGRAMS.items():
        write_tile(idx, _interleave(_BLANK_GLYPH, half_glyphs[right]))

    # --- Tile 1470: double-quote ---
    write_tile(1470, _DQUOTE_TILE_DATA)

    # --- Tiles 1491-1500: VD apostrophe bigrams ---
    for (left, right), idx in _VD_APOSTROPHE_BIGRAMS.items():
        left_g = half_glyphs[left]
        right_g = half_glyphs[right]
        write_tile(idx, _interleave(left_g, right_g))

    # --- Tile 1500: 'v (CWX special) ---
    for (left, right), idx in _CWX_SPECIAL_BIGRAMS.items():
        write_tile(idx, _interleave(half_glyphs[left], half_glyphs[right]))

    # --- Tiles 1659-1664: custom umlaut bigrams (kanji area) ---
    # Same composition as the regular (X, u/a/o) bigrams + umlaut dots.
    # Lives outside CWX range (1500-1620) where the engine renders with
    # name-input-grid spacing that produces visible gaps in dialogue.
    for (left, right), idx in _CUSTOM_UMLAUT_BIGRAMS.items():
        write_tile(idx, _interleave(half_glyphs[left], half_glyphs[right]))

    # --- Tiles 1621-1626: custom apostrophe bigrams ---
    for (left, right), idx in _CUSTOM_APOSTROPHE_BIGRAMS.items():
        left_g = half_glyphs[left]
        right_g = half_glyphs[right]
        write_tile(idx, _interleave(left_g, right_g))

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
        # quote+space pairs (same dquote glyph, different half)
        (' ', '"'): (_BLANK_GLYPH, dquote_half),
        ('"', ' '): (dquote_half, _BLANK_GLYPH),
        # Bullet bigram for ・ -style bullet points (e.g. " •Death of <$F600>")
        (' ', '•'): (_BLANK_GLYPH, _BULLET_GLYPH_BIGRAM),
    }
    for pair, idx in _EXTRA_BIGRAM_TILES.items():
        left_g, right_g = extra_bigram_glyphs[pair]
        write_tile(idx, _interleave(left_g, right_g))

    # --- UI tiles (game engine decorations) ---
    for idx, data in _UI_TILES.items():
        write_tile(idx, data)

    # --- CWX menu tiles (English text for menus/stats/battle UI) ---
    for idx, data in _CWX_MENU_TILES.items():
        write_tile(idx, data)

    # --- CWX special tiles (between apostrophe and space+letter groups) ---
    for idx, data in _CWX_BETWEEN_TILES.items():
        write_tile(idx, data)

    # --- Blank gap tiles (remove kanji from unused slots) ---
    for idx in _BLANK_GAP_TILES:
        write_tile(idx, b'\x00' * TILE_SIZE)

    # --- CWX range overrides ---
    # Applied LAST so they take precedence over _CWX_MENU_TILES /
    # _CWX_BETWEEN_TILES (CWX hand-drawn bytes) at the same slots.
    for idx, spec in _CWX_TILE_OVERRIDES.items():
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
            raise ValueError(f'unknown CWX override mode {mode!r}')

    return bytes(font)


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
