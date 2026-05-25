#!/usr/bin/env python3
"""
cn_used_tiles.py — collect all tile codes referenced by a CN D00 scenario,
then render a labelled mosaic so each unique tile can be OCR'd by hand
or by vision model.

Usage:
    python3 tools/cn_used_tiles.py SCEN_INDEX [--scale 5 --cols 12]
        scen index = 1-based scenario number (scen123 → 123)

Output:
    build/cn_used_tiles_scenNNN.json  (sorted unique tile codes)
    build/cn_used_tiles_scenNNN_part_K.png   (one or more mosaics)
"""
import argparse
import json
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
from d00_tools import parse_d00
from cn_font_render import tile_pixels, load_font, TILE_W, TILE_H

CN_D00 = PROJ / "data" / "cn" / "d00_cn.dat"
OUT = PROJ / "build"


def collect_used_tiles(d00_data: bytes, scen_idx: int) -> list[int]:
    secs = parse_d00(d00_data)
    sec = secs[scen_idx - 1]
    used = set()
    for entry in sec.entries:
        i = 0
        while i < len(entry) - 1:
            w = struct.unpack_from(">H", entry, i)[0]
            i += 2
            if w >= 0xF000:
                if w == 0xF600 and i < len(entry) - 1:
                    i += 2
            else:
                used.add(w)
    return sorted(used)


def render_mosaic(font: bytes, tile_ids: list[int],
                  scale: int = 5, cols: int = 12,
                  per_page: int = 96) -> list[Image.Image]:
    """Render labelled mosaics, one image per `per_page` tiles."""
    pages: list[Image.Image] = []
    margin = 22
    gap = 6
    tw = TILE_W * scale
    th = TILE_H * scale

    for page_start in range(0, len(tile_ids), per_page):
        chunk = tile_ids[page_start:page_start + per_page]
        n = len(chunk)
        rows = (n + cols - 1) // cols
        iw = cols * (tw + gap) + gap
        ih = rows * (th + margin + gap) + gap
        img = Image.new("RGB", (iw, ih), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        try:
            font_pil = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except OSError:
            font_pil = ImageFont.load_default()
        for i, t in enumerate(chunk):
            col = i % cols
            row = i // cols
            x0 = col * (tw + gap) + gap
            y0 = row * (th + margin + gap) + margin
            draw.text((x0, y0 - 16), str(t), fill=(60, 60, 180), font=font_pil)
            px = tile_pixels(font, t)
            for y in range(TILE_H):
                for x in range(TILE_W):
                    if px[y][x]:
                        for sy in range(scale):
                            for sx in range(scale):
                                img.putpixel((x0 + x * scale + sx,
                                              y0 + y * scale + sy),
                                             (0, 0, 0))
        pages.append(img)
    return pages


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("scen", type=int)
    p.add_argument("--scale", type=int, default=5)
    p.add_argument("--cols", type=int, default=12)
    p.add_argument("--per-page", type=int, default=96)
    args = p.parse_args()

    d00 = CN_D00.read_bytes()
    font = load_font()

    used = collect_used_tiles(d00, args.scen)
    OUT.mkdir(exist_ok=True)
    json_path = OUT / f"cn_used_tiles_scen{args.scen:03d}.json"
    json_path.write_text(json.dumps(used))
    print(f"scen{args.scen:03d}: {len(used)} unique tile codes "
          f"(min={used[0]}, max={used[-1]}) → {json_path.name}")

    pages = render_mosaic(font, used, args.scale, args.cols, args.per_page)
    for i, img in enumerate(pages):
        out = OUT / f"cn_used_tiles_scen{args.scen:03d}_part_{i+1}.png"
        img.save(out)
        print(f"  page {i+1}/{len(pages)} → {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
