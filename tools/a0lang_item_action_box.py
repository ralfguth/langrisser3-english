"""tools/a0lang_item_action_box.py — item-action confirmation box glue fix.

TWO owned byte patches over the **JP** `A0LANG.BIN`. See
tests/test_a0lang_item_action_box.py.

Bug (RE + RAM dumps 2026-06-13): the field item-action box rendered
"Magic Herb**cp**Use Equipment" instead of the JP "魔力草を使用します"
("Will use the Magic Herb").

RE (Ghidra: A0LANG `FUN_0601299c`, caller PROG_4 `FUN_0608f410` dispatch via
ptr @ PROG_4 file 0x7A0C; confirmed against live RAM dumps
`~/romhack/ymir-dumps/{04,JP-02}`). The box is assembled in FIXED Japanese
SOV slots in the work buffer at 0x0604EE10:

    [item name fntsys10] + を + [fntsys1 rec14 使用 / rec13 装備] + [fntsys1 rec96 します]

with the を written as a HARDCODED `mov #0x7C,r0; mov.w r0,@r7` at A0LANG
file 0x49CA/0x49CC, and the piece-B index (rec96) read from the constant
DAT_06012a74 = 0x00C0 (file 0x4A74-0x4A75; byte-offset 0xC0 into the fntsys1
offset table = word index 96). Two things were wrong for English:

  - tile 0x7C (JP を) draws as the "cp" bigram in our repainted font;
  - fntsys1 rec96 (JP します, the polite verb-ending glue) is "Equipment" in
    our EN fntsys1 — it CANNOT be blanked: rec96 is ALSO the X=12 centre piece
    of the PROG_4 equip-title screen (test_prog4_equip_title). So we leave the
    record alone and reroute THIS box's piece-B pointer instead.

Fix (surgical — the engine slots are immutable here):

    0x49CB  0x7C (の-family glue を) -> 0x01   tile 0x01 = ": " (colon +
            half-width space). SIGN-SAFE: SH-2 `mov #imm8` sign-extends, so the
            tile index MUST be <= 0x7F (a >= 0x80 immediate becomes 0xFFxx ->
            blank; the 0xD4 trap). 0x01 qualifies.

    0x4A75  0xC0 -> 0xF8   piece-B index: rec96 (byte 0xC0) -> rec124 (byte
            0xF8), an EMPTY fntsys1 record. The builder's piece-B copy then
            appends nothing, dropping the します verb-ending the way English
            wants. This is a CONSTANT-POOL value (loaded via `mov.w @(pc)`),
            NOT a `mov #imm`, so the sign-extension rule does not apply. Only
            the use(param=1)/equip(param=0) confirmation boxes read this index;
            the param_2==4/else modes use DAT_06012a76/78, so they are
            untouched. rec96 ("Equipment") stays intact for the equip-title.

Composed result: "[item]: [Use/Equip]"  e.g. "Magic Herb: Use".

*** FONT REFACTOR INVARIANT ***
tile 0x01 = ": " is now LOAD-BEARING: it is the immediate of this engine
`mov #imm` separator. The font/encoder refactor MUST keep a ": " (colon +
half-width space) glyph at a LOW (<= 0x7F) tile index. See memory
reference_engine_immediate_tile_constraint and
archive/docs/20260607_font_encoder_refactor_roadmap.md.
The repoint target (fntsys1 rec124) MUST stay empty — guarded by the test.
"""

A0LANG_ITEM_ACTION_BOX = {
    "A0LANG.BIN": [
        (0x000049CB, b"\x01"),   # を(0x7C) -> tile 0x01 ": " (sign-safe separator)
        (0x00004A75, b"\xf8"),   # piece-B index 0xC0 (rec96) -> 0xF8 (rec124, empty)
    ],
}

# JP baseline bytes at the patch sites — verified against the live JP A0LANG.BIN
# by tests/test_a0lang_item_action_box.py before any build.
A0LANG_ITEM_ACTION_BOX_JP_BASELINE = {
    0x000049CB: 0x7C,            # JP glue tile is を
    0x00004A75: 0xC0,            # JP piece-B index = rec96 (byte-offset 0xC0)
}
