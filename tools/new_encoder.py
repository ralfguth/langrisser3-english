"""New encoder for the rebuilt FONT.BIN layout — Part 4
(archive/docs/20260625_new_font_from_scratch_plan.md).

It targets the data-driven `new_font.BIGRAM_LAYOUT` (relocated bigrams) while the
singles stay at their preserved positions (`font_tools.CHAR_TILE_MAP`). It reuses
the proven control-code / token / right-blank core, so spacing and structural
parity are byte-identical to the production encoder — ONLY the bigram tile
numbers differ. With complete 2-by-2 coverage the proven pairing IS strict
2-by-2 (the no-fallback guard pins it).
"""
from __future__ import annotations

import font_tools as ft
import new_font as nf
from d00_tools import encode_text_to_entry

# Singles preserved at position; bigrams data-driven / relocated.
NEW_CHAR_MAP = ft.CHAR_TILE_MAP
NEW_BIGRAM_MAP = nf.BIGRAM_LAYOUT


def encode(text: str) -> bytes:
    """Encode one entry's text to raw bytes for the new font layout, with the
    rigorous trailing rule (trailing composable char -> (c, space) half-width)."""
    return encode_text_to_entry(text, NEW_CHAR_MAP, NEW_BIGRAM_MAP,
                                trailing_bigram=True)


def old_to_new_bigram_remap() -> dict:
    """old bigram tile index -> new bigram tile index (for equivalence checks).
    Singles + control codes keep their value (not in this map)."""
    return {
        ft.BIGRAM_TILE_MAP[p]: nf.BIGRAM_LAYOUT[p]
        for p in nf.BIGRAM_LAYOUT
        if p in ft.BIGRAM_TILE_MAP
    }


def relocated_fntsys_bigram_map() -> dict:
    """The fntsys/syswin bigram map relocated to the new font positions, with the
    complete dialogue layout filling every gap.

    The OLD fntsys map is INCOMPLETE for the trailing (c, space) tiles — a
    word-final uppercase (e.g. 'OPTIONS' -> S) had no half-width tile and, under
    the rigorous trailing rule, fell to the wide zenkaku single ('OPTION Ｓ').
    Union with new_font.BIGRAM_LAYOUT (complete 2-by-2 coverage) so the trailing
    rule always finds a half-width tile. The relocated fntsys-specific pairs
    (apostrophe-UC possessives, leading-space templates) WIN on overlap, so their
    established renders are untouched; deliberate full-width labels (the button
    glyphs ＸＹＺ…, headers ＳＣＥＮＡＲＩＯ) use full-width source and are unaffected."""
    remap = old_to_new_bigram_remap()
    relocated = {pair: remap.get(t, t) for pair, t in ft.FNTSYS_BIGRAM_TILE_MAP.items()}
    return {**nf.BIGRAM_LAYOUT, **relocated}
