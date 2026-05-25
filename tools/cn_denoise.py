#!/usr/bin/env python3
"""
cn_denoise.py — try to clean up CN font tile bitmaps by removing
isolated/sparse pixels (treating them as noise) while preserving
connected strokes.

Strategy: flood-fill connected components on the on-pixels;
keep components with >= MIN_SIZE pixels. Render before+after
side-by-side at high scale for visual confirmation.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
from cn_font_render import TILE_H, TILE_W, load_font, tile_pixels


def connected_components(px):
    seen = [[False]*TILE_W for _ in range(TILE_H)]
    comps = []
    for y in range(TILE_H):
        for x in range(TILE_W):
            if px[y][x] and not seen[y][x]:
                stack = [(x, y)]
                comp = []
                while stack:
                    cx, cy = stack.pop()
                    if (0 <= cx < TILE_W and 0 <= cy < TILE_H
                            and px[cy][cx] and not seen[cy][cx]):
                        seen[cy][cx] = True
                        comp.append((cx, cy))
                        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),
                                       (-1,-1),(1,-1),(-1,1),(1,1)]:
                            stack.append((cx+dx, cy+dy))
                comps.append(comp)
    return comps


def denoise(px, min_size=3):
    comps = connected_components(px)
    out = [[0]*TILE_W for _ in range(TILE_H)]
    for comp in comps:
        if len(comp) >= min_size:
            for x, y in comp:
                out[y][x] = 1
    return out


def render_pair(font_data, tile_ids, scale=10, cols=4, min_size=3):
    rows = (len(tile_ids) + cols - 1) // cols
    margin = 14
    gap = 4
    pair_w = TILE_W * scale * 2 + 4   # before + after side-by-side
    pair_h = TILE_H * scale
    iw = cols * (pair_w + gap) + gap
    ih = rows * (pair_h + margin + gap) + gap
    img = Image.new("RGB", (iw, ih), (40, 40, 40))
    draw = ImageDraw.Draw(img)
    for i, tid in enumerate(tile_ids):
        col = i % cols
        row = i // cols
        x0 = col * (pair_w + gap) + gap
        y0 = row * (pair_h + margin + gap) + margin
        draw.text((x0, y0 - 12), str(tid), fill=(180, 180, 220))
        before = tile_pixels(font_data, tid)
        after = denoise(before, min_size=min_size)
        for y in range(TILE_H):
            for x in range(TILE_W):
                if before[y][x]:
                    for sy in range(scale):
                        for sx in range(scale):
                            img.putpixel((x0 + x*scale + sx, y0 + y*scale + sy),
                                         (200, 200, 200))
                if after[y][x]:
                    bx = x0 + TILE_W*scale + 4 + x*scale
                    for sy in range(scale):
                        for sx in range(scale):
                            img.putpixel((bx + sx, y0 + y*scale + sy),
                                         (255, 255, 255))
    return img


if __name__ == "__main__":
    data = load_font()
    if len(sys.argv) >= 2:
        ids = [int(s) for s in sys.argv[1:]]
    else:
        ids = [644, 758, 4, 163, 466, 229, 453, 468]
    img = render_pair(data, ids, scale=12, cols=2, min_size=3)
    out = PROJ / "build" / "cn_denoise_test.png"
    img.save(out)
    print(f"Wrote {out}")
