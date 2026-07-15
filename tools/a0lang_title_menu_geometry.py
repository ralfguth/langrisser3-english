"""tools/a0lang_title_menu_geometry.py — title START/LOAD/OPTIONS box geometry
(our module).

Owned byte patches over the JP `A0LANG.BIN` (load base 0x0600E000). The title
START/LOAD/OPTIONS menu is an A0LANG display-list group (RAM 0x060333C4); we
narrow its box from the right and centre it on screen.

WHY THIS PATCHES CODE, NOT THE STRUCT (instrumented-Ymir + Ghidra, 2026-06-28,
skills `lang3-ui-text-debug` + `saturn-ghidra-re`):
The static group struct at file 0x253C4 (+4 parent X, +8 box width) is a DEAD
DEFAULT. At boot the menu is rebuilt by code — the START/LOAD/OPTIONS installer
near PC 0x06015D16 writes the LIVE geometry with `mov #imm,r1` / `mov.b` pairs:

    0x06015CD2  E10B  mov #0x0b,r1   ; 11  -> group +4 parent X   (file 0x07CD2/3)
    0x06015CDA  E112  mov #0x12,r1   ; 18  -> group +5 parent Y
    0x06015CE2  E113  mov #0x13,r1   ; 19  -> group +8 box WIDTH   (file 0x07CE2/3)
    0x06015CE8  E108  mov #0x08,r1   ; 8   -> group +9 box HEIGHT

So the effective bytes are the 8-bit immediates inside those opcodes. The JP
code already writes width 19 (the "22" in the struct is the dead default that
the code overwrites — and was the reason the first, struct-based, cut of this
patch did nothing in-game while the LOAD title text move DID stick).

Fix (user spec, eye-tuned by playtest 2026-06-28): narrow + CENTRE.
parent X 11 -> 14, width 19 -> 12 → box cells 14..26, centre 20. Y/height
untouched. The text and cursor are parent-relative so they follow automatically.
Tuning history: first cut parent X 13 / width 14 (centre 20) read slightly LEFT;
nudged to parent X 14 / width 13 (right edge 27); then the user trimmed one more
cell (8px) off the RIGHT only, keeping the box position → parent X 14 / width 12,
right edge 26, centre back on cell 20.

PATH B (no-save START/OPTIONS layout near PC 0x06015D5E) reuses ONE immediate
(0x06015D72 = 0x13) for BOTH parent Y and width, so it cannot be narrowed
without splitting the instruction. Left to a follow-up; the common (has-save)
state is Path A, patched here.

Each entry: (A0LANG.BIN file offset, replacement byte). JP baseline noted in the
comment + the truth-lock test. Same shape as byte_overlays.BYTE_OVERLAYS so
build.py applies it through the same overlay loop.
"""

A0LANG_TITLE_MENU_GEOMETRY = {
    "A0LANG.BIN": [
        (0x00007CD3, b"\x0e"),  # mov #imm,r1 @0x06015CD2 parent X: 0B(11) -> 0E(14)  [centre, eye-tuned]
        (0x00007CE3, b"\x0c"),  # mov #imm,r1 @0x06015CE2 box width: 13(19) -> 0C(12)  [eye-tuned, right edge 26]
    ],
}

# JP baseline bytes (offset -> expected JP value), for an auditable truth-lock test.
A0LANG_TITLE_MENU_GEOMETRY_JP_BASELINE = {
    0x00007CD3: 0x0B,
    0x00007CE3: 0x13,
}
