"""tools/prog4_menu_geometry.py — PROG_4 menu/display-list geometry (disembarked).

234 owned byte patches over the **JP** `LANG/PROG_4.BIN`, carved out of the opaque
byte_overlays blob (2026-06-14) into this self-documenting module
(feedback_patch_per_module_closed_scope). This empties byte_overlays entirely.

What it is
----------
PROG_4 holds the A0LANG-style display-list **node groups** for the in-battle /
menu UI (PROG_4 and PROG_5 are overlay-swapped at the same load region — see
tools/prog5_menu_geometry.py). Every patched byte is a layout coordinate — a menu
item's X/Y position, or a window's width/height/size — nudged off the Japanese
value so the wider English labels fit. None of these are text. (The magic-icon
spell-name TEXT table at 0x7F80 was carved separately to
tools/prog4_spell_name_table.py.)

Load base = 0x06089000 (pinned 2026-06-10 by WRAM-dump byte-match; see
tools/prog4_field_box_geometry.py, which carved the field 2x2 command box from
this same file).

Node format (16 bytes), two variants
------------------------------------
    item node:   [type u32][text/child ptr u32][attr/len u32][X u8][Y u8][00 00]
    window node: [w u8][h u8][00 00][child ptr u32][attr u32][X u8][Y u8][00 00]

So in this file most item-node X/Y live at node+0xC / node+0xD, window size at
node+0 / +4, and node+8 is an attr/length. The text/child pointers are mostly
0x0603A4A2 / 0x0603A5A0 (work-RAM scratch text buffers — the menu-state composer
fills them per-frame; see archive/docs/20260608_menu_box_geometry_re.md), with a
few in-file child pointers (0x06093xxx / 0x0608xxxx). Each run is annotated below
with its node base, field offset and JP baseline byte(s).

The big group @0x0B82D-0x0C3DE (187 runs) is one large menu grid whose node Y
coordinates (node+0xD) are shifted down ~1 row (a few +2) to open vertical room
for the EN layout. Truth-locked vs the live JP ISO
(tests/test_prog4_menu_geometry.py); the exact on-screen menu each group maps to
is confirmed in the Phase-A playtest (the A0LANG trees are pointer-walked, so
there is no static code xref to name them).
"""

PROG4_MENU_GEOMETRY = {
    "LANG/PROG_4.BIN": [
    # --- node group @0x0A59C-0x0A59D (1 runs): menu node X/Y / box size for EN ---
    (0x0000A59C, b'\x02'),  # @0x0A590+C X: JP 01
    # --- node group @0x0A734-0x0A735 (1 runs): menu node X/Y / box size for EN ---
    (0x0000A734, b'\x03'),  # @0x0A730+4 ptr/size: JP 01
    # --- node group @0x0AA48-0x0AA4D (1 runs): menu node X/Y / box size for EN ---
    (0x0000AA48, b'\r\x01\x00\x00\x08'),  # @0x0AA40+8 attr: JP 0e01000006
    # --- node group @0x0ABC8-0x0ABD9 (2 runs): menu node X/Y / box size for EN ---
    (0x0000ABC8, b'\t'),  # @0x0ABC0+8 attr: JP 0a
    (0x0000ABD8, b'\n'),  # @0x0ABD0+8 attr: JP 0b
    # NOTE: node @0x0AD10 (Battle-Preparations box width) is intentionally NOT
    # patched — it ships the JP width 0x11(17). An inherited over-widening to
    # 0x18(24) made the box "too wide" (big empty gap right of the menu); removed
    # 2026-06-23 (RG) because JP 17 already leaves ~24px (3 cells) of padding after
    # the longest item ("Class Change" = 12 cells, text starts at X=3). Guarded in
    # tests/test_prog4_menu_geometry.py (offset must stay unpatched).
    # --- node group @0x0AD8C-0x0AD8D (1 runs): menu node X/Y / box size for EN ---
    (0x0000AD8C, b'\x11'),  # @0x0AD80+C X: JP 0c
    # --- node group @0x0AF50-0x0AF85 (3 runs): menu node X/Y / box size for EN ---
    (0x0000AF50, b'\x01'),  # @0x0AF50+0 w/X: JP 02
    (0x0000AF60, b'\x15'),  # @0x0AF60+0 w/X: JP 0e
    (0x0000AF84, b'\x1a'),  # @0x0AF80+4 ptr/size: JP 16
    # --- node group @0x0B1FC-0x0B26D (8 runs): menu node X/Y / box size for EN ---
    (0x0000B1FC, b'\x0b'),  # @0x0B1F0+C X: JP 09
    (0x0000B20C, b'\x0b'),  # @0x0B200+C X: JP 09
    (0x0000B21C, b'\x11'),  # @0x0B210+C X: JP 0f
    (0x0000B22C, b'\x11'),  # @0x0B220+C X: JP 0f
    (0x0000B23C, b'\x0e'),  # @0x0B230+C X: JP 0c
    (0x0000B24C, b'\x0e'),  # @0x0B240+C X: JP 0c
    (0x0000B25C, b'\x13'),  # @0x0B250+C X: JP 11
    (0x0000B26C, b'\x13'),  # @0x0B260+C X: JP 11
    # --- node group @0x0B3E0-0x0B451 (5 runs): menu node X/Y / box size for EN ---
    (0x0000B3E0, b'\n'),  # @0x0B3E0+0 w/X: JP 09
    (0x0000B40C, b'\x0b'),  # @0x0B400+C X: JP 01
    (0x0000B41C, b'\x01'),  # @0x0B410+C X: JP 09
    (0x0000B42C, b'\x15'),  # @0x0B420+C X: JP 0f
    (0x0000B450, b'\x1a'),  # @0x0B450+0 w/X: JP 16
    # --- node group @0x0B494-0x0B499 (1 runs): menu node X/Y / box size for EN ---
    (0x0000B494, b'\x01\x0c\x00\x00&'),  # @0x0B490+4 ptr/size: JP 030c000022
    # --- node group @0x0B4F4-0x0B4FA (1 runs): menu node X/Y / box size for EN ---
    (0x0000B4F4, b'\x00\x00\x00\x00(\x1c'),  # @0x0B4F0+4 ptr/size: JP 01010000261a
    # --- node group @0x0B5CC-0x0B6AE (13 runs): menu node X/Y / box size for EN ---
    (0x0000B5CC, b'#'),  # @0x0B5C0+C X: JP 21
    (0x0000B5DC, b'#'),  # @0x0B5D0+C X: JP 21
    (0x0000B5EC, b'#'),  # @0x0B5E0+C X: JP 21
    (0x0000B5FC, b'#'),  # @0x0B5F0+C X: JP 21
    (0x0000B60D, b'\x19'),  # @0x0B600+D Y: JP 17
    (0x0000B63C, b'\x1f'),  # @0x0B630+C X: JP 21
    (0x0000B64C, b'\x0b'),  # @0x0B640+C X: JP 0a
    (0x0000B65C, b'\x15'),  # @0x0B650+C X: JP 0f
    (0x0000B66C, b'\x1e'),  # @0x0B660+C X: JP 14
    (0x0000B67D, b'\x0e'),  # @0x0B670+D Y: JP 0d
    (0x0000B68D, b'\x10'),  # @0x0B680+D Y: JP 0f
    (0x0000B69D, b'\x12'),  # @0x0B690+D Y: JP 11
    (0x0000B6AD, b'\x14'),  # @0x0B6A0+D Y: JP 13
    # --- node group @0x0B71C-0x0B7AD (8 runs): menu node X/Y / box size for EN ---
    (0x0000B71C, b'\x10'),  # @0x0B710+C X: JP 11
    (0x0000B72C, b'\x10'),  # @0x0B720+C X: JP 11
    (0x0000B73C, b'\x10'),  # @0x0B730+C X: JP 11
    (0x0000B74C, b'\x10'),  # @0x0B740+C X: JP 11
    (0x0000B75C, b'\x1a\x19'),  # @0x0B750+C X: JP 1b15
    (0x0000B78C, b'\x0c'),  # @0x0B780+C X: JP 0a
    (0x0000B79C, b'\x16'),  # @0x0B790+C X: JP 0f
    (0x0000B7AC, b'\x1f'),  # @0x0B7A0+C X: JP 14
    # --- node group @0x0B82D-0x0C3DE (187 runs): BIG menu-grid X/Y for EN ---
    (0x0000B82D, b'\x04'),  # @0x0B820+D Y: JP 03
    (0x0000B83D, b'\x04'),  # @0x0B830+D Y: JP 03
    (0x0000B84D, b'\x04'),  # @0x0B840+D Y: JP 03
    (0x0000B85D, b'\x04'),  # @0x0B850+D Y: JP 03
    (0x0000B86D, b'\x04'),  # @0x0B860+D Y: JP 03
    (0x0000B87D, b'\x05'),  # @0x0B870+D Y: JP 04
    (0x0000B88D, b'\x05'),  # @0x0B880+D Y: JP 04
    (0x0000B89D, b'\x05'),  # @0x0B890+D Y: JP 04
    (0x0000B8AD, b'\x05'),  # @0x0B8A0+D Y: JP 04
    (0x0000B8BD, b'\x06'),  # @0x0B8B0+D Y: JP 05
    (0x0000B8CD, b'\x06'),  # @0x0B8C0+D Y: JP 05
    (0x0000B8DD, b'\x06'),  # @0x0B8D0+D Y: JP 05
    (0x0000B8ED, b'\x19'),  # @0x0B8E0+D Y: JP 17
    (0x0000B8FD, b'\x19'),  # @0x0B8F0+D Y: JP 17
    (0x0000B90D, b'\x19'),  # @0x0B900+D Y: JP 17
    (0x0000B91D, b'\x19'),  # @0x0B910+D Y: JP 17
    (0x0000B92D, b'\x1a'),  # @0x0B920+D Y: JP 18
    (0x0000B94C, b'\x03\x02'),  # @0x0B940+C X: JP 0201
    (0x0000B95C, b'\x16\x02'),  # @0x0B950+C X: JP 1501
    (0x0000B96C, b'\x16\x05'),  # @0x0B960+C X: JP 1504
    (0x0000B97C, b'\x16\x07'),  # @0x0B970+C X: JP 1506
    (0x0000B98C, b'\x16\t'),  # @0x0B980+C X: JP 1508
    (0x0000B99C, b'\x16\x0b'),  # @0x0B990+C X: JP 150a
    (0x0000B9AC, b'\x16\r'),  # @0x0B9A0+C X: JP 150c
    (0x0000B9BC, b'\x16\x0f'),  # @0x0B9B0+C X: JP 150e
    (0x0000B9CC, b'\x16\x11'),  # @0x0B9C0+C X: JP 1510
    (0x0000B9DD, b'\x0c'),  # @0x0B9D0+D Y: JP 0a
    (0x0000B9ED, b'\x0e'),  # @0x0B9E0+D Y: JP 0c
    (0x0000B9FD, b'\x10'),  # @0x0B9F0+D Y: JP 0e
    (0x0000BA0D, b'\x12'),  # @0x0BA00+D Y: JP 10
    (0x0000BA1D, b'\x14'),  # @0x0BA10+D Y: JP 12
    (0x0000BA3C, b'\x01\t'),  # @0x0BA30+C X: JP 0707
    (0x0000BA4D, b'\x17'),  # @0x0BA40+D Y: JP 15
    (0x0000BA5D, b'\x04'),  # @0x0BA50+D Y: JP 03
    (0x0000BA6D, b'\x04'),  # @0x0BA60+D Y: JP 03
    (0x0000BA7D, b'\x04'),  # @0x0BA70+D Y: JP 03
    (0x0000BA8D, b'\x04'),  # @0x0BA80+D Y: JP 03
    (0x0000BA9D, b'\x04'),  # @0x0BA90+D Y: JP 03
    (0x0000BAAD, b'\x05'),  # @0x0BAA0+D Y: JP 04
    (0x0000BABD, b'\x05'),  # @0x0BAB0+D Y: JP 04
    (0x0000BACD, b'\x05'),  # @0x0BAC0+D Y: JP 04
    (0x0000BADD, b'\x05'),  # @0x0BAD0+D Y: JP 04
    (0x0000BAED, b'\x06'),  # @0x0BAE0+D Y: JP 05
    (0x0000BAFD, b'\x06'),  # @0x0BAF0+D Y: JP 05
    (0x0000BB0D, b'\x06'),  # @0x0BB00+D Y: JP 05
    (0x0000BB1D, b'\x19'),  # @0x0BB10+D Y: JP 17
    (0x0000BB2D, b'\x19'),  # @0x0BB20+D Y: JP 17
    (0x0000BB3D, b'\x19'),  # @0x0BB30+D Y: JP 17
    (0x0000BB4D, b'\x19'),  # @0x0BB40+D Y: JP 17
    (0x0000BB5C, b'\x04\t'),  # @0x0BB50+C X: JP 0b07
    (0x0000BB6D, b'\x1a'),  # @0x0BB60+D Y: JP 18
    (0x0000BBAC, b'\x03\x02'),  # @0x0BBA0+C X: JP 0201
    (0x0000BBBD, b'\x04'),  # @0x0BBB0+D Y: JP 03
    (0x0000BBCD, b'\x06'),  # @0x0BBC0+D Y: JP 05
    (0x0000BBDD, b'\x08'),  # @0x0BBD0+D Y: JP 07
    (0x0000BBED, b'\n'),  # @0x0BBE0+D Y: JP 09
    (0x0000BBFD, b'\x0c'),  # @0x0BBF0+D Y: JP 0b
    (0x0000BC0D, b'\x0e'),  # @0x0BC00+D Y: JP 0d
    (0x0000BC1D, b'\x10'),  # @0x0BC10+D Y: JP 0f
    (0x0000BC2D, b'\x12'),  # @0x0BC20+D Y: JP 11
    (0x0000BC3D, b'\x14'),  # @0x0BC30+D Y: JP 13
    (0x0000BC4D, b'\x16'),  # @0x0BC40+D Y: JP 15
    (0x0000BC5D, b'\x18'),  # @0x0BC50+D Y: JP 17
    (0x0000BC6D, b'\x04'),  # @0x0BC60+D Y: JP 03
    (0x0000BC7D, b'\x06'),  # @0x0BC70+D Y: JP 05
    (0x0000BC8D, b'\x08'),  # @0x0BC80+D Y: JP 07
    (0x0000BC9D, b'\n'),  # @0x0BC90+D Y: JP 09
    (0x0000BCAD, b'\x0c'),  # @0x0BCA0+D Y: JP 0b
    (0x0000BCBD, b'\x0e'),  # @0x0BCB0+D Y: JP 0d
    (0x0000BCCD, b'\x10'),  # @0x0BCC0+D Y: JP 0f
    (0x0000BCDD, b'\x12'),  # @0x0BCD0+D Y: JP 11
    (0x0000BCED, b'\x14'),  # @0x0BCE0+D Y: JP 13
    (0x0000BCFD, b'\x16'),  # @0x0BCF0+D Y: JP 15
    (0x0000BD0D, b'\x18'),  # @0x0BD00+D Y: JP 17
    (0x0000BD1D, b'\x02'),  # @0x0BD10+D Y: JP 01
    (0x0000BD3C, b'\x03\x02'),  # @0x0BD30+C X: JP 0201
    (0x0000BD4D, b'\x04'),  # @0x0BD40+D Y: JP 03
    (0x0000BD5D, b'\x06'),  # @0x0BD50+D Y: JP 05
    (0x0000BD6D, b'\x08'),  # @0x0BD60+D Y: JP 07
    (0x0000BD7D, b'\n'),  # @0x0BD70+D Y: JP 09
    (0x0000BD87, b'\x87'),  # @0x0BD80+7 +7: JP 88
    (0x0000BD8D, b'\x0c'),  # @0x0BD80+D Y: JP 0b
    (0x0000BD97, b'\x7f'),  # @0x0BD90+7 +7: JP 80
    (0x0000BD9D, b'\x0e'),  # @0x0BD90+D Y: JP 0d
    (0x0000BDAD, b'\x10'),  # @0x0BDA0+D Y: JP 0f
    (0x0000BDB7, b'i'),  # @0x0BDB0+7 +7: JP 68
    (0x0000BDBD, b'\x12'),  # @0x0BDB0+D Y: JP 11
    (0x0000BDC7, b'a'),  # @0x0BDC0+7 +7: JP 60
    (0x0000BDCD, b'\x14'),  # @0x0BDC0+D Y: JP 13
    (0x0000BDDD, b'\x16'),  # @0x0BDD0+D Y: JP 15
    (0x0000BDE7, b'Q'),  # @0x0BDE0+7 +7: JP 54
    (0x0000BDED, b'\x18'),  # @0x0BDE0+D Y: JP 17
    (0x0000BDFD, b'\x04'),  # @0x0BDF0+D Y: JP 03
    (0x0000BE0D, b'\x06'),  # @0x0BE00+D Y: JP 05
    (0x0000BE17, b'3'),  # @0x0BE10+7 +7: JP 34
    (0x0000BE1D, b'\x08'),  # @0x0BE10+D Y: JP 07
    (0x0000BE27, b'*'),  # @0x0BE20+7 +7: JP 2c
    (0x0000BE2D, b'\n'),  # @0x0BE20+D Y: JP 09
    (0x0000BE3D, b'\x0c'),  # @0x0BE30+D Y: JP 0b
    (0x0000BE4D, b'\x0e'),  # @0x0BE40+D Y: JP 0d
    (0x0000BE5D, b'\x10'),  # @0x0BE50+D Y: JP 0f
    (0x0000BE6D, b'\x12'),  # @0x0BE60+D Y: JP 11
    (0x0000BE7D, b'\x14'),  # @0x0BE70+D Y: JP 13
    (0x0000BE8D, b'\x16'),  # @0x0BE80+D Y: JP 15
    (0x0000BE9D, b'\x18'),  # @0x0BE90+D Y: JP 17
    (0x0000BEAD, b'\x04'),  # @0x0BEA0+D Y: JP 03
    (0x0000BEBD, b'\x06'),  # @0x0BEB0+D Y: JP 05
    (0x0000BECD, b'\x08'),  # @0x0BEC0+D Y: JP 07
    (0x0000BEDD, b'\n'),  # @0x0BED0+D Y: JP 09
    (0x0000BEED, b'\x0c'),  # @0x0BEE0+D Y: JP 0b
    (0x0000BEFD, b'\x0e'),  # @0x0BEF0+D Y: JP 0d
    (0x0000BF0D, b'\x10'),  # @0x0BF00+D Y: JP 0f
    (0x0000BF1D, b'\x12'),  # @0x0BF10+D Y: JP 11
    (0x0000BF2D, b'\x14'),  # @0x0BF20+D Y: JP 13
    (0x0000BF3D, b'\x16'),  # @0x0BF30+D Y: JP 15
    (0x0000BF47, b'\x89'),  # @0x0BF40+7 +7: JP 88
    (0x0000BF4D, b'\x18'),  # @0x0BF40+D Y: JP 17
    (0x0000BF5D, b'\x04'),  # @0x0BF50+D Y: JP 03
    (0x0000BF6D, b'\x02'),  # @0x0BF60+D Y: JP 01
    (0x0000BF8C, b'\x03\x02'),  # @0x0BF80+C X: JP 0201
    (0x0000BF9D, b'\x04'),  # @0x0BF90+D Y: JP 03
    (0x0000BFAD, b'\x06'),  # @0x0BFA0+D Y: JP 05
    (0x0000BFBD, b'\x08'),  # @0x0BFB0+D Y: JP 07
    (0x0000BFCD, b'\n'),  # @0x0BFC0+D Y: JP 09
    (0x0000BFDD, b'\x0c'),  # @0x0BFD0+D Y: JP 0b
    (0x0000BFED, b'\x0e'),  # @0x0BFE0+D Y: JP 0d
    (0x0000BFFD, b'\x10'),  # @0x0BFF0+D Y: JP 0f
    (0x0000C00D, b'\x12'),  # @0x0C000+D Y: JP 11
    (0x0000C01D, b'\x14'),  # @0x0C010+D Y: JP 13
    (0x0000C02D, b'\x16'),  # @0x0C020+D Y: JP 15
    (0x0000C03D, b'\x18'),  # @0x0C030+D Y: JP 17
    (0x0000C04D, b'\x04'),  # @0x0C040+D Y: JP 03
    (0x0000C05D, b'\x06'),  # @0x0C050+D Y: JP 05
    (0x0000C06D, b'\x08'),  # @0x0C060+D Y: JP 07
    (0x0000C07D, b'\n'),  # @0x0C070+D Y: JP 09
    (0x0000C08D, b'\x0c'),  # @0x0C080+D Y: JP 0b
    (0x0000C09D, b'\x0e'),  # @0x0C090+D Y: JP 0d
    (0x0000C0AD, b'\x10'),  # @0x0C0A0+D Y: JP 0f
    (0x0000C0BD, b'\x12'),  # @0x0C0B0+D Y: JP 11
    (0x0000C0CD, b'\x14'),  # @0x0C0C0+D Y: JP 13
    (0x0000C0DD, b'\x16'),  # @0x0C0D0+D Y: JP 15
    (0x0000C0ED, b'\x02'),  # @0x0C0E0+D Y: JP 01
    (0x0000C10C, b'\x03\x02'),  # @0x0C100+C X: JP 0201
    (0x0000C11D, b'\x04'),  # @0x0C110+D Y: JP 03
    (0x0000C12D, b'\x06'),  # @0x0C120+D Y: JP 05
    (0x0000C13D, b'\x08'),  # @0x0C130+D Y: JP 07
    (0x0000C14D, b'\n'),  # @0x0C140+D Y: JP 09
    (0x0000C15D, b'\x0c'),  # @0x0C150+D Y: JP 0b
    (0x0000C16D, b'\x0e'),  # @0x0C160+D Y: JP 0d
    (0x0000C17D, b'\x10'),  # @0x0C170+D Y: JP 0f
    (0x0000C18D, b'\x12'),  # @0x0C180+D Y: JP 11
    (0x0000C19D, b'\x14'),  # @0x0C190+D Y: JP 13
    (0x0000C1AD, b'\x16'),  # @0x0C1A0+D Y: JP 15
    (0x0000C1BD, b'\x18'),  # @0x0C1B0+D Y: JP 17
    (0x0000C1CD, b'\x04'),  # @0x0C1C0+D Y: JP 03
    (0x0000C1DD, b'\x06'),  # @0x0C1D0+D Y: JP 05
    (0x0000C1ED, b'\x08'),  # @0x0C1E0+D Y: JP 07
    (0x0000C1FD, b'\n'),  # @0x0C1F0+D Y: JP 09
    (0x0000C20D, b'\x0c'),  # @0x0C200+D Y: JP 0b
    (0x0000C21D, b'\x0e'),  # @0x0C210+D Y: JP 0d
    (0x0000C22D, b'\x10'),  # @0x0C220+D Y: JP 0f
    (0x0000C23C, b'!\x02'),  # @0x0C230+C X: JP 1f01
    (0x0000C25C, b'\x03\x02'),  # @0x0C250+C X: JP 0201
    (0x0000C26C, b'\x06\x04'),  # @0x0C260+C X: JP 0503
    (0x0000C27C, b'\x17\x04'),  # @0x0C270+C X: JP 0e03
    (0x0000C28D, b'\x06'),  # @0x0C280+D Y: JP 05
    (0x0000C29D, b'\x08'),  # @0x0C290+D Y: JP 07
    (0x0000C2AD, b'\n'),  # @0x0C2A0+D Y: JP 09
    (0x0000C2BD, b'\x0c'),  # @0x0C2B0+D Y: JP 0b
    (0x0000C2CD, b'\x0e'),  # @0x0C2C0+D Y: JP 0d
    (0x0000C2DD, b'\x10'),  # @0x0C2D0+D Y: JP 0f
    (0x0000C2ED, b'\x12'),  # @0x0C2E0+D Y: JP 11
    (0x0000C2FC, b'\t\x06'),  # @0x0C2F0+C X: JP 0505
    (0x0000C30C, b'\t\x08'),  # @0x0C300+C X: JP 0507
    (0x0000C31C, b'\t\n'),  # @0x0C310+C X: JP 0509
    (0x0000C32C, b'\t\x0c'),  # @0x0C320+C X: JP 050b
    (0x0000C33C, b'\t\x0e'),  # @0x0C330+C X: JP 050d
    (0x0000C34C, b'\t\x10'),  # @0x0C340+C X: JP 050f
    (0x0000C35C, b'\t\x12'),  # @0x0C350+C X: JP 0511
    (0x0000C36C, b'\x18\x06'),  # @0x0C360+C X: JP 1205
    (0x0000C37C, b'\x18\x08'),  # @0x0C370+C X: JP 1207
    (0x0000C38C, b'\x18\n'),  # @0x0C380+C X: JP 1209
    (0x0000C39C, b'\x18\x0c'),  # @0x0C390+C X: JP 120b
    (0x0000C3AC, b'\x18\x0e'),  # @0x0C3A0+C X: JP 120d
    (0x0000C3BC, b'\x18\x10'),  # @0x0C3B0+C X: JP 120f
    (0x0000C3CC, b'\x18\x12'),  # @0x0C3C0+C X: JP 1211
    (0x0000C3DC, b'\x17\x02'),  # @0x0C3D0+C X: JP 1d01
    # --- node group @0x0C63C-0x0C63D (1 runs): menu node X/Y / box size for EN ---
    (0x0000C63C, b'\x0e'),  # @0x0C630+C X: JP 0a
    # --- node group @0x0C684-0x0C685 (1 runs): menu node X/Y / box size for EN ---
    (0x0000C684, b'\x17'),  # @0x0C680+4 ptr/size: JP 14
    ],
}
