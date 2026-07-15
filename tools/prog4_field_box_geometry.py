"""tools/prog4_field_box_geometry.py — field 2x2 command-box geometry fix.

FOUR owned byte patches over the **JP** `LANG/PROG_4.BIN` (roadmap T11,
2026-06-10). Ours (RG) — 0.2 patch never fixed this geometry; his v0.2 worked
around it with text hacks ('Decide' truncated to 'Decid' on screen, a
`<$0000><$0000>` indent inside the 'map arrangement' record).

What it does
------------
The field command box (JP 決定/マップ参照 // 取消/戻る, EN Confirm/View Map //
Cancel/Return — the box on pressing C over empty ground) is drawn by the
A0LANG display-list walker (`FUN_06018258`) from a static node group that
ships INSIDE PROG_4.BIN. Load base 0x06089000 (pinned 2026-06-10 by
matching WRAM dump bytes to the file) puts the group at RAM 0x06093EE8.

Node format (16 bytes): [type u32][X u8][Y u8][pad u16][attr u32][ptr u32]
X/Y/pos/size are half-width 8px cells (unit proven twice: 0.2 patch's 'Decide'
lost exactly its last half-tile under column 2, and the playtest
screenshot puts the window edges at posX*8 / (posX+width)*8 px). One
16x16 glyph tile = 2 cells. String ptrs are installed per-frame by
PROG_4 `FUN_0608e9d0` case 2 (fntsys1 records via `base + offtbl[id]*2`):
rec48 決定, rec152 マップ参照, rec11 取消, rec120 戻る.

JP group (file offsets):

    0xAEE8  node1  X=2 Y=1   決定        cells 2..5 (2 tiles)
    0xAEF8  node2  X=7 Y=1   マップ参照   cells 7..16 (5 tiles)
    0xAF08  node3  X=2 Y=3   取消
    0xAF18  node4  X=7 Y=3   戻る
    0xAF28  terminator (type 0)
    0xAF38  window node: pos(11,10) size(0x12,6), children 0x06093EE8

JP layout: border tile in the window's first/last cell; left side has a
1-cell gap (border 0 | gap 1 | text 2..), right side none (text ..16 |
border 17). The window (cells 11..28 abs = 88..232px) is CENTERED on the
320px screen. Column 2 at X=7 fits JP column 1 (2 tiles + gap); EN
'Confirm' is 4 tiles (cells 2..9), so the column-2 draw landed on its
last 1.5 tiles — the "Decid/map" glue.

The EN fix (playtest-tuned with the user, 2026-06-10):

    column-2 X   7 -> 10   View Map/Return start 16px left of the first
                           fix attempt (X=11); 'Confirm' ends at cell 9
                           with its trailing blank half-tile (7 chars in
                           4 tiles), so the visual gap matches JP's ~8px
    window posX 11 -> 10   \  +1 cell on EACH side: the box stays
    window width 18 -> 20  /  screen-centered (80..240px, center 160)
                           and the margins become symmetric:
                           border 0 | gap 1 | text 2..17 | gap 18 | border 19

Locked against future text growth by
tests/test_prog4_field_box_geometry.py (real-encoder measurement: col-1
texts must not overlap column 2, col-2 texts must clear the border).

RE artifacts: archive/docs/20260610_t11_field_box_re.md (pipeline, dump
evidence, instrumented-Ymir log analysis).
"""

# Cell coordinates (8px half-width units, relative to the box window).
COL1_X = 2        # JP and EN column 1 (unchanged)
COL2_X_JP = 0x07  # JP column 2
COL2_X_EN = 0x0A  # EN column 2: Confirm's glyphs end cell 8 (+blank 9)
WIDTH_JP = 0x12   # window width in cells; border tiles = first/last cell
WIDTH_EN = 0x14   # View Map ends 17, gap 18, border 19 (symmetric)
POSX_JP = 0x0B    # window left edge (abs cells); JP box = 88..232px
POSX_EN = 0x0A    # -1 cell to keep the wider box screen-centered

# File offsets of the four text nodes in LANG/PROG_4.BIN.
NODE_OFFSETS = [0x0AEE8, 0x0AEF8, 0x0AF08, 0x0AF18]

# The window node sits after the terminator; posX at +4, width at +8.
WINDOW_NODE_OFFSET = 0x0AF38
_POSX_OFFSET = WINDOW_NODE_OFFSET + 4
_WIDTH_OFFSET = WINDOW_NODE_OFFSET + 8

# X byte = node offset + 4. Column-2 nodes are #2 (View Map) and #4 (Return).
_COL2_X_OFFSETS = [NODE_OFFSETS[1] + 4, NODE_OFFSETS[3] + 4]

# (file offset, replacement bytes) — same shape as byte_overlays.BYTE_OVERLAYS
# so build.py applies it through the same loop.
PROG4_FIELD_BOX_GEOMETRY = {
    "LANG/PROG_4.BIN":
        [(off, bytes([COL2_X_EN])) for off in _COL2_X_OFFSETS]
        + [(_POSX_OFFSET, bytes([POSX_EN])),
           (_WIDTH_OFFSET, bytes([WIDTH_EN]))],
}

# JP baseline bytes at the same offsets, for the truth-lock test.
JP_BASELINE = {off: COL2_X_JP for off in _COL2_X_OFFSETS}
JP_BASELINE[_POSX_OFFSET] = POSX_JP
JP_BASELINE[_WIDTH_OFFSET] = WIDTH_JP
