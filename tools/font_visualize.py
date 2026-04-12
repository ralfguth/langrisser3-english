#!/usr/bin/env python3
"""
font_visualize.py - Generate PNG mosaic of font.bin tiles.

Reads lang3a2/font.bin (1691 tiles × 32 bytes, 16×16 1bpp) and renders
a grid of tiles with index labels.

Usage:
    python3 tools/font_visualize.py                    # all tiles
    python3 tools/font_visualize.py 0 64               # tiles 0-63
    python3 tools/font_visualize.py 1500 1620           # tiles 1500-1619
    python3 tools/font_visualize.py --cols 8 --scale 6  # custom grid

Output: build/font_tiles.png
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

PROJ = Path(__file__).resolve().parent.parent
FONT_PATH = PROJ / 'lang3a2' / 'font.bin'
OUTPUT_DIR = PROJ / 'build'


def tile_pixels(data: bytes, idx: int) -> list[list[int]]:
    """Decode a 32-byte tile into 16×16 grid of 0/1."""
    off = idx * 32
    rows = []
    for r in range(16):
        b0 = data[off + r * 2]
        b1 = data[off + r * 2 + 1]
        val = (b0 << 8) | b1
        row = []
        for bit in range(15, -1, -1):
            row.append(1 if val & (1 << bit) else 0)
        rows.append(row)
    return rows


def generate_mosaic(start: int = 0, end: int | None = None,
                    cols: int = 16, scale: int = 4,
                    output: Path | None = None) -> Path:
    """Generate PNG mosaic of tiles [start, end)."""
    data = FONT_PATH.read_bytes()
    total_tiles = len(data) // 32

    if end is None:
        end = total_tiles
    end = min(end, total_tiles)

    n = end - start
    if n <= 0:
        raise ValueError(f"No tiles in range [{start}, {end})")

    row_count = (n + cols - 1) // cols
    margin = 16
    gap = 2
    tile_w = 16 * scale
    tile_h = 16 * scale

    img_w = cols * (tile_w + gap) + gap
    img_h = row_count * (tile_h + margin + gap) + gap

    img = Image.new('RGB', (img_w, img_h), (30, 30, 30))
    draw = ImageDraw.Draw(img)

    for i in range(n):
        t = start + i
        col = i % cols
        row = i // cols
        x0 = col * (tile_w + gap) + gap
        y0 = row * (tile_h + margin + gap) + margin

        draw.text((x0, y0 - 12), str(t), fill=(180, 180, 220))

        px = tile_pixels(data, t)
        for py in range(16):
            for px_i in range(16):
                if px[py][px_i]:
                    for sy in range(scale):
                        for sx in range(scale):
                            img.putpixel((x0 + px_i * scale + sx,
                                          y0 + py * scale + sy),
                                         (255, 255, 255))

    OUTPUT_DIR.mkdir(exist_ok=True)
    if output is None:
        if start == 0 and end == total_tiles:
            output = OUTPUT_DIR / 'font_tiles.png'
        else:
            output = OUTPUT_DIR / f'font_tiles_{start}_{end}.png'

    img.save(output)
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Generate PNG mosaic of font.bin tiles')
    parser.add_argument('start', nargs='?', type=int, default=0,
                        help='First tile index (default: 0)')
    parser.add_argument('end', nargs='?', type=int, default=None,
                        help='Last tile index exclusive (default: all)')
    parser.add_argument('--cols', type=int, default=16,
                        help='Tiles per row (default: 16)')
    parser.add_argument('--scale', type=int, default=4,
                        help='Pixel scale factor (default: 4)')
    parser.add_argument('-o', '--output', type=Path, default=None,
                        help='Output path (default: build/font_tiles[_N_M].png)')
    args = parser.parse_args()

    out = generate_mosaic(args.start, args.end, args.cols, args.scale, args.output)
    print(f'Saved {out} ({out.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
