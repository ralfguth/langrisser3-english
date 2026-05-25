#!/usr/bin/env python3
"""
build_cn_tile_map.py — match each CN font tile against rendered hanzi/kana
to identify which character it represents.

Strategy: render candidate characters (ASCII, kana, CJK punct, hanzi) at
16x16 1bpp using Noto Sans CJK SC, centered. Pack each 16x16 bitmap into
a 256-bit Python int; Hamming distance = (a ^ b).bit_count(). Pure-Python
to avoid numpy dependency.

Saves data/cn/tile_char_map.json with best match + top-3 alternates +
distance, so downstream consumers can flag low-confidence matches.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
from cn_font_render import TILE_H, TILE_W, load_font, tile_count, tile_pixels
from cn_denoise import denoise

OUT_MAP = PROJ / "data" / "cn" / "tile_char_map.json"
NOTO_TTC = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def candidate_chars() -> list[str]:
    chars: list[str] = []
    chars += [chr(c) for c in range(0x20, 0x7F)]            # ASCII
    chars += [chr(c) for c in range(0x3000, 0x3040)]        # CJK punct
    chars += [chr(c) for c in range(0x3040, 0x30A0)]        # Hiragana
    chars += [chr(c) for c in range(0x30A0, 0x3100)]        # Katakana
    chars += [chr(c) for c in range(0xFF01, 0xFF60)]        # Fullwidth ASCII
    chars += [chr(c) for c in range(0xFFE0, 0xFFE7)]        # Fullwidth signs
    chars += [chr(c) for c in range(0x4E00, 0x9FA6)]        # CJK Unified
    return chars


def img_to_bits(img: Image.Image) -> int:
    """Pack a 16x16 L-mode image into a 256-bit int (>127 = on)."""
    bits = 0
    px = img.load()
    for y in range(TILE_H):
        for x in range(TILE_W):
            if px[x, y] > 127:
                bits |= 1 << (y * TILE_W + x)
    return bits


def render_centered_bits(char: str, font: ImageFont.FreeTypeFont) -> int | None:
    """Render `char` centered into a 16x16 bitmap → packed bits. None if empty."""
    probe = Image.new("L", (TILE_W * 3, TILE_H * 3), 0)
    pdraw = ImageDraw.Draw(probe)
    bbox = pdraw.textbbox((0, 0), char, font=font)
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    img = Image.new("L", (TILE_W, TILE_H), 0)
    draw = ImageDraw.Draw(img)
    x = (TILE_W - w) / 2 - bbox[0]
    y = (TILE_H - h) / 2 - bbox[1]
    draw.text((x, y), char, fill=255, font=font)
    bits = img_to_bits(img)
    return bits if bits else None


def tile_to_bits(font_data: bytes, idx: int, do_denoise: bool = True,
                 min_size: int = 3) -> int:
    px = tile_pixels(font_data, idx)
    if do_denoise:
        px = denoise(px, min_size=min_size)
    bits = 0
    for y in range(TILE_H):
        row = px[y]
        for x in range(TILE_W):
            if row[x]:
                bits |= 1 << (y * TILE_W + x)
    return bits


def find_sc_font_index(path: str) -> int:
    for i in range(8):
        try:
            f = ImageFont.truetype(path, 14, index=i)
            family, _style = f.getname()
            if "SC" in family:
                return i
        except OSError:
            continue
    return 0


def jaccard_score(a: int, b: int) -> float:
    """IoU on packed bit representations: |a∩b| / |a∪b|. Higher = better."""
    inter = (a & b).bit_count()
    union = (a | b).bit_count()
    if union == 0:
        return 0.0
    return inter / union


def evaluate_size(size: int, sc_idx: int, chars: list[str],
                   tile_bits: list[int]) -> tuple[float, list[str], list[int]]:
    """Render all candidates at `size`. Returns (mean best IoU on sample, cands, bits).
    Higher mean IoU = better. We negate to keep "lower = better" convention."""
    font = ImageFont.truetype(NOTO_TTC, size, index=sc_idx)
    cand_chars: list[str] = []
    cand_bits: list[int] = []
    for ch in chars:
        b = render_centered_bits(ch, font)
        if b is None:
            continue
        cand_chars.append(ch)
        cand_bits.append(b)
    sample = tile_bits[::max(1, len(tile_bits) // 200)]
    total = 0.0
    for tb in sample:
        if tb == 0:
            continue
        best = 0.0
        for cb in cand_bits:
            inter = (tb & cb).bit_count()
            union = (tb | cb).bit_count()
            iou = inter / union if union else 0.0
            if iou > best:
                best = iou
        total += best
    return -total / len(sample), cand_chars, cand_bits


def main() -> int:
    print("Loading CN font...")
    font_data = load_font()
    n_tiles = tile_count(font_data)
    print(f"  {n_tiles} tiles")

    sc_idx = find_sc_font_index(NOTO_TTC)
    print(f"Noto Sans CJK SC index: {sc_idx}")

    chars = candidate_chars()
    print(f"Candidate pool: {len(chars)} chars")

    print("Packing tile bitmaps...")
    tile_bits = [tile_to_bits(font_data, i) for i in range(n_tiles)]

    print("Rendering candidates at multiple sizes (12-16)...")
    multi_chars: list[str] = []
    multi_bits: list[int] = []
    multi_size: list[int] = []
    for size in (12, 13, 14, 15, 16):
        font = ImageFont.truetype(NOTO_TTC, size, index=sc_idx)
        for ch in chars:
            b = render_centered_bits(ch, font)
            if b is None:
                continue
            multi_chars.append(ch)
            multi_bits.append(b)
            multi_size.append(size)
    print(f"  total renders: {len(multi_bits)}")

    # Per-character: keep best IoU across sizes
    cand_chars = multi_chars
    cand_bits = multi_bits
    print(f"Matching all {n_tiles} tiles via IoU (max across sizes)...")

    out_tiles = {}
    for i, tb in enumerate(tile_bits):
        if tb == 0:
            out_tiles[str(i)] = {
                "char": "", "iou": 0.0, "tile_pixels": 0,
                "alt": [], "alt_iou": [],
            }
            continue
        # Best IoU per char across sizes
        best_per_char: dict[str, float] = {}
        for j, cb in enumerate(cand_bits):
            inter = (tb & cb).bit_count()
            union = (tb | cb).bit_count()
            iou = inter / union if union else 0.0
            ch = cand_chars[j]
            if iou > best_per_char.get(ch, -1):
                best_per_char[ch] = iou
        ranked = sorted(best_per_char.items(), key=lambda kv: -kv[1])[:3]
        out_tiles[str(i)] = {
            "char": ranked[0][0],
            "iou": round(ranked[0][1], 3),
            "tile_pixels": tb.bit_count(),
            "alt": [ch for ch, _ in ranked[1:]],
            "alt_iou": [round(v, 3) for _, v in ranked[1:]],
        }
        if i % 200 == 0:
            print(f"  {i}/{n_tiles}")

    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    OUT_MAP.write_text(json.dumps({
        "render_sizes": [12, 13, 14, 15, 16],
        "n_tiles": n_tiles,
        "n_candidates": len(set(cand_chars)),
        "tiles": out_tiles,
    }, ensure_ascii=False, indent=2))
    print(f"Wrote {OUT_MAP}")

    print("\nSanity checks:")
    for tid in (644, 758, 4, 163, 466, 229, 453, 468):
        if str(tid) not in out_tiles:
            continue
        e = out_tiles[str(tid)]
        print(f"  tile {tid:4d}  px={e['tile_pixels']:3d}  "
              f"→ '{e['char']}' (iou={e['iou']:.2f})  alts={e['alt']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
