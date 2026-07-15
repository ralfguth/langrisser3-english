"""tools/prog4_spell_name_table.py — magic-icon spell-name table (declared).

The PROG_4 magic-cast icon name table at file 0x7F80 (runtime 0x06090F80, load
base 0x06089000). 33 uppercase spell labels (TELEPORT, HEAL3, FIRE, ...) shown
on the magic-selection icons.

STATUS: declared TEXT, shipped BYTE-IDENTICAL (user decision 2026-06-14).
-------------------------------------------------------------------------------
This is the inherited 0.2-patch English text. We OWN it here (declared, not an
opaque blob), but we do NOT re-encode it yet: converting it to a script-driven,
font-aware encoder (like tools/prog_text_tools.py does for the PROG_3 tables) is
deferred to Phase B / roadmap T28. The magic tables are crash-prone
(memory feedback_magic_table_fragile): entry lengths must never change without
Ghidra RE first. So this module relocates the bytes into a self-documenting home
and stops there.

Structure (RE)
--------------
A stride-0xC array: each entry is a half-width katakana (JP) / ASCII (EN) name,
NUL-terminated, followed by per-entry level/icon metadata (the 0x01/0x02/0x03
bytes are the Heal/Force spell levels). Index-accessed — the region is read by
PROG_4 FUN_060912e8 (confirmed by Ghidra xref: instruction @0x06091514 ->
0x060910A4, the table tail). Because the access is base+index*stride, the
decompiler shows few direct refs.

The three runs below are the offsets where the EN text differs from the JP
katakana baseline (the 4-byte gaps at 0x8008 / 0x8010 are bytes EN and JP share,
so no run covers them). Verified end-to-end by tests/test_prog4_spell_name_table.py
(decodes to the 33 canonical names + truth-lock vs the live JP ISO).
"""

# Disembarked 2026-06-14 verbatim from byte_overlays.PROG_4_OVERLAY (offsets
# < 0x8100). BYTE-IDENTICAL — do not re-pack here; that is Phase B work.
PROG4_SPELL_NAME_TABLE = {
    "LANG/PROG_4.BIN": [
        (0x00007F80, b'TELEPORT\x00F.HEAL3\x00\x03\x00\x00F.HEAL2\x00\x00\x02\x00\x00F.HEAL1\x00\x00\x01\x00\x00HEAL3\x00\x00\x00HEAL2\x00\x00\x00HEAL1\x00\x00\x00RESIST\x00\x00QUICK\x00\x00\x00ATTACK2\x00ATTACK1\x00PROTECT2\x00\x00\x00\x00PROTECT1\x00\x00\x00\x00DECLINE\x00MUTE'),
        (0x0000800C, b'ZONE'),
        (0x00008014, b'CONFUSE\x00SLEEP\x00\x00\x00BLAST\x00MP DRAIN\x00HP DRAIN\x00T.UNDEAD\x00\x00\x00\x00HOLY BLZ\x00METEOR\x00EARTHQKE\x00TORNADO\x00WINDCUTR\x00\x00\x00T.STORM\x00\x00\x00\x00THUNDER\x00BLIZZARD\x00FREEZE\x00\x00FIREBALL\x00\x00\x00\x00FIRE\x00'),
    ],
}
