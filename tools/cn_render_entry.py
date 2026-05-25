#!/usr/bin/env python3
"""Render the tiles of a single CN entry IN ORDER, denoised, high scale.
Reads text linearly. Used for OCR by vision."""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
from cn_font_render import TILE_H, TILE_W, load_font, tile_pixels
from cn_denoise import denoise

PAIRS_CN = PROJ / "data" / "translation_pairs_cn"
OUT = PROJ / "build"


def render_sequence(font_data, tile_ids, scale=12, cols=8):
    rows = (len(tile_ids) + cols - 1) // cols
    cell_w = TILE_W * scale
    cell_h = TILE_H * scale + 18
    gap = 4
    iw = cols * (cell_w + gap) + gap
    ih = rows * (cell_h + gap) + gap
    img = Image.new("RGB", (iw, ih), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    label_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 12)
    for i, tid in enumerate(tile_ids):
        col = i % cols
        row = i // cols
        x0 = col * (cell_w + gap) + gap
        y0 = row * (cell_h + gap) + gap
        # draw position label (1-indexed)
        draw.text((x0 + 2, y0), f"{i+1}:{tid}", fill=(150, 200, 255), font=label_font)
        gy0 = y0 + 16
        px = denoise(tile_pixels(font_data, tid), min_size=3)
        for y in range(TILE_H):
            for x in range(TILE_W):
                if px[y][x]:
                    for sy in range(scale):
                        for sx in range(scale):
                            img.putpixel((x0 + x*scale + sx, gy0 + y*scale + sy),
                                         (255, 255, 255))
    return img


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("scen", type=int)
    p.add_argument("entry", type=int)
    p.add_argument("--scale", type=int, default=12)
    p.add_argument("--cols", type=int, default=8)
    args = p.parse_args()

    pairs = json.loads((PAIRS_CN / f"scen{args.scen:03d}.json").read_text())
    target = next(e for e in pairs["entries"] if e["index"] == args.entry)
    tile_ids = target["cn_tile_codes"]
    print(f"scen{args.scen:03d} entry {args.entry}: {len(tile_ids)} tiles")

    OUT.mkdir(exist_ok=True)
    img = render_sequence(load_font(), tile_ids, args.scale, args.cols)
    out = OUT / f"cn_entry_{args.scen:03d}_{args.entry:03d}.png"
    img.save(out)
    print(f"Wrote {out} ({img.size[0]}x{img.size[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
