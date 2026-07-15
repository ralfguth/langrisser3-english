"""tools/prog3_statup_template.py — our stat-up message-template patch.

SIX owned byte patches over the **JP** `LANG/PROG_3.BIN`. These are OURS
(RG, ~v0.5 phase 3a, commit 717d850) — NOT 0.2 patch bytes. They lived mislabeled
inside `byte_overlays.PROG_3_OVERLAY` until 2026-06-10 (roadmap T08); this
module gives them the self-documenting home the patch-per-module directive
requires.

What it does
------------
`FUN_0607c430` (file 0x29A30, load base 0x06052800) is the PROG_3 system-
message builder: a switch on the message opcode that composes each line
from name/value tiles, HARDCODED TILE IMMEDIATES, and fntsys3 suffix
records (e.g. rec24 ' Level', rec0 ' went up!', rec29 ' went down!').

The JP code writes two glue tiles between the pieces:

    tile 0x5C — the JP possessive particle の glyph
    tile 0x39 — a JP separator glyph

In our font those slots hold OTHER glyphs (the JP layout was repainted),
so the EN build must substitute:

    0x5C -> 0x2C  tile 44 = our `'s` glyph. 44 was drawn at a LOW slot
                  on purpose: SH-2 `mov #imm,Rn` immediates are 8-bit, so
                  the normal `'s` bigram tile (1498) cannot be encoded.
                  Tile 44 is guarded by the font CSV truth-lock.
    0x39 -> 0x00  tile 0 = full-width blank (the only index that never
                  moves on font rebuilds).

Composed result (level-change template, opcode 0x12 family):

    [NAME] ['s] [rec24 ' Level'] [blank] [digit] [rec ' went up!']
            0x2C       |           0x00     |
                       |                    `- tiles 7-16, value+7
                       `- the LEADING SPACE in fntsys3 rec24 is the
                          half-width gap after 's — load-bearing
                          (locked by tests/test_prog3_statup_template.py)

The two 0x2C sites are the two name+'s template paths (opcodes 0x12 and
the later level-up case); the FIVE 0x00 sites are the separator slots
before the numeric value in the stat/MP/item-effect templates (those
paths start with the stat-name record directly, hence blank + centered
digit + suffix-with-own-leading-space — no double gap).

All five 0x39 sites were enumerated by disassembling FUN_0607c430
(2026-06-13): mov #0x39 at runtime 0x0607C5E8/C622/C6B6/C72C/C782 →
file +1 = 0x29DE9/29E23/29EB7/29F2D/29F83. The original sweep patched
four and missed 0x29F83 (opcode 0x15).

Patch sites (file offsets in LANG/PROG_3.BIN; JP baseline byte first)
---------------------------------------------------------------------
    0x29DCF  0x5C -> 0x2C   's  (opcode 0x12: NAME's Level n went down!)
    0x29DE9  0x39 -> 0x00   blank before the value (same template)
    0x29E09  0x5C -> 0x2C   's  (second name+stat template path)
    0x29E23  0x39 -> 0x00   blank before the value
    0x29EB7  0x39 -> 0x00   blank before the value (MP-recovery template)
    0x29F2D  0x39 -> 0x00   blank before the value (generic stat-up)
    0x29F83  0x39 -> 0x00   blank before the value (opcode 0x15, item-
                            effect "MP/HP n recovered"; "MPak" fix)

RE artifacts: /home/ralf/romhack/langrisser3-english-reverse-engineering/
statup_template/decompile.txt; format notes in
archive/docs/20260609_fntsys_systems_and_encoder.md §4.
"""

# (file offset in LANG/PROG_3.BIN, replacement bytes). Same shape as
# byte_overlays.BYTE_OVERLAYS so build.py applies it through the same loop.
PROG3_STATUP_TEMPLATE = {
    "LANG/PROG_3.BIN": [
        (0x00029DCF, b"\x2c"),  # 0x5C(の) -> tile 44 's
        (0x00029DE9, b"\x00"),  # 0x39 -> tile 0 blank
        (0x00029E09, b"\x2c"),  # 0x5C(の) -> tile 44 's
        (0x00029E23, b"\x00"),  # 0x39 -> tile 0 blank
        (0x00029EB7, b"\x00"),  # 0x39 -> tile 0 blank
        (0x00029F2D, b"\x00"),  # 0x39 -> tile 0 blank
        (0x00029F83, b"\x00"),  # 0x39 -> tile 0 blank (opcode 0x15, item-
                                # effect value: "MP/HP n recovered"). Missed by
                                # the original 4-site sweep; user saw "MPak 18
                                # recovered" (0x39 = our 'ak' bigram), playtest
                                # 2026-06-13.
    ],
}

# JP baseline bytes at the same offsets, for the truth-lock test.
JP_BASELINE = {
    0x00029DCF: 0x5C,
    0x00029DE9: 0x39,
    0x00029E09: 0x5C,
    0x00029E23: 0x39,
    0x00029EB7: 0x39,
    0x00029F2D: 0x39,
    0x00029F83: 0x39,
}
