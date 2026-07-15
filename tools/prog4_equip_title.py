"""tools/prog4_equip_title.py — equip-screen composed title slot repoint.

ONE owned u16 patch over the **JP** `LANG/PROG_4.BIN` (playtest follow-up
to T11, 2026-06-11).

The equip screen's title bar is composed from THREE fntsys1 records drawn
at fixed slots (X cells 2 / 12 / 22 on row 1; slot X values come from an
A0LANG-unpacked UI blob — runtime work area 0x06094408, NOT patchable as
plain file data). The per-frame installer in PROG_4 (`FUN_0608f410`,
install site file 0x647E..0x64AE) resolves each slot's record through a
u16 literal pool of `record_index * 2` values:

    file 0x657E  0x0094 = rec74  装備する 'Equip'   -> slot X=12
    file 0x6580  0x0126 = rec147 指揮官  'Commander' -> slot X=2
    file 0x6582  0x016E = rec183 の選択  ' Menu'     -> slot X=22

JP composes 指揮官/装備する/の選択 with airy gaps sized for those widths.
The EN pieces left holes ("Commander Equip      Menu") and rec74/rec183
are SHARED records (rec74 is also the prep screen's L/R tab label), so
fixing by text alone was impossible without side effects.

The fix: repoint slot X=12 from rec74 to **rec96** — a JP composition
fragment (します) whose consumer was never observed rendering (shipped
EMPTY since T04, see tests/test_fntsys1.py) — and give rec96 the text
'Equipment' (5 tiles = cells 12..21, exact fit). Composed result:

    Commander Equipment Menu
    2......11 12.....21 22..27   (continuous, no holes)

If rec96's unknown JP consumer ever surfaces in a playtest it will now
render 'Equipment'; that screen would have shown a blank before — either
way it needs RE, and this repoint is one u16 to revert.

RE trail: archive/docs/20260610_t11_field_box_re.md (renderer/walker
hooks; the instrumented-Ymir REND/WALK log analysis that pinned the
slots, the installer, and the pool).
"""

# u16 literal pool entries (file offsets) = fntsys1 record index * 2.
SLOT1_OFFSET = 0x657E   # slot X=12 (centre piece)
SLOT2_OFFSET = 0x6580   # slot X=2  (left piece)
SLOT3_OFFSET = 0x6582   # slot X=22 (right piece)

SLOT1_REC_JP = 74       # 装備する 'Equip' (shared with prep L/R tab)
SLOT1_REC_EN = 96       # orphan fragment -> 'Equipment'

PROG4_EQUIP_TITLE = {
    "LANG/PROG_4.BIN": [
        (SLOT1_OFFSET, (SLOT1_REC_EN * 2).to_bytes(2, "big")),
    ],
}

# JP baseline u16s at the pool, for the truth-lock test.
JP_BASELINE_U16 = {
    SLOT1_OFFSET: SLOT1_REC_JP * 2,
    SLOT2_OFFSET: 147 * 2,
    SLOT3_OFFSET: 183 * 2,
}
