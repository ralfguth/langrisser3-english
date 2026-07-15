#!/usr/bin/env python3
"""screenshot_decode.py — read game text out of Ymir screenshots.

Template-matches the project's FONT.BIN tiles (1bpp 16x16) against the
screenshot's bright-text mask and emits the decoded text per row — so
playtest review reads TEXT, not pixels. The decode uses the same font
the engine renders with (verify-in-bytes philosophy; never OCR).

Method (dependency-free: 256-bit int masks + popcount):
  1. Binarize: luminance >= --threshold = glyph foreground.
  2. For every 8px-aligned 16x16 cell with enough ink, score every font
     tile: (matched - missing - stray ink) / tile ink.
  3. Greedy left-to-right per row; accepted tiles map back to text via
     the FNT_SYS reverse maps (bigrams two chars, zenkaku one).

Usage:
  python3 tools/screenshot_decode.py SHOT.png [SHOT2.png ...]
  python3 tools/screenshot_decode.py --dir /path/to/ymir-screenshots
  (font defaults to the current build's FONT.BIN via build.py's naming rule)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
sys.path.insert(0, str(PROJ))

import font_tools as ft  # noqa: E402

TILE = 16
STRIDE = 8           # glyphs land on 8px boundaries (half-tile steps)
MIN_INK = 12         # foreground pixels required to attempt a match
MIN_SCORE = 0.62     # accept threshold: (hits - miss - extra) / tile_ink


def _font_bytes() -> bytes:
    """Current build's FONT.BIN (via build.py naming rule), else generated."""
    import build as _b
    stem = Path(_b._resolve_canonical_cue_name(
        _b.LANGUAGES[_b.DEFAULT_LANG])).stem
    track = PROJ / "build" / stem / "track01.bin"
    if track.exists():
        from iso_tools import build_file_index, extract_file_data
        img = track.read_bytes()
        idx = build_file_index(img)
        e = idx["LANG/FONT.BIN"]
        return extract_file_data(img, e.extent, e.size)
    jp = PROJ / "data" / "jp" / "font_jp.bin"
    return ft.generate_english_font(jp.read_bytes())


def _tile_masks(font: bytes) -> tuple[list[int], list[int]]:
    """Per tile: 256-bit int mask (row-major, MSB-first) + ink count."""
    masks: list[int] = []
    ink: list[int] = []
    for t in range(len(font) // 32):
        m = 0
        for row in range(16):
            w = int.from_bytes(font[t * 32 + row * 2: t * 32 + row * 2 + 2],
                               "big")
            m = (m << 16) | w
        masks.append(m)
        ink.append(m.bit_count())
    return masks, ink


def _reverse_text_map() -> dict[int, str]:
    rev: dict[int, str] = {}
    for (a, b), t in ft.FNTSYS_BIGRAM_TILE_MAP.items():
        rev[t] = a + b
    for ch, t in ft.FNTSYS_CHAR_TILE_MAP.items():
        rev.setdefault(t, ch)
    return rev


def _fg_rows(path: Path, threshold: int,
             scale: int = 1) -> tuple[list[int], int, int]:
    """Image -> per-scanline foreground bitmask ints (MSB = x0).

    scale=2 halves the image first (Ymir doubles the native frame:
    640x448 = 320x224 x2) — NEAREST keeps the pixel-doubling exact."""
    im = Image.open(path).convert("L")
    if scale > 1:
        im = im.resize((im.width // scale, im.height // scale),
                       Image.NEAREST)
    W, H = im.size
    data = im.tobytes()
    rows = []
    for y in range(H):
        bits = 0
        base = y * W
        for x in range(W):
            bits = (bits << 1) | (1 if data[base + x] >= threshold else 0)
        rows.append(bits)
    return rows, W, H


def _cell_mask(rows: list[int], W: int, x: int, y: int) -> int:
    """16x16 cell at (x, y) as a 256-bit int (row-major, MSB-first)."""
    m = 0
    shift = W - x - 16
    for yy in range(y, y + 16):
        m = (m << 16) | ((rows[yy] >> shift) & 0xFFFF)
    return m


def decode_image(path: Path, masks: list[int], ink: list[int],
                 rev: dict[int, str], threshold: int = 180,
                 scale: int | None = None) -> list[str]:
    if scale is None:
        # auto: try native and half (Ymir 2x) — keep the richer decode
        a = decode_image(path, masks, ink, rev, threshold, scale=1)
        b = decode_image(path, masks, ink, rev, threshold, scale=2)
        return a if sum(map(len, a)) >= sum(map(len, b)) else b
    rows, W, H = _fg_rows(path, threshold, scale)
    # candidate tiles: skip blank tiles
    cand = [t for t, k in enumerate(ink) if k >= MIN_INK]
    lines: list[str] = []
    for y0 in range(0, H - TILE + 1, TILE):
        best_row = None
        for phase in (0, 8):
            y = y0 + phase
            if y + TILE > H:
                continue
            out: list[str] = []
            x = 0
            while x <= W - TILE:
                cell = _cell_mask(rows, W, x, y)
                cnt = cell.bit_count()
                if cnt < MIN_INK:
                    if out and out[-1] != " ":
                        out.append(" ")
                    x += STRIDE
                    continue
                best_t, best_s = -1, MIN_SCORE
                for t in cand:
                    m = masks[t]
                    hits = (m & cell).bit_count()
                    if hits * 2 < ink[t]:
                        continue
                    score = (2 * hits - ink[t] - cnt) / ink[t] + 1.0
                    # == (hits - (ink-hits) - (cnt-hits)) / ink, rearranged
                    if score > best_s:
                        best_s, best_t = score, t
                if best_t >= 0:
                    out.append(rev.get(best_t, f"<{best_t}>"))
                    x += TILE
                else:
                    x += STRIDE
            text = "".join(out).strip()
            if text and (best_row is None or len(text) > len(best_row)):
                best_row = text
        if best_row:
            lines.append(best_row)
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("shots", nargs="*", type=Path)
    ap.add_argument("--dir", type=Path, default=None)
    ap.add_argument("--threshold", type=int, default=180)
    args = ap.parse_args()
    shots = list(args.shots)
    if args.dir:
        shots += sorted(args.dir.glob("*.png"))
    if not shots:
        ap.error("no screenshots given")
    masks, ink = _tile_masks(_font_bytes())
    rev = _reverse_text_map()
    for p in shots:
        print(f"== {p.name}")
        for line in decode_image(p, masks, ink, rev, args.threshold):
            print(f"   {line}")


if __name__ == "__main__":
    main()
