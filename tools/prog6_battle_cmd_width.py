"""tools/prog6_battle_cmd_width.py — in-battle command-box width (disembarked).

THREE owned byte patches over the **JP** `LANG/PROG_6.BIN`. Carved out of the
opaque `byte_overlays.py` blob (2026-06-14) into this self-documenting module
(feedback_patch_per_module_closed_scope). The 0.2 patch shipped these as raw
0x0D->0x12/0x0F byte deltas with no provenance; here we own them.

What it does
------------
The in-battle unit command menu (Move/Attack/Magic/Item/Wait...) is drawn from
three A0LANG-style **window descriptor nodes** that ship inside PROG_6.BIN. The
nodes are stacked vertically (posX=2, posY=2 / 6 / 10). Each node's `width`
field is JP 0x0D (13 half-width 8px cells); the English labels are wider than
the Japanese ones, so each box is widened to fit.

Load base — 0x0609A800 (pinned by internal pointer self-consistency)
-------------------------------------------------------------------
PROG_6 is overlay-loaded at the same region as PROG_7 (0x0609A800). Proof
without a WRAM dump: each window node's child pointer (0x060C734C / 0x060C73DC /
0x060C7554) resolves under this base to a valid in-file text node
(`01 00 00 00  03 01 00 00  07 00 00 00  00 00 00 00` = type 1 text, X=3 Y=1,
attr 7) right next to its parent window node. All three resolve in-file; no
other base does.

Node format (16 bytes), at file offsets 0x2CBA0 / 0x2CC80 / 0x2CDD8:

    [posX u8][posY u8][00 00][width u8][height u8][00 00][child ptr u32][term u32]

The width field is node+4. Patched sites (file offset = node+4):

    0x2CBA4  node@0x2CBA0  pos(2, 2)  width 0x0D -> 0x12 (+5)  child 0x060C734C
    0x2CC84  node@0x2CC80  pos(2, 6)  width 0x0D -> 0x0F (+2)  child 0x060C73DC
    0x2CDDC  node@0x2CDD8  pos(2,10)  width 0x0D -> 0x0F (+2)  child 0x060C7554

Cross-reference: the box-width value (0x0D=13 / 0x11=17 by flag) is what the
PROG_3 box dispatcher `FUN_0607d168` reads (archive/docs/
20260608_menu_box_geometry_re.md §"Text placement & box width"). Widening it is
functional, not a cosmetic inherited tweak — without it the English command
labels overrun the box border.
"""

PROG6_BATTLE_CMD_WIDTH = {
    "LANG/PROG_6.BIN": [
        (0x0002CBA4, b"\x12"),   # JP 0x0D -> 0x12 (+5) — command box row 1
        (0x0002CC84, b"\x0F"),   # JP 0x0D -> 0x0F (+2) — command box row 2
        (0x0002CDDC, b"\x0F"),   # JP 0x0D -> 0x0F (+2) — command box row 3
    ],
}
