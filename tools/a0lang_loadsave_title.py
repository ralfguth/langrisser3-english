"""tools/a0lang_loadsave_title.py — LOAD/SAVE-screen title text centring
(our module).

One owned byte patch over the JP `A0LANG.BIN` (load base 0x0600E000). The
load/save screen's title is a SINGLE A0LANG display-list node that BOTH the LOAD
mode and the SAVE mode reuse — proven by Ghidra (2026-06-28): two installers
write the mode-selected fntsys record into the same `node+0xC`:

    LOAD mode: PC 0x060142EC  `mov.l r1,@(0xc,r3)`   r3 = node 0x06033218
    SAVE mode: PC 0x06014AF0  `mov.l r1,@(0xc,r3)`   r3 = node 0x06033218

So there is NO separate SAVE node; centring this one node centres both "LOAD"
and "SAVE". (Distinct from the title menu box `a0lang_title_menu_geometry.py`,
whose geometry is code-built — see that module.)

Node format (16 B): `[type u32][X u8][Y u8][pad u16][attr u32][ptr u32]`, X/Y in
8px cells. Group struct +4/+5 = parent X/Y (added to node X/Y AND = box top-left),
+8/+9 = box width/height.

LOAD/SAVE title, node RAM 0x06033218 (A0LANG file 0x25218), group RAM 0x06033238
(instrumented-Ymir REND/WALK, 2026-06-27): frame box (14,2) size (12,4), centre
X=20; node X=2 → screen X=16. The JP zenkaku ＬＯＡＤ / ＳＡＶＥ are 8 cells (centred
at X=16); our half-width ASCII "LOAD" / "SAVE" are 4 cells, so at X=16 they render
LEFT of the box centre. Fix: node X 2 -> 4 → text spans cells 18..22, centred in
the 14..26 box. Frame size unchanged (text-only move). Both words are 4 cells, so
the single X=4 centres LOAD and SAVE identically.

Each entry: (A0LANG.BIN file offset, replacement byte). Same shape as
byte_overlays.BYTE_OVERLAYS so build.py applies it through the overlay loop.
"""

A0LANG_LOADSAVE_TITLE = {
    "A0LANG.BIN": [
        (0x0002521C, b"\x04"),  # LOAD/SAVE title node X: 02 -> 04  [centre 4-cell text]
    ],
}

# JP baseline byte (offset -> expected JP value), for an auditable truth-lock test.
A0LANG_LOADSAVE_TITLE_JP_BASELINE = {
    0x0002521C: 0x02,
}
