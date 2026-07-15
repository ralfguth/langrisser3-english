"""test_fntsys_char_map.py — lock the EFFECTIVE encoder↔glyph mapping.

FNT_SYS strings render through the SAME shared custom font as the scenario (D00)
and chapter-recap (PLOT) text, so fntsys MUST encode with the SAME map those
pipelines use: font_tools.CHAR_TILE_MAP. There is no JP font in the build.

Historically fnt_sys_tools._build_fntsys_char_map() layered the JP decoder's
tile_map.json under the EN map and let JP slots WIN for ASCII letters, which
silently pointed a standalone lowercase letter at a JP tile id that the EN font
(generate_english_font) re-paints with a DIFFERENT glyph.

Concrete regression this guards against: JP places 'r' at tile 67, but the EN
font paints tile 67 with the ('a','u') bigram glyph. A word-final 'r' (e.g.
"Commander", "Soldier", "Gladiator") fell back to the standalone-'r' slot 67 and
rendered as "au" on screen ("Commandeau", "Soldieau", "Gladiatoau").

Invariant (the fix): the EN font owns every tile it paints, so the encoder MUST
use the EN tile for every char the EN font defines. In particular each standalone
lowercase letter must resolve to its own (letter, ' ') half-width tile — the very
glyph generate_english_font draws there — never a colliding JP slot.
"""

import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from fnt_sys_tools import _build_fntsys_char_map          # noqa: E402
from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP     # noqa: E402
from d00_tools import encode_text_to_entry                # noqa: E402

import string


def _eff():
    return _build_fntsys_char_map()


def test_standalone_lowercase_is_letter_space_tile():
    """Each a-z standalone resolves to its own (letter, ' ') half-width tile —
    the glyph the EN font actually paints there. Catches r->67(=au)."""
    eff = _eff()
    bad = []
    for c in string.ascii_lowercase:
        want = BIGRAM_TILE_MAP[(c, " ")]   # EN font's standalone-letter glyph
        got = eff.get(c)
        if got != want:
            bad.append((c, got, want))
    assert bad == [], (
        "standalone lowercase letters point at the wrong tile "
        "(JP slot collides with an EN bigram glyph): "
        + ", ".join(f"{c!r}:{got}!=want{want}" for c, got, want in bad)
    )


def test_effective_map_agrees_with_en_font_for_every_en_char():
    """The EN font (generate_english_font) is painted from font_tools maps, so
    the encoder must use the EN tile for EVERY char the EN font defines. JP slots
    may only fill chars the EN font does NOT paint (kanji/kana).

    Per-surface exception (2026-06-11): half-width digit singles on the
    FNT_SYS surface use the (d,' ') half-width tiles 201-210 — also painted
    by the EN font — while dialogue keeps the centered 7-16. The effective
    fnt_sys map must equal FNTSYS_CHAR_TILE_MAP for digits and
    CHAR_TILE_MAP everywhere else."""
    from font_tools import FNTSYS_CHAR_TILE_MAP
    eff = _eff()
    mism = [(ch, eff.get(ch), tid)
            for ch, tid in CHAR_TILE_MAP.items()
            if eff.get(ch) != (FNTSYS_CHAR_TILE_MAP[ch] if ch.isdigit()
                               and ord(ch) < 128 else tid)]
    assert mism == [], (
        "effective encoder map diverges from the EN font for "
        f"{len(mism)} char(s): "
        + ", ".join(f"{ch!r}:{got}!=font{tid}" for ch, got, tid in mism[:20])
    )


def test_word_final_r_encodes_to_r_space_tile():
    """End-to-end: a word ending in a standalone 'r' must emit the (r,' ') tile,
    not the JP 'r' slot. Mirrors the on-screen class names."""
    rspace = BIGRAM_TILE_MAP[("r", " ")]
    for word in ("Commander", "Soldier", "Gladiator", "Fighter"):
        rec = encode_text_to_entry(word, _eff(), bigram_tile_map=BIGRAM_TILE_MAP)
        last_tile = struct.unpack_from(">H", rec, len(rec) - 2)[0]
        assert last_tile == rspace, (
            f"{word!r}: final tile {last_tile} != (r,' ') tile {rspace} "
            f"(would render as the glyph painted at {last_tile})"
        )


def test_no_ascii_letter_collides_with_a_different_bigram_glyph():
    """Defensive: no standalone ASCII letter may resolve to a tile that the EN
    font paints as a *different* bigram pair. This is the general form of the
    r->au bug for the whole alphabet."""
    eff = _eff()
    tile_to_pair = {t: p for p, t in BIGRAM_TILE_MAP.items()}
    bad = []
    for c in string.ascii_letters:
        t = eff.get(c)
        pair = tile_to_pair.get(t)
        # A letter is allowed to land on its own (letter, ' ') tile; anything
        # else that is a bigram tile means a glyph mismatch.
        if pair is not None and pair != (c, " "):
            bad.append((c, t, "".join(pair)))
    assert bad == [], (
        "ASCII letters resolving to a mismatched bigram glyph: "
        + ", ".join(f"{c!r}->{t}(={g})" for c, t, g in bad)
    )
