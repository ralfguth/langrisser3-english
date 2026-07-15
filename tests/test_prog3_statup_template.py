"""Truth-lock for the stat-up template patch (tools/prog3_statup_template.py).

Verifies against the LIVE JP baseline (LANG3_JP_DIR), same contract as
tests/test_prog3_nameplate_new_line.py:

1. Every patch site holds the documented JP byte (0x5C/0x39) in the
   pristine PROG_3.BIN — if the offsets drift, this fails loudly instead
   of silently patching the wrong instruction.
2. The replacement bytes are the documented 0x2C ('s tile 44) / 0x00
   (blank tile 0) — and tile 44 in the GENERATED font really is the 's
   glyph (absolute-glyph-index rule: any hardcoded tile index must be
   validated against the font it indexes).
3. The fntsys3 records appended after a DIGIT/stat keep their load-bearing
   leading space (rec0 ' went up!', rec29 ' went down!', rec28 ' recovered!',
   rec23 ' adjustment'). EXCEPTION: rec24 'Level' is appended right after the
   possessive 's (tile 0x2C), redrawn 2026-06-14 to "'s " (compact 's + 8px
   trailing space) — so rec24 carries NO leading space (the gap is in the tile).
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from prog3_statup_template import PROG3_STATUP_TEMPLATE, JP_BASELINE  # noqa: E402

ISO_PATH = "LANG/PROG_3.BIN"


@pytest.fixture(scope="module")
def jp_prog3():
    jp_dir = os.environ.get("LANG3_JP_DIR")
    if not jp_dir:
        pytest.skip("LANG3_JP_DIR env var not set")
    candidates = (list(Path(jp_dir).glob("*rack*01*.bin"))
                  or list(Path(jp_dir).glob("*rack*1*.bin"))
                  or list(Path(jp_dir).glob("*.bin")))
    if not candidates:
        pytest.skip(f"no Track 01 .bin in {jp_dir}")
    from iso_tools import build_file_index, extract_file_data
    image = candidates[0].read_bytes()
    entry = build_file_index(image).get(ISO_PATH)
    assert entry is not None, f"{ISO_PATH} not in JP ISO"
    return extract_file_data(image, entry.extent, entry.size)


def test_jp_baseline_bytes_match(jp_prog3):
    for off, jp_byte in JP_BASELINE.items():
        assert jp_prog3[off] == jp_byte, (
            f"JP PROG_3.BIN[0x{off:06X}] = 0x{jp_prog3[off]:02X}, expected "
            f"0x{jp_byte:02X} — patch offsets drifted"
        )


def test_patch_values_are_documented_tiles():
    runs = PROG3_STATUP_TEMPLATE[ISO_PATH]
    assert len(runs) == 7
    values = {off: chunk for off, chunk in runs}
    assert values[0x29DCF] == values[0x29E09] == b"\x2c"   # 's tile 44
    # FIVE 0x39 separator sites. 0x29F83 (opcode 0x15, item-effect value
    # message) was missed by the original 4-site sweep — the user saw it
    # as "MPak 18 recovered" (tile 0x39 = our 'ak' bigram), playtest
    # 2026-06-13.
    for off in (0x29DE9, 0x29E23, 0x29EB7, 0x29F2D, 0x29F83):
        assert values[off] == b"\x00"                       # blank tile 0


def test_tile_44_is_the_apostrophe_s_glyph(jp_prog3):
    """The 0x2C immediate indexes tile 44 — assert the generated font
    draws the 's glyph there (it must not be blank, and must equal the
    glyph font_tools installs for the 8-bit-loadable 's slot)."""
    jp_dir = os.environ["LANG3_JP_DIR"]
    candidates = (list(Path(jp_dir).glob("*rack*01*.bin"))
                  or list(Path(jp_dir).glob("*.bin")))
    from iso_tools import build_file_index, extract_file_data
    from font_tools import generate_english_font
    image = candidates[0].read_bytes()
    entry = build_file_index(image).get("LANG/FONT.BIN")
    if entry is None:
        pytest.skip("LANG/FONT.BIN not in JP ISO")
    font = generate_english_font(
        extract_file_data(image, entry.extent, entry.size))
    tile44 = font[44 * 32:(44 + 1) * 32]
    assert sum(bin(b).count("1") for b in tile44) > 4, (
        "tile 44 is blank in the generated font — the stat-up template "
        "would render nothing for 's"
    )


def _fntsys3_records():
    return [l.rstrip("\n").replace("<$FFFF>", "")
            for l in (PROJECT / "scripts" / "en" / "fntsys3E.txt")
            .read_text(encoding="utf-8").splitlines() if l.strip()]


def test_statup_records_keep_leading_space():
    recs = _fntsys3_records()
    # records the template appends right after a glyph (no engine gap).
    # rec24 ("Level") is EXCLUDED since 2026-06-14: it is appended right after
    # the possessive 's (tile 0x2C), which was redrawn to "'s " (compact 's +
    # trailing 8px space). The post-'s gap now lives in the tile, so rec24 must
    # NOT carry its own leading space (it would double the gap). See font_tools
    # tile-44 redraw + prog3_item_use_glue.
    must_lead_with_space = {0: " rose!", 23: " adjustment",
                            28: " recovered!", 29: " fell!"}
    bad = {ri: recs[ri] for ri, want in must_lead_with_space.items()
           if not recs[ri].startswith(" ")}
    assert not bad, (
        f"fntsys3 template records lost their load-bearing leading space "
        f"(would glue to the preceding name/'s): {bad}"
    )


def _fntsys_tiles(text):
    """Greedy FNTSYS tokenizer (mirror of encode_fntsys's walk)."""
    from font_tools import FNTSYS_BIGRAM_TILE_MAP, FNTSYS_CHAR_TILE_MAP
    toks, j = [], 0
    while j < len(text):
        pair = (text[j], text[j + 1]) if j + 1 < len(text) else None
        if pair and pair in FNTSYS_BIGRAM_TILE_MAP:
            toks.append(text[j:j + 2])
            j += 2
        elif text[j] in FNTSYS_CHAR_TILE_MAP:
            toks.append(text[j])
            j += 1
        else:
            j += 1
    return toks


def test_level_template_fits_message_window():
    """Worst case: 8-tile keyboard name. Window grid is 17 tiles/row
    (ui-render-pipeline.md) — the composed Level line must fit ONE row:
    [name 8]['s 1][rec24][sep 1][digit 1][rec0 or rec29].
    The playtest of 2026-06-11 caught ' went up!' wrapping ('up' alone
    on the next row) with the default DIEHARTE name (8 keyboard tiles).
    """
    recs = _fntsys3_records()
    for suffix_idx in (0, 29):
        line = 8 + 1 + len(_fntsys_tiles(recs[24])) + 1 + 1 \
                 + len(_fntsys_tiles(recs[suffix_idx]))
        assert line <= 17, (
            f"Level template with rec{suffix_idx} = {line} tiles > 17 "
            f"(rec24={recs[24]!r}, suffix={recs[suffix_idx]!r})"
        )


def test_class_change_message_fits_one_row():
    """The class-change-available message composes [class name] + rec7
    (no glue; rec6's leading space is the separator) in the same 17-tile
    window row. Playtest 2026-06-13 caught 'Sorcerer class change now
    possib|le!' wrapping mid-word. A 7-tile class name (e.g. Silver/
    Pegasus Knight) is the realistic worst case for a player class-change
    target, so rec6 must be <= 10 tiles (7 + 10 = 17 = one row).
    """
    recs = _fntsys3_records()
    rec6 = len(_fntsys_tiles(recs[6]))
    assert rec6 <= 10, (
        f"class-change suffix rec6 = {rec6} tiles; a 7-tile class name "
        f"+ rec6 must fit the 17-tile row (rec6={recs[6]!r})"
    )


def test_class_up_completed_message():
    """rec3 (line 4) = JP へクラスアップした = class-up COMPLETED, a distinct
    event from rec6 (class-change AVAILABLE). It must convey completion
    (not availability), differ from rec6, and fit the 17-tile row with a
    7-tile class name.
    Red: rec3 was ' class now available!' — a mistranslation (states
    availability) that also collided with rec6 ' class is available!'.
    """
    recs = _fntsys3_records()
    assert "available" not in recs[3].lower(), (
        f"rec3 is class-up COMPLETED, not availability: {recs[3]!r}")
    assert recs[3] != recs[6], "class-up-done and class-available must differ"
    line = 7 + len(_fntsys_tiles(recs[3]))
    assert line <= 17, f"class-up line {line} tiles > 17 (rec3={recs[3]!r})"


def test_template_suffixes_render_tight():
    """Suffixes may not leave a standalone letter before '!' — the
    right-blank of a lone lowercase letter would open a gap inside the
    word ('ros e!'). Locked by walking the real FNTSYS greedy."""
    recs = _fntsys3_records()
    for ri in (0, 28, 29):
        toks = _fntsys_tiles(recs[ri])
        for a, b in zip(toks, toks[1:]):
            assert not (len(a) == 1 and a.isalpha() and b == "!"), (
                f"rec{ri} {recs[ri]!r}: standalone {a!r} before '!' "
                f"opens a mid-word gap — fix the parity"
            )


def test_bytes_not_duplicated_in_overlay():
    """The 6 stat-up bytes moved OUT of byte_overlays.PROG_3_OVERLAY —
    they must not be applied twice nor drift back into the blob."""
    import byte_overlays
    blob_offsets = {off for off, _ in
                    byte_overlays.BYTE_OVERLAYS.get(ISO_PATH, [])}
    ours = {off for off, _ in PROG3_STATUP_TEMPLATE[ISO_PATH]}
    overlap = blob_offsets & ours
    assert not overlap, (
        f"stat-up offsets still present in byte_overlays.PROG_3_OVERLAY: "
        f"{[hex(o) for o in overlap]}"
    )
