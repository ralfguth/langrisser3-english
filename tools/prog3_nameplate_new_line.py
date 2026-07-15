"""tools/prog3_nameplate_new_line.py — our nameplate newline engine patch.

A SINGLE owned byte patch over the **JP** `LANG/PROG_3.BIN`. This is NOT a
0.2 patch overlay: it is our own engine RE (v0.6), kept in its own module so its
provenance stays unambiguous and never gets mistaken for 0.2 patch-derived bytes
in `tools/byte_overlays.py`.

We patch the JP baseline — not 0.2 patch. The baseline byte at 0x2CB77 is 0x01.

What it does
------------
The balloon composer (PROG_3, runtime 0x0607F364) writes a value into the
nameplate stack slot right after the speaker name. The JP game writes
`<$0001>` there — tile index 1, the `:` glyph — producing an inline layout:

    [NAMEPLATE]<$0001>[DIALOGO]      ->   one line, ":" between name and text

We change the immediate at file offset 0x2CB77 (0x01 -> 0xFC), turning
`mov #1, R0` (E001) into `mov #-4, R0` (E0FC). The following
`mov.w R0, @R14` at 0x2CB7E then stores 0xFFFC — the engine's newline
control code — so the composer emits, after the nameplate:

    [NAMEPLATE]<$FFFC>[DIALOGO]      ->   [NAMEPLATE]
                                          [DIALOGO]      (two lines)

The dispatcher/layout already honours `<$FFFC>` as a newline in dialogue
text, so we reuse the engine's own control code rather than inventing one.

Patch site (file offsets in LANG/PROG_3.BIN)
--------------------------------------------
    0x2CB64  composer prologue   2f86 2f96 2fa6 2fb6 2fe6 4f22 7ffc 6ef3 6b53
    0x2CB76  immediate           E001 (JP) -> E0FC (ours)   <-- the patch
    0x2CB77    `--- the single byte we own: 0x01 -> 0xFC
    0x2CB7E  store               2E01  mov.w R0, @R14        (must stay)

Locked by tests/test_prog3_nameplate_new_line.py (verified against the live
JP baseline extracted from LANG3_JP_DIR, not a stored blob).

See archive/docs/20260511_colon_phase7_composer_found.md for the full RE.
"""

# (file offset in LANG/PROG_3.BIN, replacement bytes). Same shape as
# byte_overlays.BYTE_OVERLAYS so build.py applies it through the same loop.
PROG3_NAMEPLATE_NEW_LINE = {
    "LANG/PROG_3.BIN": [
        (0x0002CB77, b"\xfc"),  # E001 -> E0FC: composer emits <$FFFC>, not <$0001>
    ],
}
