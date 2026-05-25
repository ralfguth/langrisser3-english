#!/usr/bin/env python3
"""Brute-force search for the right CN font decoder.

Tries many bit/byte/offset orderings; for each, renders the known
ground-truth tiles, compares to Noto Sans CJK SC reference renderings
of the expected characters, and reports best decoder by mean IoU.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "tools"))

NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def load_font_bin():
    return Path(PROJ.parent / "langrisser3-english"
                / "data" / "cn" / "font_cn.bin").read_bytes()


# Ground truth: tile_code → expected hanzi
GT = {
    4: '。', 61: '・', 128: '间', 163: '的', 195: '，',
    275: '利', 339: '城', 434: '帝', 440: '国', 450: '之',
    468: '亚', 597: '里', 652: '古', 1024: '原', 227: '本',
    1319: '富', 1522: '饶', 1287: '繁', 1288: '荣',
    466: '拉', 229: '卡', 510: '斯', 429: '王',
    1461: '见', 2177: '谒',
}

TILE_W = 16
TILE_H = 16


def render_ref(char: str, size: int = 14) -> int:
    """Render character via Noto, return packed 256-bit int."""
    font = ImageFont.truetype(NOTO, size, index=2)
    probe = Image.new("L", (TILE_W * 3, TILE_H * 3), 0)
    pdraw = ImageDraw.Draw(probe)
    bbox = pdraw.textbbox((0, 0), char, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    img = Image.new("L", (TILE_W, TILE_H), 0)
    draw = ImageDraw.Draw(img)
    x = (TILE_W - w) / 2 - bbox[0]
    y = (TILE_H - h) / 2 - bbox[1]
    draw.text((x, y), char, fill=255, font=font)
    bits = 0
    px = img.load()
    for yy in range(TILE_H):
        for xx in range(TILE_W):
            if px[xx, yy] > 127:
                bits |= 1 << (yy * TILE_W + xx)
    return bits


def best_ref_iou(tile_bits: int, refs: list[int]) -> float:
    """Best IoU between tile and any reference rendering."""
    best = 0.0
    for r in refs:
        inter = (tile_bits & r).bit_count()
        union = (tile_bits | r).bit_count()
        if union and inter / union > best:
            best = inter / union
    return best


# === Decoder hypotheses ===

def dec_msb(font: bytes, code: int, off_fn=lambda c: c * 32, byte_len=32) -> int:
    """1bpp 16x16 row-major MSB-first within byte (current decoder)."""
    off = off_fn(code)
    if off + byte_len > len(font):
        return 0
    bits = 0
    for r in range(TILE_H):
        b1 = font[off + r * 2]
        b2 = font[off + r * 2 + 1]
        for x in range(8):
            if b1 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + x)
        for x in range(8):
            if b2 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + 8 + x)
    return bits


def dec_lsb(font: bytes, code: int, off_fn=lambda c: c * 32) -> int:
    """1bpp 16x16 row-major LSB-first within byte."""
    off = off_fn(code)
    if off + 32 > len(font):
        return 0
    bits = 0
    for r in range(TILE_H):
        b1 = font[off + r * 2]
        b2 = font[off + r * 2 + 1]
        for x in range(8):
            if b1 & (1 << x):
                bits |= 1 << (r * TILE_W + x)
        for x in range(8):
            if b2 & (1 << x):
                bits |= 1 << (r * TILE_W + 8 + x)
    return bits


def dec_byteswap_msb(font: bytes, code: int, off_fn=lambda c: c * 32) -> int:
    """Swap b1/b2 within row, then MSB."""
    off = off_fn(code)
    if off + 32 > len(font):
        return 0
    bits = 0
    for r in range(TILE_H):
        b1 = font[off + r * 2 + 1]  # swapped
        b2 = font[off + r * 2]
        for x in range(8):
            if b1 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + x)
        for x in range(8):
            if b2 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + 8 + x)
    return bits


def dec_colmajor(font: bytes, code: int, off_fn=lambda c: c * 32) -> int:
    """16-bit columns instead of rows."""
    off = off_fn(code)
    if off + 32 > len(font):
        return 0
    bits = 0
    for c in range(TILE_W):
        b1 = font[off + c * 2]
        b2 = font[off + c * 2 + 1]
        word = (b1 << 8) | b2
        for r in range(TILE_H):
            if word & (1 << (15 - r)):
                bits |= 1 << (r * TILE_W + c)
    return bits


def dec_2bpp_planar_low(font: bytes, code: int, off_fn=lambda c: c * 64) -> int:
    """2bpp planar 64 bytes/tile, take LOW plane only."""
    off = off_fn(code)
    if off + 64 > len(font):
        return 0
    bits = 0
    for r in range(TILE_H):
        b1 = font[off + r * 2]
        b2 = font[off + r * 2 + 1]
        for x in range(8):
            if b1 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + x)
        for x in range(8):
            if b2 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + 8 + x)
    return bits


def dec_2bpp_planar_high(font: bytes, code: int, off_fn=lambda c: c * 64) -> int:
    """2bpp planar, take HIGH plane (bytes 32-63)."""
    off = off_fn(code) + 32
    if off + 32 > len(font):
        return 0
    bits = 0
    for r in range(TILE_H):
        b1 = font[off + r * 2]
        b2 = font[off + r * 2 + 1]
        for x in range(8):
            if b1 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + x)
        for x in range(8):
            if b2 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + 8 + x)
    return bits


def dec_2bpp_planar_and(font: bytes, code: int, off_fn=lambda c: c * 64) -> int:
    """2bpp planar, AND of both planes."""
    return (dec_2bpp_planar_low(font, code, off_fn)
            & dec_2bpp_planar_high(font, code, lambda c: off_fn(c) + 0))


def dec_2bpp_planar_or(font: bytes, code: int, off_fn=lambda c: c * 64) -> int:
    return (dec_2bpp_planar_low(font, code, off_fn)
            | dec_2bpp_planar_high(font, code, lambda c: off_fn(c)))


# Decoder set
DECODERS = {
    "1bpp_msb_x32": (dec_msb, lambda c: c * 32),
    "1bpp_lsb_x32": (dec_lsb, lambda c: c * 32),
    "1bpp_bswap_x32": (dec_byteswap_msb, lambda c: c * 32),
    "1bpp_colmajor_x32": (dec_colmajor, lambda c: c * 32),
    "1bpp_msb_minus2_x32": (dec_msb, lambda c: max(0, c - 2) * 32),
    "1bpp_msb_minus16_x32": (dec_msb, lambda c: max(0, c - 16) * 32),
    "1bpp_msb_minus32_x32": (dec_msb, lambda c: max(0, c - 32) * 32),
    "2bpp_planar_low_x64": (dec_2bpp_planar_low, lambda c: c * 64),
    "2bpp_planar_high_x64": (dec_2bpp_planar_high, lambda c: c * 64),
    "2bpp_planar_and_x64": (dec_2bpp_planar_and, lambda c: c * 64),
    "2bpp_planar_or_x64": (dec_2bpp_planar_or, lambda c: c * 64),
    "1bpp_msb_split8x16_at128": (
        # codes <128 narrow at code*16; codes >=128 wide at 2048+(code-128)*32
        lambda f, c, _: dec_split(f, c),
        lambda c: c,
    ),
}


def dec_split(font: bytes, code: int) -> int:
    if code < 128:
        off = code * 16
        if off + 16 > len(font):
            return 0
        bits = 0
        for r in range(TILE_H):
            b = font[off + r]
            for x in range(8):
                if b & (1 << (7 - x)):
                    bits |= 1 << (r * TILE_W + x)
        return bits
    return dec_msb(font, code, lambda c: 2048 + (c - 128) * 32)


def main():
    font = load_font_bin()
    # Pre-render references at multiple sizes; use max IoU across sizes.
    refs = {}
    for tc, ch in GT.items():
        refs[tc] = [render_ref(ch, size) for size in (12, 13, 14, 15, 16)]

    print(f"Testing {len(DECODERS)} decoders against {len(GT)} ground-truth tiles\n")
    print(f"{'decoder':<35}  {'mean_iou':>9}  {'#good':>6}  best/worst")
    results = []
    for name, (decoder, off_fn) in DECODERS.items():
        ious = {}
        for tc in GT:
            try:
                if name.endswith("split8x16_at128"):
                    bits = decoder(font, tc, None)
                else:
                    bits = decoder(font, tc, off_fn)
                ious[tc] = best_ref_iou(bits, refs[tc])
            except Exception as e:
                ious[tc] = 0
        mean = sum(ious.values()) / len(ious)
        good = sum(1 for v in ious.values() if v > 0.4)
        best_t = max(ious, key=ious.get)
        worst_t = min(ious, key=ious.get)
        print(f"  {name:<35}  {mean:8.3f}   {good:3d}    "
              f"best={GT[best_t]}({ious[best_t]:.2f}) worst={GT[worst_t]}({ious[worst_t]:.2f})")
        results.append((mean, name, ious))

    # Show per-tile IoU for best decoder
    results.sort(reverse=True)
    print(f"\nBest decoder: {results[0][1]} (mean IoU = {results[0][0]:.3f})")
    print("\nPer-tile IoU:")
    for tc, ch in sorted(GT.items()):
        v = results[0][2][tc]
        marker = "✓" if v > 0.4 else "✗"
        print(f"  {marker} tile {tc:4d} ({ch}): {v:.3f}")


if __name__ == "__main__":
    main()
