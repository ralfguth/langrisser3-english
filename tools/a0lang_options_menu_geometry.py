"""tools/a0lang_options_menu_geometry.py — OPTIONS menu text geometry (our module).

A set of owned byte patches over the **JP** `A0LANG.BIN`, disembarked from 0.2 patch
English Menus v0.2. Kept in its own module so its provenance and purpose stay
unambiguous (this is the OPTIONS/config screen layout — NOT the field 2x2
"Decide/Show Map" box, which is runtime-generated; see archive docs).

We patch the JP baseline. Every byte below is a single tile-X (and one tile-Y)
coordinate in the OPTIONS-screen display list.

What it fixes
-------------
The in-game OPTIONS screen (システム設定) draws its rows from a static A0LANG
display list of 16-byte nodes:

    [ptr 0x0603A4A2][flags 01000000][X Y 00 00][07000000]      (X,Y in TILES)

The JP value-column X positions assume short Japanese labels. Our English
labels are longer ("Display Terrain Effect", "Battle Scenes", ...) so at the JP
positions the value words (On/Off/Fast/...) render ON TOP of the labels
("Onfect", "NormalFast"). 0.2 patch shifted the value columns (and a few label/cursor
cells) right to clear the English text; we adopt those shifts here.

The OPTIONS screen is the A0LANG display-list block under header 0x06033384
(file ~0x253D0), a run of 21 text nodes at 0x25400-0x25550. It has 6 rows at
tile-Y 0x02/0x05/0x08/0x0B/0x0E/0x11 (step 3); only the VALUE columns move:

    Row Y   Option                  value-column X edits (JP -> ours)
    0x02    Message                 Fast 1F->21
    0x05    Time per Turn           Fast 1F->21
    0x08    Display Terrain Effect  On   13->1B   Off 1B->21
    0x0B    PCM                     On   13->1B   Off 1B->21
    0x0E    Battle Scenes           On   12->13   Real 17->19   Off 1E->21
    0x11    BGM                     Stereo 11->13   Mono 1B->21

SCOPE — OPTIONS ONLY (11 bytes). 0.2 patch v0.2 changes 17 A0LANG bytes total, but the
OTHER 6 belong to DIFFERENT menus' display-list blocks and must NOT be applied:
    0x2521C            (hdr 0x060331B4)  — other menu
    0x252B0,0x25300/10/20 (hdr 0x06033290) — other menu (a 4-row menu)
    0x253CC            (hdr 0x060332AC)  — other menu
Those 6 are 0.2 patch's fit for 0.2 patch's OWN English LOAD/SAVE text; applied over our
(different) text they shoved the LOAD title and save rows out of their box.
Our LOAD/SAVE menus stay at the JP positions (which were fine). See
archive/docs/20260608_prog7_options_menu_geometry_re.md (§ A0LANG).

Each entry: (file offset in A0LANG.BIN, replacement byte). JP baseline noted in
the comment so the change is auditable. Same shape as byte_overlays.BYTE_OVERLAYS
so build.py applies it through the same overlay loop.
"""

A0LANG_OPTIONS_MENU_GEOMETRY = {
    "A0LANG.BIN": [
        # OPTIONS value columns only (display-list block @ hdr 0x06033384), by row Y:
        (0x00025488, b"\x21"),  # row Y=02 Message: Fast      1F -> 21
        (0x000254B8, b"\x21"),  # row Y=05 Time per Turn: Fast 1F -> 21
        (0x000254C8, b"\x1b"),  # row Y=08 Display Terrain Effect: On  13 -> 1B
        (0x000254D8, b"\x21"),  # row Y=08 Display Terrain Effect: Off 1B -> 21
        (0x000254E8, b"\x1b"),  # row Y=0B PCM: On  13 -> 1B
        (0x000254F8, b"\x21"),  # row Y=0B PCM: Off 1B -> 21
        (0x00025508, b"\x13"),  # row Y=0E Battle Scenes: On   12 -> 13
        (0x00025518, b"\x19"),  # row Y=0E Battle Scenes: Real 17 -> 19
        (0x00025528, b"\x21"),  # row Y=0E Battle Scenes: Off  1E -> 21
        (0x00025538, b"\x13"),  # row Y=11 BGM: Stereo 11 -> 13
        (0x00025548, b"\x21"),  # row Y=11 BGM: Mono   1B -> 21
    ],
}

# JP baseline bytes (offset -> expected JP value), for an auditable test.
A0LANG_OPTIONS_MENU_GEOMETRY_JP_BASELINE = {
    0x00025488: 0x1F, 0x000254B8: 0x1F, 0x000254C8: 0x13, 0x000254D8: 0x1B,
    0x000254E8: 0x13, 0x000254F8: 0x1B, 0x00025508: 0x12, 0x00025518: 0x17,
    0x00025528: 0x1E, 0x00025538: 0x11, 0x00025548: 0x1B,
}
