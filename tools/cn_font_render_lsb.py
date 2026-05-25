#!/usr/bin/env python3
"""Same as cn_font_render but LSB-first within each byte.

Test if the CN font is encoded LSB-left (bit 0 = leftmost pixel)
instead of MSB-left.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJ = Path(__file__).resolve().parent.parent
FONT = PROJ / "data" / "cn" / "font_cn.bin"
OUT = PROJ / "build"

TILE_W = 16
TILE_H = 16


def tile_pixels_lsb(data, idx):
    off = idx * 32
    rows = []
    for r in range(TILE_H):
        b1 = data[off + r * 2]
        b2 = data[off + r * 2 + 1]
        # Within each byte: bit 0 = leftmost
        row = []
        for x in range(8):
            row.append(1 if b1 & (1 << x) else 0)
        for x in range(8):
            row.append(1 if b2 & (1 << x) else 0)
        rows.append(row)
    return rows


def render_mosaic(data, start, end, cols=8, scale=8):
    n = end - start
    rows = (n + cols - 1) // cols
    margin = 14
    gap = 2
    tw = TILE_W * scale
    th = TILE_H * scale
    iw = cols * (tw + gap) + gap
    ih = rows * (th + margin + gap) + gap
    img = Image.new("RGB", (iw, ih), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    for i in range(n):
        t = start + i
        col = i % cols
        row = i // cols
        x0 = col * (tw + gap) + gap
        y0 = row * (th + margin + gap) + margin
        draw.text((x0, y0 - 12), str(t), fill=(180, 180, 220))
        px = tile_pixels_lsb(data, t)
        for y in range(TILE_H):
            for x in range(TILE_W):
                if px[y][x]:
                    for sy in range(scale):
                        for sx in range(scale):
                            img.putpixel((x0 + x * scale + sx, y0 + y * scale + sy),
                                         (255, 255, 255))
    return img


if __name__ == "__main__":
    data = FONT.read_bytes()
    OUT.mkdir(exist_ok=True)
    if len(sys.argv) >= 3:
        s, e = int(sys.argv[1]), int(sys.argv[2])
    else:
        s, e = 640, 672
    img = render_mosaic(data, s, e)
    out = OUT / f"lsb_{s}_{e}.png"
    img.save(out)
    print(f"Wrote {out}")
