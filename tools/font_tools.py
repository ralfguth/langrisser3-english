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
}

# CWX space+digit bigrams (already in VD/CWX font)
_CWX_SPACE_DIGIT_BIGRAMS = {
    (' ', '0'): 1575,
    (' ', '1'): 1576,
    (' ', '2'): 1577,
    (' ', '3'): 1578,
    (' ', '4'): 1579,
    (' ', '5'): 1580,
    (' ', '6'): 1581,
    (' ', '7'): 1582,
    (' ', '8'): 1583,
    (' ', '9'): 1584,
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
    ':': bytes.fromhex('00000000000000303000003030000000'),
    ';': bytes.fromhex('00000000000000303000000030301020'),
    ',': bytes.fromhex('00000000000000000000000030301020'),
    '.': bytes.fromhex('00000000000000000000000030300000'),
    '?': bytes.fromhex('38448202020204081010100010100000'),
    '!': bytes.fromhex('10101010101010101010100010100000'),
}

# Comma glyph used in bigram right-halves (same shape as standalone)
_COMMA_GLYPH_BIGRAM = bytes.fromhex('00000000000000000000000030301020')

_APOSTROPHE_GLYPH = bytes.fromhex('00303010200000000000000000000000')

_BLANK_GLYPH = b'\x00' * 16

# Half-width (8px) digit glyphs used in space+digit bigrams
_DIGIT_HALF_GLYPHS = {
    '0': bytes.fromhex('38448282868a92a2c282828244380000'),
    '1': bytes.fromhex('103050101010101010101010107c0000'),
    '2': bytes.fromhex('38448202020202040810204080fe0000'),
    '3': bytes.fromhex('384482020202027c0202028244380000'),
    '4': bytes.fromhex('0c141424444484fe0404040404040000'),
    '5': bytes.fromhex('fe8080808080f8040202020284780000'),
    '6': bytes.fromhex('3c4280808080b8c48282828244380000'),
    '7': bytes.fromhex('fe020204040408080810101020200000'),
    '8': bytes.fromhex('38448282824438448282828244380000'),
    '9': bytes.fromhex('3a4682828282463a0202020202020000'),
}

# Full 32-byte standalone uppercase tiles (tiles 17-42)
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

_ELLIPSIS_TILE_DATA = bytes.fromhex(
    '000000000000000000000000000000000000000000000000318c318c00000000'
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

    # CWX space+digit bigrams (tiles already in font)
    m.update(_CWX_SPACE_DIGIT_BIGRAMS)

    # Custom apostrophe bigrams (tiles 1621+, written into kanji area)
    m.update(_CUSTOM_APOSTROPHE_BIGRAMS)

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

    # --- Tiles 1575-1584: space+digit bigrams ---
    for (left, right), idx in _CWX_SPACE_DIGIT_BIGRAMS.items():
        write_tile(idx, _interleave(_BLANK_GLYPH, _DIGIT_HALF_GLYPHS[right]))

    # --- Tiles 1621-1626: custom apostrophe bigrams ---
    for (left, right), idx in _CUSTOM_APOSTROPHE_BIGRAMS.items():
        left_g = half_glyphs[left]
        right_g = half_glyphs[right]
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
