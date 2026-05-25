#!/usr/bin/env python3
"""font_preview.py — non-destructive A/B preview of the current font vs.
a TTF candidate (Mx437 CL Eagle III by default), rendered into a real
balloon-sized canvas using the existing CHAR_TILE_MAP / BIGRAM_TILE_MAP.

Pipeline (preview only — does NOT modify font_tools.py):
  1. Rasterize the candidate TTF at 8×16 / 16×16 cells (FreeType MONO).
  2. Replace ONLY the half-glyphs that are mapped today (no new tile_codes,
     no reorder).
  3. Generate bigrams by interleaving (same as build pipeline).
  4. Compose a sample balloon (16 tiles × 5 rows = 256×80 px) using the
     current encoder so wrap/ordering matches the real game.
  5. Emit build/font_preview.png with current vs candidate stacked.

Usage:
    python3 tools/font_preview.py
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from font_tools import (
    CHAR_TILE_MAP, BIGRAM_TILE_MAP,
    _LETTER_GLYPHS, _DIGIT_TILES, _PUNCT_GLYPHS, _EXTRA_PUNCT_GLYPHS,
    _UC_STANDALONE_TILES, _APOSTROPHE_GLYPH, _BLANK_GLYPH, _interleave,
)
from d00_tools import encode_text_to_entry
from font_jbm_generate import render_8w as render_glyph_8w
from font_jbm_generate import render_16w as render_glyph_16w

CANDIDATES = [
    ("production (current font_tools.py inline)", None),
    ("Mx437 CL Eagle III 8x16 (candidate)",
     PROJ / "data/fonts/Mx437_CL_EagleIII_8x16.ttf"),
]

SAMPLE_TEXT = (
    " Sir Dieharte. The enemy has come into sight."
    "<$FFFD>What are your orders, my lord?<$FFFE>"
)

TILE_W = TILE_H = 16
BALLOON_TILES_W = 16
BALLOON_TILES_H = 5
SCALE = 3


def build_candidate_font(font_obj) -> dict:
    """Return a dict mapping tile_code → 32-byte tile data, generated from
    the candidate TTF using the SAME tile_codes that the encoder knows.
    """
    half_glyphs = {" ": _BLANK_GLYPH, "'": render_glyph_8w(font_obj, "'")}
    for ch in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
        half_glyphs[ch] = render_glyph_8w(font_obj, ch)
    for ch in "0123456789":
        half_glyphs[ch] = render_glyph_8w(font_obj, ch)
    for ch in ":;,.?!-+()/*%[]&":
        half_glyphs[ch] = render_glyph_8w(font_obj, ch)

    out = {}
    for ch, tile_code in CHAR_TILE_MAP.items():
        if ch == " ":
            out[tile_code] = b"\x00" * 32
        elif ch in "abcdefghijklmnopqrstuvwxyz":
            out[tile_code] = _interleave(half_glyphs[ch], _BLANK_GLYPH)
        elif ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" or ch in "0123456789":
            out[tile_code] = render_glyph_16w(font_obj, ch)
        elif ch in half_glyphs:
            out[tile_code] = _interleave(half_glyphs[ch], _BLANK_GLYPH)

    for (lc, rc), tile_code in BIGRAM_TILE_MAP.items():
        l = half_glyphs.get(lc, _BLANK_GLYPH)
        r = half_glyphs.get(rc, _BLANK_GLYPH)
        out[tile_code] = _interleave(l, r)
    return out


def build_current_font() -> dict:
    """Build the same dict using the CURRENT inline pixel data."""
    half_glyphs = {" ": _BLANK_GLYPH, "'": _APOSTROPHE_GLYPH}
    half_glyphs.update(_LETTER_GLYPHS)
    half_glyphs.update(_PUNCT_GLYPHS)
    half_glyphs.update(_EXTRA_PUNCT_GLYPHS)

    out = {}
    for ch, tile_code in CHAR_TILE_MAP.items():
        if ch == " ":
            out[tile_code] = b"\x00" * 32
        elif ch in _UC_STANDALONE_TILES:
            out[tile_code] = _UC_STANDALONE_TILES[ch]
        elif ch in _DIGIT_TILES:
            out[tile_code] = _DIGIT_TILES[ch]
        elif ch in half_glyphs:
            out[tile_code] = _interleave(half_glyphs[ch], _BLANK_GLYPH)

    for (lc, rc), tile_code in BIGRAM_TILE_MAP.items():
        l = half_glyphs.get(lc, _BLANK_GLYPH)
        r = half_glyphs.get(rc, _BLANK_GLYPH)
        out[tile_code] = _interleave(l, r)
    return out


def render_balloon(font_dict: dict, text: str, scale: int = SCALE) -> Image.Image:
    raw = encode_text_to_entry(text, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
    tile_codes = []
    for i in range(0, len(raw), 2):
        c = (raw[i] << 8) | raw[i + 1]
        tile_codes.append(c)

    rows = [[]]
    for c in tile_codes:
        if c in (0xFFFC, 0xFFFD):
            rows.append([])
            continue
        if c == 0xFFFE:
            break
        if c >= 0xFF00:
            continue
        rows[-1].append(c)
        if len(rows[-1]) == BALLOON_TILES_W:
            rows.append([])

    while len(rows) < BALLOON_TILES_H:
        rows.append([])
    rows = rows[:BALLOON_TILES_H]

    img_w = BALLOON_TILES_W * TILE_W * scale
    img_h = BALLOON_TILES_H * TILE_H * scale
    img = Image.new("L", (img_w, img_h), 0)
    for ri, row in enumerate(rows):
        for ci, code in enumerate(row):
            tile = font_dict.get(code)
            if not tile or len(tile) != 32:
                continue
            for r in range(TILE_H):
                b1, b2 = tile[r * 2], tile[r * 2 + 1]
                for x in range(8):
                    if b1 & (0x80 >> x):
                        for sy in range(scale):
                            for sx in range(scale):
                                img.putpixel(
                                    (ci * TILE_W * scale + x * scale + sx,
                                     ri * TILE_H * scale + r * scale + sy), 255)
                    if b2 & (0x80 >> x):
                        for sy in range(scale):
                            for sx in range(scale):
                                img.putpixel(
                                    (ci * TILE_W * scale + (8 + x) * scale + sx,
                                     ri * TILE_H * scale + r * scale + sy), 255)
    return img


def main():
    print(f"sample text: {SAMPLE_TEXT[:80]!r}")
    panels = []
    label_h = 24
    for label, ttf_path in CANDIDATES:
        if ttf_path is None:
            font_dict = build_current_font()
        else:
            if not ttf_path.exists():
                print(f"  skip {label}: {ttf_path} not found")
                continue
            font_obj = ImageFont.truetype(str(ttf_path), 16)
            font_dict = build_candidate_font(font_obj)
        ballon = render_balloon(font_dict, SAMPLE_TEXT)
        full = Image.new("L", (ballon.width, ballon.height + label_h), 64)
        d = ImageDraw.Draw(full)
        d.text((6, 4), label, fill=255)
        full.paste(ballon, (0, label_h))
        panels.append((label, full))
        print(f"  rendered {label}: {ballon.size}")

    sep_h = 6
    total_h = sum(p.height for _, p in panels) + sep_h * (len(panels) - 1)
    total_w = panels[0][1].width
    out = Image.new("L", (total_w, total_h), 32)
    y = 0
    for _, p in panels:
        out.paste(p, (0, y))
        y += p.height + sep_h

    out_path = PROJ / "build" / "font_preview.png"
    out_path.parent.mkdir(exist_ok=True)
    out.save(out_path)
    print(f"\nwrote {out_path.relative_to(PROJ)}")
    print(f"  open in image viewer to compare {len(panels)} candidates")


if __name__ == "__main__":
    main()
