#!/usr/bin/env python3
"""font_jbm_generate.py — generate Eagle III pixel data that will replace
the inline glyph dicts in font_tools.py.

Outputs Python dict literals to stdout. Pipe to a file, then hand-paste
into font_tools.py (replaces _LETTER_GLYPHS, _UC_STANDALONE_TILES,
_DIGIT_TILES, _PUNCT_GLYPHS, _EXTRA_PUNCT_GLYPHS, _APOSTROPHE_GLYPH,
_COMMA_GLYPH_BIGRAM). Asterisk `*` is intentionally NOT emitted —
preserved as a hand-drawn override (decision: 2026-05-04).

Tile-code mapping in CHAR_TILE_MAP / BIGRAM_TILE_MAP is NOT changed.
Bigrams regenerate automatically from the new half-glyphs at build time.

Source font: Mx437 CL Eagle III 8x16 (Mx = mixed outline+bitmap, the
embedded bitmap pulls at SIZE=16 with FT_LOAD_TARGET_MONO via PIL mode '1').
Pack: VileR Oldschool PC Fonts v2.2 (CC-BY-SA-4.0). See data/fonts/SOURCES.md.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
JBM = REPO_ROOT / "data/fonts/Mx437_CL_EagleIII_8x16.ttf"
SIZE = 16


# Single baseline row for ALL chars (LC, UC, digits, descenders).
# Empirical baseline lands at row (BASELINE_ROW - 1) due to PIL's
# ascent metric for the Mx437 family at size 16. With BASELINE_ROW = 13,
# baseline lands at row 12 — leaving 3 rows (13-14-15) of descender
# space below for g, p, q, y, j.
BASELINE_ROW = 13


def _render(font_obj, ch: str, cell_w: int) -> bytes:
    """Native 1-bit monochrome render — no anti-aliasing, no threshold.

    Uses PIL Image mode '1' which routes through FreeType's
    FT_LOAD_TARGET_MONO. Two-pass centering: first render in an
    oversized buffer to discover the actual ink footprint (which
    includes serifs/hooks that PIL's textbbox can miss for narrow
    chars like 'i'/'l'/'j'), then re-render centered on the real
    footprint.
    """
    ascent, _ = font_obj.getmetrics()

    # Pass 1: render in a wide buffer to find the actual ink extent.
    pad = 16
    big = Image.new("1", (cell_w + pad * 2, 16), 0)
    bd = ImageDraw.Draw(big)
    bbox = bd.textbbox((0, 0), ch, font=font_obj)
    bd.text((pad - bbox[0], BASELINE_ROW - ascent), ch, fill=1, font=font_obj)
    bp = big.load()

    # Find leftmost / rightmost lit columns.
    left, right = None, None
    for c in range(big.width):
        for r in range(16):
            if bp[c, r]:
                if left is None or c < left:
                    left = c
                if right is None or c > right:
                    right = c
                break
    if left is None:  # blank glyph (space, etc.)
        return bytes(16) if cell_w == 8 else bytes(32)

    visible_w = right - left + 1
    target_left = (cell_w - visible_w) // 2

    img = Image.new("1", (cell_w, 16), 0)
    img_px = img.load()
    for r in range(16):
        for c in range(cell_w):
            src_c = c - target_left + left
            if 0 <= src_c < big.width and bp[src_c, r]:
                img_px[c, r] = 1
    px = img_px

    if cell_w == 8:
        out = bytearray(16)
        for r in range(16):
            b = 0
            for c in range(8):
                if px[c, r]:
                    b |= 1 << (7 - c)
            out[r] = b
        return bytes(out)
    out = bytearray(32)
    for r in range(16):
        for half in range(2):
            b = 0
            for c in range(8):
                if px[half * 8 + c, r]:
                    b |= 1 << (7 - c)
            out[r * 2 + half] = b
    return bytes(out)


def render_8w(font_obj, ch: str) -> bytes:
    """8 wide × 16 tall half-glyph, baseline-aligned at BASELINE_ROW."""
    return _render(font_obj, ch, 8)


def render_16w(font_obj, ch: str) -> bytes:
    """16 wide × 16 tall full tile, baseline-aligned at BASELINE_ROW."""
    return _render(font_obj, ch, 16)


def hexlit(b: bytes) -> str:
    return "bytes.fromhex('" + b.hex() + "')"


def emit_dict(name: str, items: list[tuple[str, bytes]]):
    print(f"_{name} = {{")
    for ch, data in items:
        ch_repr = repr(ch)
        print(f"    {ch_repr}: {hexlit(data)},")
    print("}")
    print()


def main():
    if not JBM.exists():
        raise SystemExit(f"font not found: {JBM}")
    f = ImageFont.truetype(str(JBM), SIZE)

    lc = "abcdefghijklmnopqrstuvwxyz"
    uc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = "0123456789"
    punct = ":;,.?!"
    # Asterisk '*' deliberately omitted — preserved hand-drawn (user decision 2026-05-04).
    extra_punct = "-+()/%[]'&"

    letter_items = [(ch, render_8w(f, ch)) for ch in lc + uc]
    emit_dict("LETTER_GLYPHS", letter_items)

    uc_items = [(ch, render_16w(f, ch)) for ch in uc]
    emit_dict("UC_STANDALONE_TILES", uc_items)

    digit_items = [(ch, render_16w(f, ch)) for ch in digits]
    emit_dict("DIGIT_TILES", digit_items)

    # 8w half-glyphs for digits — needed by CWX-range bigram overrides
    # like (' ', '2'), ('+', '8'), ('1', '5') in tiles 1537-1568.
    digit_half_items = [(ch, render_8w(f, ch)) for ch in digits]
    emit_dict("DIGIT_HALF_GLYPHS", digit_half_items)

    punct_items = [(ch, render_8w(f, ch)) for ch in punct]
    emit_dict("PUNCT_GLYPHS", punct_items)

    extra_items = [(ch, render_8w(f, ch)) for ch in extra_punct]
    emit_dict("EXTRA_PUNCT_GLYPHS", extra_items)

    # Lowercase umlauts (a/o/u-diaeresis) — appear in CWX-range bigrams
    # like 'Jä', 'öl', 'är' (tiles 1533-1536, 1611-1614).
    umlaut_items = [(ch, render_8w(f, ch)) for ch in 'äöü']
    emit_dict("UMLAUT_HALF_GLYPHS", umlaut_items)

    print(f"_APOSTROPHE_GLYPH = {hexlit(render_8w(f, chr(39)))}")
    print()
    print(f"_COMMA_GLYPH_BIGRAM = {hexlit(render_8w(f, ','))}")


if __name__ == "__main__":
    main()
