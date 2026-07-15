"""Data-driven FONT.BIN layout/generator — now PRODUCTION (Part 6 swap, 2026-06-26).

The from-scratch rebuild's logic was promoted into font_tools (the owner of the
half-glyph alphabet, the char map and the legacy preserved-tile oracle), so the
data-driven packed layout IS the production font: font_tools.BIGRAM_TILE_MAP ==
this module's BIGRAM_LAYOUT, and font_tools.generate_english_font composes the
FRESH region. This module remains a thin re-export for the build and the Part 1-3
guards that import `new_font`. See archive/docs/20260625_new_font_from_scratch_plan.md.
"""
from __future__ import annotations

import font_tools as ft

TILE = 32
BLANK = bytes(TILE)
NEW_FONT_TILES = ft.NEW_FONT_TILES
FRESH_START = ft._FRESH_LO     # first data-driven tile (after the low band)
FRESH_END = ft._FRESH_HI       # last (before the menu/UI band at 1500)

# Region sets (engine-fixed / kept-special / preserved singles / dropped).
FIXED_TILES = ft.FIXED_TILES
KEPT_SPECIAL_TILES = ft.KEPT_SPECIAL_TILES
CHAR_SINGLE_TILES = ft.CHAR_SINGLE_TILES
PRESERVED_TILES = ft.PRESERVED_TILES
DROPPED_TILES = ft.DROPPED_TILES

# The half-glyph alphabet + the data-driven packed bigram layout (== production).
HALF_GLYPHS = ft.HALF_GLYPHS
BIGRAM_LAYOUT = ft.BIGRAM_TILE_MAP

# Builders (kept callable for the guards; they recompute the same packed result).
build_half_glyphs = ft.build_half_glyphs
compose_bigram = ft.compose_bigram
necessary_bigrams = ft.necessary_bigrams
build_bigram_layout = ft.build_bigram_layout
write_layout_csv = ft.write_layout_csv


def generate_new_font(jp_font: bytes) -> bytes:
    """The production font generator (data-driven layout)."""
    return ft.generate_english_font(jp_font)


if __name__ == "__main__":
    n = write_layout_csv("build/new_font_map.csv")
    print(f"font: {NEW_FONT_TILES} tiles, {n} bigrams -> build/new_font_map.csv")
