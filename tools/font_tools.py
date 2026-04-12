#!/usr/bin/env python3
"""
font_tools.py - Bigram font system for Langrisser III Saturn English translation.

Self-contained font generator: all Latin glyph bitmaps are embedded as constants.
No external font files are needed — the build extracts the JP FONT.BIN from the
ISO as a base (preserving UI/decoration tiles) and overwrites letter/bigram tiles
with glyphs generated from the embedded data.

Tile layout follows CyberWarriorX's v0.2 translation patch tile map, which
assigns specific tile indices to bigram pairs. UI/decoration tiles interspersed
in the bigram groups are left untouched (they come from the JP original).

FONT.BIN format: 1691 tiles × 32 bytes each (16×16 1bpp, MSB=leftmost).
"""

# ---------------------------------------------------------------------------
# Tile layout (tile index assignments for bigram groups)
# ---------------------------------------------------------------------------

# Lowercase bigram groups: each letter has 31 consecutive tile slots.
_LC_STARTS = {
    'a': 46,  'b': 77,  'c': 108, 'd': 139, 'e': 170,
    'f': 214, 'g': 245, 'h': 276, 'i': 335, 'j': 374,
    'k': 405, 'l': 436, 'm': 467, 'n': 500, 'o': 531,
    'p': 562, 'q': 594, 'r': 625, 's': 656, 't': 687,
    'u': 718, 'v': 749, 'w': 780, 'x': 811, 'y': 842,
    'z': 875,
}
_LC_RIGHT_FULL = [' '] + list('abcdefghijklmnopqrstuvwxyz') + ["'", ',', '?', '!']

# UI/decoration tiles at specific offsets within bigram groups.
# These tiles are used by the game engine and must NOT be overwritten.
_LC_UI_OFFSETS = {
    'm': {15, 22},   # tiles 482, 489
    'p': {4},        # tile 566
    'y': {18, 19},   # tiles 860, 861
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
# Custom tile indices (free region 1509-1690)
# ---------------------------------------------------------------------------

I_APOSTROPHE_TILE = 1509
APOSTROPHE_TILE = 1510

_SPACE_BIGRAM_BASE = 1511
_UC_HAS_SPACE = {'A', 'C', 'I', 'O'}
_UC_MISSING_SPACE = [ch for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                     if ch not in _UC_HAS_SPACE]

# Allocation (76 tiles, 1511-1586):
#   1511-1536: space + lowercase a-z  (26)
#   1537-1562: space + uppercase A-Z  (26)
#   1563-1584: uppercase + space      (22, missing ones only)
#   1585:      's bigram
#   1586:      … ellipsis (full-width)
APOS_S_TILE = 1585
ELLIPSIS_TILE = 1586

# ---------------------------------------------------------------------------
# Embedded glyph bitmaps (8px wide, 16 rows, 1 byte/row = 16 bytes each)
# Extracted from CWX v0.2 font and stored here so the build is self-contained.
# ---------------------------------------------------------------------------

_LETTER_GLYPHS = {
    'a': bytes.fromhex('0000000000007804047c84848c720000'),
    'b': bytes.fromhex('808080808080b8c482828282c4b80000'),
    'c': bytes.fromhex('00000000000038448280808244380000'),
    'd': bytes.fromhex('0202020202023a4682828282463a0000'),
    'e': bytes.fromhex('000000000000384482fe808244380000'),
    'f': bytes.fromhex('182420202020f8202020202020200000'),
    'g': bytes.fromhex('000000000000344c8484844c34844830'),
    'h': bytes.fromhex('808080808080b8c48282828282820000'),
    'i': bytes.fromhex('00000000100030101010101010380000'),
    'j': bytes.fromhex('00000000040004040404040404044438'),
    'k': bytes.fromhex('8080808080808890a0c0a09088840000'),
    'l': bytes.fromhex('30101010101010101010101010380000'),
    'm': bytes.fromhex('0000000000006c929292929292820000'),
    'n': bytes.fromhex('000000000000cc724242424242420000'),
    'o': bytes.fromhex('00000000000038448282828244380000'),
    'p': bytes.fromhex('000000000000b0c8848484c8b0808080'),
    'q': bytes.fromhex('000000000000344c8484844c34040604'),
    'r': bytes.fromhex('000000000000b8444040404040e00000'),
    's': bytes.fromhex('00000000000078848060180484780000'),
    't': bytes.fromhex('1010101010107c1010101010100c0000'),
    'u': bytes.fromhex('000000000000848484848484847a0000'),
    'v': bytes.fromhex('00000000000082824444282810100000'),
    'w': bytes.fromhex('000000000000829292929292926c0000'),
    'x': bytes.fromhex('00000000000082442810102844820000'),
    'y': bytes.fromhex('0000000000008282828282827e02027c'),
    'z': bytes.fromhex('000000000000fc040810204080fc0000'),
    'A': bytes.fromhex('38448282828282fe8282828282820000'),
    'B': bytes.fromhex('f88482828284f8848282828284f80000'),
    'C': bytes.fromhex('38448282808080808080828244380000'),
    'D': bytes.fromhex('f8848282828282828282828284f80000'),
    'E': bytes.fromhex('fe42404040447c444040404042fe0000'),
    'F': bytes.fromhex('fe42404040447c444040404040e00000'),
    'G': bytes.fromhex('384482808080808e8282828244380000'),
    'H': bytes.fromhex('ee4444444444447c4444444444ee0000'),
    'I': bytes.fromhex('fe101010101010101010101010fe0000'),
    'J': bytes.fromhex('3e080808080808080808088888700000'),
    'K': bytes.fromhex('ee444848505060605050484844ee0000'),
    'L': bytes.fromhex('e0404040404040404040404242fe0000'),
    'M': bytes.fromhex('c66c6c6c545454444444444444ee0000'),
    'N': bytes.fromhex('ce446464645454544c4c4c4444c40000'),
    'O': bytes.fromhex('38448282828282828282828244380000'),
    'P': bytes.fromhex('f8444242424244784040404040e00000'),
    'Q': bytes.fromhex('38448282828282828282828a443a0000'),
    'R': bytes.fromhex('f8848282828284f88888848482820000'),
    'S': bytes.fromhex('38448280804020180402028244380000'),
    'T': bytes.fromhex('fe929210101010101010101010380000'),
    'U': bytes.fromhex('ee444444444444444444444444380000'),
    'V': bytes.fromhex('82828282444444282828281010100000'),
    'W': bytes.fromhex('8282828282929292aaaaaa4444440000'),
    'X': bytes.fromhex('ee444428282810102828284444ee0000'),
    'Y': bytes.fromhex('ee444428282810101010101010380000'),
    'Z': bytes.fromhex('fe840408080810102020204042fe0000'),
}

# Full 32-byte tiles for digits (they span the full 16px width)
_DIGIT_TILES = {
    '0': bytes.fromhex('000007e008101008100810081008100810081008100810081008081007e00000'),
    '1': bytes.fromhex('0000008001800280008000800080008000800080008000800080008003e00000'),
    '2': bytes.fromhex('000007e00810100810080008001000600180060008001000100010001ff80000'),
    '3': bytes.fromhex('000007e00810100810080008001003e000100008000810081008081007e00000'),
    '4': bytes.fromhex('0000006000a001200220042008201020102010201ff800200020002000f80000'),
    '5': bytes.fromhex('00001ff8100010001000100017e0181010080008000810081008081007e00000'),
    '6': bytes.fromhex('000007e00810100810081000100017e018101008100810081008081007e00000'),
    '7': bytes.fromhex('00001ff810081010101000200020004000400080008001000100020002000000'),
    '8': bytes.fromhex('000007e00810100810081008081007e008101008100810081008081007e00000'),
    '9': bytes.fromhex('000007e008101008100810081008081807e80008000810081008081007e00000'),
}

_PUNCT_GLYPHS = {
    '?': bytes.fromhex('38448202020204081010100010100000'),
    '!': bytes.fromhex('10101010101010101010100010100000'),
}

# Redesigned punctuation (8px half-glyph)
_COMMA_GLYPH = bytes([
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x60, 0x60, 0x20, 0x00,
])
_PERIOD_GLYPH = bytes([
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x60, 0x60, 0x00, 0x00,
])
_APOSTROPHE_GLYPH = bytes([
    0x00, 0x60, 0x60, 0x20, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])

# Full 32-byte tiles for standalone uppercase (proportional full-width design)
_UC_STANDALONE_TILES = {
    'A': bytes.fromhex('0000000001000380028006c004400c6008200fe01830101030182008f83e0000'),
    'B': bytes.fromhex('000000003fe0081008080808080808100fe0081808040804080408083ff00000'),
    'C': bytes.fromhex('0000000003c80c281818100830082000200020003000100818180c3003c00000'),
    'D': bytes.fromhex('000000003fc0083008180808080c080408040804080c0808081808303fc00000'),
    'E': bytes.fromhex('000000003ff8080808040800084008400fc0084008400800080408083ff80000'),
    'F': bytes.fromhex('000000001ffc0404040404000420042007e0042004200400040004001f000000'),
    'G': bytes.fromhex('0000000003c80c3818081008300020002000203e3008100818180c2803c80000'),
    'H': bytes.fromhex('000000007c3e100810081008100810081ff8100810081008100810087c3e0000'),
    'I': bytes.fromhex('0000000007c00100010001000100010001000100010001000100010007c00000'),
    'J': bytes.fromhex('0000000000f8002000200020002000200020002000200020102018400f800000'),
    'K': bytes.fromhex('000000003e7c0830086008c009800b000f00098008c00860083008183e3e0000'),
    'L': bytes.fromhex('000000001f00040004000400040004000400040004000404040404041ffc0000'),
    'M': bytes.fromhex('00000000f01e30183838282828282c682448244826c8228823882108f11e0000'),
    'N': bytes.fromhex('00000000783e1c081408160813081108118810c8104810681038101878080000'),
    'O': bytes.fromhex('0000000003c00c3018181008300c200420042004300c100818180c3003c00000'),
    'P': bytes.fromhex('000000001ff00408040404040404040807f0040004000400040004001f000000'),
    'Q': bytes.fromhex('0000000003c00c3018181008300c200420042004300c11881a580c3003d2000c'),
    'R': bytes.fromhex('000000003fe0081008080808080808100fe0082008300810081808083e3e0000'),
    'S': bytes.fromhex('0000000007c808281018100810080c0003c00030100810081808141013e00000'),
    'T': bytes.fromhex('000000007ffc4104410401000100010001000100010001000100010007c00000'),
    'U': bytes.fromhex('000000007c3e10081008100810081008100810081008100818180c3003c00000'),
    'V': bytes.fromhex('000000007c3e10081818081008300c2004200460064002c00280038001000000'),
    'W': bytes.fromhex('00000000f99f2184218423c4324c12481668142814281c380c30081008100000'),
    'X': bytes.fromhex('00000000f83e301818300c6006c003800100038006c00c6018303018f83e0000'),
    'Y': bytes.fromhex('000000007c7c1010183008200c60044006c00380010001000100010007c00000'),
    'Z': bytes.fromhex('000000001ff810301060004000c0018001000300060004000c0818083ff80000'),
}

_BLANK_GLYPH = b'\x00' * 16

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compose_tile(left_glyph: bytes, right_glyph: bytes) -> bytes:
    """Compose a 32-byte tile from two 16-byte half-glyphs."""
    result = bytearray(32)
    for r in range(16):
        result[r * 2] = left_glyph[r]
        result[r * 2 + 1] = right_glyph[r]
    return bytes(result)


def _glyph(ch: str) -> bytes:
    """Look up the 16-byte half-glyph for a character."""
    if ch == ' ':
        return _BLANK_GLYPH
    if ch == ',':
        return _COMMA_GLYPH
    if ch == '.':
        return _PERIOD_GLYPH
    if ch == "'":
        return _APOSTROPHE_GLYPH
    if ch in _LETTER_GLYPHS:
        return _LETTER_GLYPHS[ch]
    if ch in _PUNCT_GLYPHS:
        return _PUNCT_GLYPHS[ch]
    return _BLANK_GLYPH


# ---------------------------------------------------------------------------
# Build tile maps
# ---------------------------------------------------------------------------

def build_char_tile_map() -> dict:
    """Build single char -> tile_index mapping."""
    m = {}
    m[' '] = 0
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

    m["'"] = APOSTROPHE_TILE
    m['…'] = ELLIPSIS_TILE

    return m


def build_bigram_tile_map() -> dict:
    """Build (left_char, right_char) -> tile_index mapping."""
    m = {}

    # Lowercase bigrams
    for left, base in _LC_STARTS.items():
        ui_offsets = _LC_UI_OFFSETS.get(left, set())
        char_idx = 0
        for ri in range(31):
            if ri in ui_offsets:
                continue
            if char_idx < len(_LC_RIGHT_FULL):
                m[(left, _LC_RIGHT_FULL[char_idx])] = base + ri
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

    # Custom bigrams
    m[('I', "'")] = I_APOSTROPHE_TILE
    m[("'", 's')] = APOS_S_TILE

    # Space bigrams
    tile_idx = _SPACE_BIGRAM_BASE
    for ch in 'abcdefghijklmnopqrstuvwxyz':
        m[(' ', ch)] = tile_idx
        tile_idx += 1
    for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        m[(' ', ch)] = tile_idx
        tile_idx += 1
    for ch in _UC_MISSING_SPACE:
        m[(ch, ' ')] = tile_idx
        tile_idx += 1

    return m


CHAR_TILE_MAP = build_char_tile_map()
BIGRAM_TILE_MAP = build_bigram_tile_map()
TILE_CHAR_MAP = {v: k for k, v in CHAR_TILE_MAP.items()}


# ---------------------------------------------------------------------------
# Font generation (fully self-contained, no external font files)
# ---------------------------------------------------------------------------

def generate_all_tiles() -> dict:
    """Generate all tile overrides to patch onto JP FONT.BIN.

    Returns dict of tile_index -> 32-byte tile data for every tile that
    needs to be written. JP UI/decoration tiles are NOT included (they
    are preserved from the original).
    """
    tiles = {}

    # --- Standalone single-char tiles (0-42) ---
    tiles[0] = b'\x00' * 32                                      # space
    tiles[3] = _compose_tile(_COMMA_GLYPH, _BLANK_GLYPH)         # comma
    tiles[4] = _compose_tile(_PERIOD_GLYPH, _BLANK_GLYPH)        # period
    tiles[5] = _compose_tile(_PUNCT_GLYPHS['?'], _BLANK_GLYPH)   # ?
    tiles[6] = _compose_tile(_PUNCT_GLYPHS['!'], _BLANK_GLYPH)   # !

    # Digits 0-9 (full-width tiles, stored as-is)
    for digit, tile_data in _DIGIT_TILES.items():
        tiles[7 + int(digit)] = tile_data

    # Uppercase A-Z standalone (full-width proportional tiles)
    for i, ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
        tiles[17 + i] = _UC_STANDALONE_TILES[ch]

    # --- All bigram tiles ---
    bigram_map = build_bigram_tile_map()
    for (left, right), tile_idx in bigram_map.items():
        if tile_idx in tiles:
            continue  # already set (custom tiles handled below)
        tiles[tile_idx] = _compose_tile(_glyph(left), _glyph(right))

    # --- Custom tiles ---
    tiles[APOSTROPHE_TILE] = _compose_tile(_APOSTROPHE_GLYPH, _BLANK_GLYPH)
    tiles[I_APOSTROPHE_TILE] = _compose_tile(_LETTER_GLYPHS['I'], _APOSTROPHE_GLYPH)
    tiles[APOS_S_TILE] = _compose_tile(_APOSTROPHE_GLYPH, _LETTER_GLYPHS['s'])

    # Ellipsis (full-width, three 2x2 dots)
    ell = bytearray(32)
    ell[24] = 0x66; ell[25] = 0x60  # row 12
    ell[26] = 0x66; ell[27] = 0x60  # row 13
    tiles[ELLIPSIS_TILE] = bytes(ell)

    return tiles


def patch_font_bin(jp_font: bytes, tiles: dict) -> bytes:
    """Patch JP FONT.BIN with generated Latin tiles.

    Starts from the JP original (preserving UI/decoration tiles that the
    game engine references directly), then overwrites all letter, bigram,
    and punctuation tiles with our generated content.
    """
    font = bytearray(jp_font)
    for tile_idx, tile_data in tiles.items():
        offset = tile_idx * 32
        if offset + 32 <= len(font):
            font[offset:offset + 32] = tile_data
    return bytes(font)


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
    print(f'  Lowercase bigrams: {lc_count}')
    print(f'  Uppercase bigrams: {uc_count}')

    tiles = generate_all_tiles()
    print(f'\nGenerated tiles: {len(tiles)}')
    print(f'Max generated tile index: {max(tiles.keys())}')

    # Show some sample tiles
    for left, right in [('t','h'), ('e',' '), ('H','e'), ('T','h'), ('i','n')]:
        pair = (left, right)
        if pair in BIGRAM_TILE_MAP:
            idx = BIGRAM_TILE_MAP[pair]
            if idx in tiles:
                print(f'\n--- "{left}{right}" at tile {idx} ---')
                print(visualize_tile(tiles[idx], f'{left}{right}'))
