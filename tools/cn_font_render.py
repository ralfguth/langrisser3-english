#!/usr/bin/env python3
"""
cn_font_render.py — Render CN font tiles to PNG (single tile or mosaic).

Geometry: 16x16 1bpp row-major MSB-left, 32 bytes per tile, ~4506 tiles
(8-byte trailing pad).

Usage:
    python3 tools/cn_font_render.py mosaic START END [--cols 16 --scale 4]
    python3 tools/cn_font_render.py single TILE_INDEX [--scale 8]
    python3 tools/cn_font_render.py tiles INDEX [INDEX ...]   # one png per tile
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJ = Path(__file__).resolve().parent.parent
FONT = PROJ / "data" / "cn" / "font_cn.bin"
OUT = PROJ / "build"

TILE_W = 16
TILE_H = 16
TILE_BYTES = (TILE_W * TILE_H) // 8


def load_font() -> bytes:
    return FONT.read_bytes()


def tile_count(data: bytes) -> int:
    return len(data) // TILE_BYTES


def tile_pixels(data: bytes, idx: int) -> list[list[int]]:
    off = idx * TILE_BYTES
    rows = []
    for r in range(TILE_H):
        v = (data[off + r * 2] << 8) | data[off + r * 2 + 1]
        rows.append([1 if v & (1 << (TILE_W - 1 - bit)) else 0 for bit in range(TILE_W)])
    return rows


def render_tile_image(data: bytes, idx: int, scale: int = 8) -> Image.Image:
    """Single-tile black-on-white image (OCR-ready)."""
    img = Image.new("L", (TILE_W * scale, TILE_H * scale), 255)
    px = tile_pixels(data, idx)
    for y in range(TILE_H):
        for x in range(TILE_W):
            if px[y][x]:
                for sy in range(scale):
                    for sx in range(scale):
                        img.putpixel((x * scale + sx, y * scale + sy), 0)
    return img


def render_mosaic(data: bytes, start: int, end: int, cols: int, scale: int) -> Image.Image:
    n = end - start
    if n <= 0:
        raise ValueError(f"empty range [{start},{end})")
    rows = (n + cols - 1) // cols
    margin = 18
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
        draw.text((x0, y0 - 14), str(t), fill=(180, 180, 220))
        px = tile_pixels(data, t)
        for y in range(TILE_H):
            for x in range(TILE_W):
                if px[y][x]:
                    for sy in range(scale):
                        for sx in range(scale):
                            img.putpixel((x0 + x * scale + sx, y0 + y * scale + sy), (255, 255, 255))
    return img


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    pm = sub.add_parser("mosaic")
    pm.add_argument("start", type=int)
    pm.add_argument("end", type=int)
    pm.add_argument("--cols", type=int, default=16)
    pm.add_argument("--scale", type=int, default=4)
    pm.add_argument("-o", "--output", type=Path, default=None)

    ps = sub.add_parser("single")
    ps.add_argument("idx", type=int)
    ps.add_argument("--scale", type=int, default=8)
    ps.add_argument("-o", "--output", type=Path, default=None)

    pt = sub.add_parser("tiles")
    pt.add_argument("indices", type=int, nargs="+")
    pt.add_argument("--scale", type=int, default=8)
    pt.add_argument("--out-dir", type=Path, default=OUT / "cn_tiles")

    args = parser.parse_args()
    data = load_font()
    OUT.mkdir(exist_ok=True)
    print(f"CN font: {len(data):,} bytes ({tile_count(data)} tiles, {len(data) % TILE_BYTES}b pad)")

    if args.cmd == "mosaic":
        img = render_mosaic(data, args.start, args.end, args.cols, args.scale)
        out = args.output or (OUT / f"cn_font_{args.start}_{args.end}.png")
        img.save(out)
        print(f"Wrote {out}")
    elif args.cmd == "single":
        img = render_tile_image(data, args.idx, args.scale)
        out = args.output or (OUT / f"cn_tile_{args.idx:04d}.png")
        img.save(out)
        print(f"Wrote {out}")
    elif args.cmd == "tiles":
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for i in args.indices:
            out = args.out_dir / f"tile_{i:04d}.png"
            render_tile_image(data, i, args.scale).save(out)
        print(f"Wrote {len(args.indices)} tiles to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
