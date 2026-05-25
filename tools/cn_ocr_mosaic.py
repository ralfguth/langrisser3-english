#!/usr/bin/env python3
"""
cn_ocr_mosaic.py — render a labelled mosaic of every unique tile used by
the empty subtitle entries of scen123 (or another scenario), denoised
and at high scale, so a vision model can OCR them.

Each cell shows: tile code, the denoised glyph, and the matcher's top-3
candidate hints (from data/cn/tile_char_map.json).
"""
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
TILE_MAP = PROJ / "data" / "cn" / "tile_char_map.json"
OUT = PROJ / "build"


def load_cjk_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", size, index=2)


def render_mosaic(font_data, tile_map, tile_ids, scale=14, cols=8):
    rows = (len(tile_ids) + cols - 1) // cols
    cell_w = TILE_W * scale + 16
    cell_h = TILE_H * scale + 60
    gap = 6
    iw = cols * (cell_w + gap) + gap
    ih = rows * (cell_h + gap) + gap
    img = Image.new("RGB", (iw, ih), (50, 50, 60))
    draw = ImageDraw.Draw(img)
    label_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 14)
    cjk_font = load_cjk_font(20)

    for i, tid in enumerate(tile_ids):
        col = i % cols
        row = i // cols
        x0 = col * (cell_w + gap) + gap
        y0 = row * (cell_h + gap) + gap

        draw.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], fill=(20, 20, 30))
        draw.text((x0 + 6, y0 + 4), f"#{tid}", fill=(220, 220, 100),
                  font=label_font)

        px = denoise(tile_pixels(font_data, tid), min_size=3)
        glyph_x0 = x0 + 8
        glyph_y0 = y0 + 24
        for y in range(TILE_H):
            for x in range(TILE_W):
                if px[y][x]:
                    for sy in range(scale):
                        for sx in range(scale):
                            img.putpixel((glyph_x0 + x * scale + sx,
                                          glyph_y0 + y * scale + sy),
                                         (255, 255, 255))

        # Top-3 hints from matcher
        entry = tile_map.get(str(tid))
        if entry:
            hint = f"~{entry['char']} {entry['alt'][0] if entry['alt'] else '_'} " \
                   f"{entry['alt'][1] if len(entry['alt'])>1 else '_'}"
            draw.text((x0 + 6, y0 + 24 + TILE_H * scale + 4),
                      hint, fill=(180, 200, 255), font=cjk_font)
    return img


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scen", type=int, default=123, nargs="?")
    p.add_argument("--entries", type=str, default="29,30,31,32,51,55,56",
                   help="comma-separated entry indices (default: scen123 empty slots)")
    p.add_argument("--scale", type=int, default=14)
    p.add_argument("--cols", type=int, default=8)
    p.add_argument("--per-page", type=int, default=64)
    args = p.parse_args()

    pairs_path = PAIRS_CN / f"scen{args.scen:03d}.json"
    pairs = json.loads(pairs_path.read_text())
    targets = {int(s) for s in args.entries.split(",")} if args.entries else None

    tile_ids: list[int] = []
    for ent in pairs["entries"]:
        if targets is None or ent["index"] in targets:
            tile_ids.extend(ent["cn_tile_codes"])
    unique_ids = sorted(set(tile_ids))
    print(f"scen{args.scen:03d}: {len(tile_ids)} tile uses; "
          f"{len(unique_ids)} unique → mosaic")

    font_data = load_font()
    tile_map_data = json.loads(TILE_MAP.read_text())
    tile_map = tile_map_data["tiles"]

    OUT.mkdir(exist_ok=True)
    for page_idx in range(0, len(unique_ids), args.per_page):
        page = unique_ids[page_idx:page_idx + args.per_page]
        img = render_mosaic(font_data, tile_map, page, args.scale, args.cols)
        out = OUT / f"cn_ocr_scen{args.scen:03d}_p{page_idx // args.per_page + 1}.png"
        img.save(out)
        print(f"  page {page_idx // args.per_page + 1}: {len(page)} tiles → {out.name}")

    # Save the full unique-tile list for reference
    list_path = OUT / f"cn_ocr_scen{args.scen:03d}_tiles.json"
    list_path.write_text(json.dumps(unique_ids))
    print(f"  wrote tile list → {list_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
