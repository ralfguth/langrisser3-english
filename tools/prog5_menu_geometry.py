"""tools/prog5_menu_geometry.py — PROG_5 menu/display-list geometry (disembarked).

63 owned byte patches over the **JP** `LANG/PROG_5.BIN`, carved out of the opaque
byte_overlays blob (2026-06-14) into this self-documenting module
(feedback_patch_per_module_closed_scope).

What it is
----------
PROG_5 holds A0LANG-style display-list **node groups** for the in-battle / menu
UI. Every patched byte is a layout coordinate — an item's X/Y position, or a
window's width/height/size — nudged from the Japanese value so the wider English
labels fit (same kind of geometry as tools/prog4_field_box_geometry.py and
tools/a0lang_options_menu_geometry.py). None of these are text.

Load base = 0x06089000 (pinned two independent ways)
----------------------------------------------------
1. WRAM signature-match: a distinctive 32-byte slice of PROG_5 appears at WRAM
   0x06089100 in all 7 Ymir dumps (~/romhack/ymir-dumps/*/wram-hi.bin), and the
   slice is NOT shared with PROG_4 (the two files differ at file 0x100), so the
   match is discriminating. PROG_5 and PROG_4 are overlay-swapped at the SAME
   region 0x06089000 (loaded at different times).
2. Internal pointer self-consistency under that base: each node's child pointer
   (e.g. 0x060893DC -> file 0x3DC, 0x0609191C -> file 0x891C) resolves to valid
   in-file PROG_5 node data. (Pointers of the form 0x0603A4xx are work-RAM
   scratch — cursor/menu-state buffers — not file data; see
   archive/docs/20260608_menu_box_geometry_re.md.)

Node format (16 bytes), two variants seen
------------------------------------------
    item node:   [X u8][Y u8][00 00][type u32][child/text ptr u32][attr u32]
    window node: [X u8][Y u8][00 00][w u8][h u8][00 00][child ptr u32][attr u32]

So a run at node+0/+1 moves the element (X/Y), node+4/+5 resizes a window (w/h),
and node+8.. touches the body (child ptr / attr / count). The per-run comments
record the node base, the field, and the JP baseline bytes.

Provenance note
---------------
The geometric effect of every run (shift / widen to fit EN) is established by the
node-format analysis above and truth-locked vs the live JP ISO
(tests/test_prog5_menu_geometry.py). Mapping each node group to its exact on-
screen menu (Magic vs Item vs status sub-window, etc.) is confirmed empirically
in the Phase-A playtest (roadmap T12 / disembark Etapa 7) — the A0LANG node trees
are pointer-walked, so there is no static code xref to name them from.
"""

PROG5_MENU_GEOMETRY = {
    "LANG/PROG_5.BIN": [
    # --- node group @0x08950-0x089A1 (3 runs): menu item X/Y + box size for EN ---
    (0x00008950, b'\x10'),  # node@0x08950+0 X: JP 0b
    (0x00008960, b'\r\x05'),  # node@0x08960+0 X: JP 0806
    (0x000089A0, b'\x02'),  # node@0x089A0+0 X: JP 01
    # --- node group @0x08A00-0x08A51 (3 runs): menu item X/Y + box size for EN ---
    (0x00008A00, b'\x12'),  # node@0x08A00+0 X: JP 0d
    (0x00008A10, b'\x0b\x05'),  # node@0x08A10+0 X: JP 0606
    (0x00008A50, b'\x06'),  # node@0x08A50+0 X: JP 0c
    # --- node group @0x08AB0-0x08B01 (3 runs): menu item X/Y + box size for EN ---
    (0x00008AB0, b'\x10'),  # node@0x08AB0+0 X: JP 0b
    (0x00008AC0, b'\r\x05'),  # node@0x08AC0+0 X: JP 0806
    (0x00008B00, b'\x02'),  # node@0x08B00+0 X: JP 01
    # --- node group @0x08B60-0x08CC1 (13 runs): menu item X/Y + box size for EN ---
    (0x00008B60, b'\x12'),  # node@0x08B60+0 X: JP 0d
    (0x00008B70, b'\x0b\x05'),  # node@0x08B70+0 X: JP 0606
    (0x00008BB0, b'\x06'),  # node@0x08BB0+0 X: JP 0c
    (0x00008BE0, b'\x00\r\x00\x00\x14'),  # node@0x08BE0+0 X/w: JP 010d000012
    (0x00008BF4, b'\x14\r\x00\x00\x14'),  # node@0x08BF0+4 size/w: JP 150d000012
    (0x00008C19, b'\x04'),  # node@0x08C10+9 body: JP 03
    (0x00008C29, b'\x04'),  # node@0x08C20+9 body: JP 03
    (0x00008C39, b'\x04'),  # node@0x08C30+9 body: JP 03
    (0x00008C69, b'\x04'),  # node@0x08C60+9 body: JP 03
    (0x00008C79, b'\x04'),  # node@0x08C70+9 body: JP 03
    (0x00008C89, b'\x04'),  # node@0x08C80+9 body: JP 03
    (0x00008CA8, b'\x00\x01\x00\x00\x13'),  # node@0x08CA0+8 body: JP 0101000006
    (0x00008CBC, b'\x15\x01\x00\x00\x13'),  # node@0x08CB0+C attr: JP 2101000006
    # --- node group @0x08D04-0x08DB1 (9 runs): menu item X/Y + box size for EN ---
    (0x00008D04, b'\x0f'),  # node@0x08D00+4 size/w: JP 0c
    (0x00008D24, b'\x0f'),  # node@0x08D20+4 size/w: JP 0c
    (0x00008D44, b'\x0f'),  # node@0x08D40+4 size/w: JP 0c
    (0x00008D64, b'\x0f'),  # node@0x08D60+4 size/w: JP 0c
    (0x00008D84, b'\x00\x03\x00\x00\x18'),  # node@0x08D80+4 size/w: JP 0303000013
    (0x00008D98, b'\r'),  # node@0x08D90+8 body: JP 0a
    (0x00008DA0, b'\r'),  # node@0x08DA0+0 X: JP 0a
    (0x00008DA8, b'\r'),  # node@0x08DA0+8 body: JP 0a
    (0x00008DB0, b'\r'),  # node@0x08DB0+0 X: JP 0a
    # --- node group @0x08E54-0x08E55 (1 run): box size for EN ---
    (0x00008E54, b'\x14'),  # node@0x08E50+4 size/w: JP 09
    # --- node group @0x08EC0-0x08FAA (14 runs): menu item X/Y + box size for EN ---
    (0x00008EC0, b'\x19'),  # node@0x08EC0+0 X: JP 16
    (0x00008ED4, b'\x0e\x03'),  # node@0x08ED0+4 size/w: JP 1701
    (0x00008EE4, b'\x12'),  # node@0x08EE0+4 size/w: JP 09
    (0x00008EF4, b'\x12'),  # node@0x08EF0+4 size/w: JP 09
    (0x00008F05, b'\x04'),  # node@0x08F00+5 h: JP 01
    (0x00008F15, b'\x05'),  # node@0x08F10+5 h: JP 02
    (0x00008F24, b'\x02'),  # node@0x08F20+4 size/w: JP 01
    (0x00008F34, b'\x02\x04'),  # node@0x08F30+4 size/w: JP 0c01
    (0x00008F44, b'\x0c\x03'),  # node@0x08F40+4 size/w: JP 1501
    (0x00008F54, b'\x10'),  # node@0x08F50+4 size/w: JP 07
    (0x00008F64, b'\x10'),  # node@0x08F60+4 size/w: JP 07
    (0x00008F75, b'\x04'),  # node@0x08F70+5 h: JP 01
    (0x00008F85, b'\x05'),  # node@0x08F80+5 h: JP 02
    (0x00008FA4, b'\x07\x10\x00\x00\x1a\x07'),  # node@0x08FA0+4 size/w: JP 0c0f00001a04
    # --- node group @0x09130-0x09131 (1 run): menu item X for EN ---
    (0x00009130, b'\x16'),  # node@0x09130+0 X: JP 15
    # --- node group @0x091C0-0x091C5 (1 run): menu item X/size for EN ---
    (0x000091C0, b'\x0b\x11\x00\x00\x1c'),  # node@0x091C0+0 X/size: JP 0e11000016
    # --- node group @0x09244-0x09245 (1 run): box size for EN ---
    (0x00009244, b'\x16'),  # node@0x09240+4 size/w: JP 15
    # --- node group @0x09374-0x09375 (1 run): box size for EN ---
    (0x00009374, b'\x16'),  # node@0x09370+4 size/w: JP 15
    # --- node group @0x0956C-0x0956D (1 run): node attr for EN ---
    (0x0000956C, b'\x1c'),  # node@0x09560+C attr: JP 13
    # --- node group @0x096A4-0x096B5 (2 runs): box size for EN ---
    (0x000096A4, b'\x1c'),  # node@0x096A0+4 size/w: JP 15
    (0x000096B4, b'\x03'),  # node@0x096B0+4 size/w: JP 05
    # --- node group @0x09788-0x09842 (10 runs): menu item X/Y + body for EN ---
    (0x00009788, b'\x17'),  # node@0x09780+8 body: JP 13
    (0x00009798, b'\x17'),  # node@0x09790+8 body: JP 13
    (0x000097A8, b'\x17'),  # node@0x097A0+8 body: JP 13
    (0x000097B8, b'\x17'),  # node@0x097B0+8 body: JP 13
    (0x000097C8, b'\x17'),  # node@0x097C0+8 body: JP 13
    (0x000097D8, b'\x17'),  # node@0x097D0+8 body: JP 13
    (0x000097E8, b'\x07'),  # node@0x097E0+8 body: JP 05
    (0x000097F8, b'\x0b\x11'),  # node@0x097F0+8 body: JP 0a10
    (0x0000981C, b'\x1b\x14'),  # node@0x09810+C attr: JP 1713
    (0x00009840, b'\t\x11'),  # node@0x09840+0 X: JP 0810
    ],
}
