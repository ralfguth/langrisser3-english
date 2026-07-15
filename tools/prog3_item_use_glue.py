"""tools/prog3_item_use_glue.py — item-use message の-glue -> 's.

TWO owned byte patches over the **JP** `LANG/PROG_3.BIN`, in the same system-
message builder as the stat-up template (FUN_0607c430, load base 0x06052800).

Bug (user playtest 2026-06-13): the item-use line rendered
"TiarisboNectar was used!" — the JP possessive particle の (tile 0x5C) sits
between the name and the item, and our repainted font draws tile 0x5C as the
"bo" bigram.

RE (Ghidra, opcode 0x13 = "[Name]の[Item]をつかった！"):
    0x2A0C3  mov #0x5c,r6 ; mov.w r6,@r8   の glue, path A
             (after the name fn PTR_FUN_0607c98c, before the item-name
              table DAT_0607c988)
    0x2A11B  mov #0x5c,r7 ; mov.w r7,@r8   の glue, path B (second name path)

Both are NAME-possessive glues — identical role to the stat-up sites at
0x29DCF/0x29E09 (see prog3_statup_template.py). Substituting:

    0x5C (の) -> 0x2C   tile 44 = our 's glyph. Tile 44 is a LOW slot on purpose:
                        SH-2 `mov #imm8` SIGN-EXTENDS, so a glue tile index
                        >= 0x80 becomes 0xFFxx and renders BLANK.

composes "[Name]'s[Item] was used!" (e.g. "Tiaris'sMagic Herb was used!").
The trailing " was used!" is a fntsys3 suffix record (already English).

Known gap: the item name is appended with NO leading space (unlike the
stat-up suffixes whose leading space separates them), so the line GLUES:
"Tiaris'sMagic Herb". A 2026-06-13 attempt to add the space by repointing の
to a packed "'s "+blank tile at 0xD4 FAILED — 0xD4 >= 0x80 sign-extended to
0xFFD4 (out of range -> blank), proven in-game (log: val=0000FFD4) and now
guarded by tests/test_prog3_glue_tile_signsafe.py. Adding the separator needs
a SECOND sign-safe (<= 0x7F) packed-'s slot; deferred to the FONT.BIN refactor
(memory reference_engine_immediate_tile_constraint), which must reserve a low
band for engine `mov #imm` tiles.
"""

PROG3_ITEM_USE_GLUE = {
    "LANG/PROG_3.BIN": [
        (0x0002A0C3, b"\x2c"),   # の -> 's tile 44 (sign-safe; item-use path A)
        (0x0002A11B, b"\x2c"),   # の -> 's tile 44 (sign-safe; item-use path B)
    ],
}

# JP baseline bytes at the patch sites — verified against the pristine JP ISO
# by tests/test_prog3_item_use_glue.py before any build.
JP_BASELINE = {
    0x0002A0C3: 0x5C,
    0x0002A11B: 0x5C,
}
