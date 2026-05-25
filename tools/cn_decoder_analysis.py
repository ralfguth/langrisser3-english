#!/usr/bin/env python3
"""cn_decoder_analysis.py — supervised structural analysis of font_cn.bin.

Uses the 708-entry seed (data/cn/tile_char_map_seed.json) as ground
truth. Each entry is (tile_code, hanzi). For each pair we have:
  - 64 raw bytes from font_cn.bin at offset tile_code * 64
  - a 16x16 reference bitmap rendered from Noto Sans CJK SC

Tests:
  bijection   — distinct hanzi → distinct 64-byte blocks?
  density     — set-bits-per-block vs rendered pixel count (1bpp vs 2bpp signature)
  mi          — per-bit mutual information (input_bit, output_pixel)
  hamming     — visually-similar hanzi → encoded-similar blocks?

Run all tests:  python3 tools/cn_decoder_analysis.py all
Run one test:   python3 tools/cn_decoder_analysis.py mi
"""
import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
FONT = PROJ / "data" / "cn" / "font_cn.bin"
SEED = PROJ / "data" / "cn" / "tile_char_map_seed.json"
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

TILE_W = 16
TILE_H = 16
SLOT_BYTES = 64


def load_pairs() -> list[tuple[int, str]]:
    raw = json.loads(SEED.read_text())["map"]
    out = []
    for k, v in raw.items():
        idx = int(k)
        if not v or len(v) != 1:
            continue
        if idx * SLOT_BYTES + SLOT_BYTES > FONT.stat().st_size:
            continue
        out.append((idx, v))
    return sorted(out)


def load_blocks(pairs: list[tuple[int, str]]) -> list[bytes]:
    data = FONT.read_bytes()
    return [data[i * SLOT_BYTES:(i + 1) * SLOT_BYTES] for i, _ in pairs]


def filter_real_glyphs(pairs, blocks):
    """Drop pairs whose block is all-zero or all-0x55 (FNT_SYS-delegated
    or placeholder tiles, not real CN font slots)."""
    out_p, out_b = [], []
    for p, b in zip(pairs, blocks):
        if all(x == 0 for x in b):
            continue
        if all(x == 0x55 for x in b):
            continue
        out_p.append(p)
        out_b.append(b)
    return out_p, out_b


def render_noto(char: str, size: int) -> list[int]:
    """Return 256-element list of 0/1 pixels (row-major, y*16+x)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(NOTO, size, index=2)
    img = Image.new("L", (TILE_W, TILE_H), 0)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), char, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (TILE_W - w) / 2 - bbox[0]
    y = (TILE_H - h) / 2 - bbox[1]
    draw.text((x, y), char, fill=255, font=font)
    px = img.load()
    return [1 if px[xx, yy] > 127 else 0
            for yy in range(TILE_H) for xx in range(TILE_W)]


def render_noto_best(char: str) -> tuple[list[int], int]:
    """Pick the size whose pixel-count is most plausible for this glyph;
    prefer 14 then 13/15 then 12/16 (matches CN font cell)."""
    best = None
    for size in (14, 13, 15, 12, 16):
        bm = render_noto(char, size)
        n = sum(bm)
        if 8 <= n <= 200:  # rough sanity
            if best is None or abs(n - 80) < abs(sum(best[0]) - 80):
                best = (bm, size)
    if best is None:
        best = (render_noto(char, 14), 14)
    return best


def block_bits(block: bytes) -> list[int]:
    """64 bytes → 512-element 0/1 list (MSB-first within each byte)."""
    out = []
    for b in block:
        for i in range(8):
            out.append((b >> (7 - i)) & 1)
    return out


# ============================================================
# Tests
# ============================================================

def test_bijection(pairs, blocks) -> None:
    print("=" * 60)
    print("TEST: bijection — distinct hanzi ↔ distinct 64-byte blocks")
    print("=" * 60)

    char_to_blocks = defaultdict(set)
    block_to_chars = defaultdict(set)
    for (idx, ch), block in zip(pairs, blocks):
        char_to_blocks[ch].add(block)
        block_to_chars[block].add(ch)

    chars_with_multi_block = {c: bs for c, bs in char_to_blocks.items() if len(bs) > 1}
    blocks_with_multi_char = {b: cs for b, cs in block_to_chars.items() if len(cs) > 1}

    print(f"\n  pairs                    : {len(pairs)}")
    print(f"  distinct hanzi           : {len(char_to_blocks)}")
    print(f"  distinct 64-byte blocks  : {len(block_to_chars)}")

    if chars_with_multi_block:
        print(f"\n  ⚠ {len(chars_with_multi_block)} hanzi map to ≥2 distinct blocks:")
        for ch, bs in list(chars_with_multi_block.items())[:5]:
            tiles = [i for (i, c) in pairs if c == ch]
            print(f"    {ch}  tiles={tiles}  ({len(bs)} blocks)")
    else:
        print("\n  ✓ each hanzi maps to a single block")

    if blocks_with_multi_char:
        print(f"\n  ⚠ {len(blocks_with_multi_char)} blocks map to ≥2 hanzi (true aliasing):")
        for b, cs in list(blocks_with_multi_char.items())[:5]:
            print(f"    block={b[:8].hex()}…  chars={sorted(cs)}")
    else:
        print("  ✓ each block maps to a single hanzi  (one-to-one confirmed)")

    # Are all blocks NON-zero (no blank-tile collisions)?
    blank_count = sum(1 for b in blocks if all(x == 0 for x in b))
    print(f"\n  blocks that are all-zero : {blank_count}")


def test_density(pairs, blocks) -> None:
    print("\n" + "=" * 60)
    print("TEST: bit-density vs Noto pixel count")
    print("=" * 60)

    block_bits_count = [sum(bin(x).count("1") for x in b) for b in blocks]
    pixel_counts = []
    for _, ch in pairs:
        bm, _ = render_noto_best(ch)
        pixel_counts.append(sum(bm))

    n = len(blocks)
    sum_x = sum(pixel_counts)
    sum_y = sum(block_bits_count)
    sum_xy = sum(x * y for x, y in zip(pixel_counts, block_bits_count))
    sum_xx = sum(x * x for x in pixel_counts)
    sum_yy = sum(y * y for y in block_bits_count)
    mean_x = sum_x / n
    mean_y = sum_y / n
    var_x = sum_xx / n - mean_x ** 2
    var_y = sum_yy / n - mean_y ** 2
    cov_xy = sum_xy / n - mean_x * mean_y
    pearson = cov_xy / (math.sqrt(var_x * var_y) + 1e-9)
    slope = cov_xy / (var_x + 1e-9)
    intercept = mean_y - slope * mean_x

    print(f"\n  n pairs                  : {n}")
    print(f"  mean pixels (Noto 16x16) : {mean_x:.1f}")
    print(f"  mean set-bits / block    : {mean_y:.1f}")
    print(f"  Pearson r                : {pearson:+.3f}")
    print(f"  linear fit               : bits = {slope:.3f} · pixels + {intercept:.1f}")
    print()
    if pearson > 0.7:
        print("  → strong correlation: encoding bit-count tracks glyph complexity")
    elif pearson > 0.3:
        print("  → moderate correlation: some structure preserved")
    else:
        print("  → near-zero: bit count is detached from rendered density")
    if abs(slope - 1.0) < 0.2:
        print("  → slope ≈ 1.0 consistent with 1bpp bitmap")
    elif abs(slope - 2.0) < 0.3:
        print("  → slope ≈ 2.0 consistent with 2bpp grayscale")


def test_mi(pairs, blocks) -> None:
    print("\n" + "=" * 60)
    print("TEST: per-bit mutual information")
    print("=" * 60)
    print("  For each (input_bit ∈ 0..511, pixel ∈ 0..255) compute MI")
    print("  across all 708 pairs. High MI cells reveal the bit-mapping.")

    # Render all reference bitmaps once
    refs = []
    for _, ch in pairs:
        bm, _ = render_noto_best(ch)
        refs.append(bm)

    n = len(pairs)
    # input_bits[k] = list of bit-vectors per pair, but easier: for each input bit b
    # store the column [pair_i -> bit_value]
    input_cols = [[0] * n for _ in range(512)]
    for i, blk in enumerate(blocks):
        bits = block_bits(blk)
        for b in range(512):
            input_cols[b][i] = bits[b]
    output_cols = [[0] * n for _ in range(256)]
    for i, bm in enumerate(refs):
        for p in range(256):
            output_cols[p][i] = bm[p]

    def mi(x, y) -> float:
        # Both binary. MI in bits.
        n_xy = Counter(zip(x, y))
        n_x = Counter(x)
        n_y = Counter(y)
        total = len(x)
        out = 0.0
        for (xv, yv), c in n_xy.items():
            pxy = c / total
            px = n_x[xv] / total
            py = n_y[yv] / total
            if pxy > 0 and px > 0 and py > 0:
                out += pxy * math.log2(pxy / (px * py))
        return out

    # For speed we compute MI for every (b, p), keep top-3 input bits per pixel.
    print("\n  computing 512 × 256 = 131,072 MI values …")
    best_per_pixel: list[list[tuple[float, int]]] = [[] for _ in range(256)]
    # Pre-sum column counts to skip degenerate cases
    sum_in = [sum(c) for c in input_cols]
    sum_out = [sum(c) for c in output_cols]

    for p in range(256):
        if sum_out[p] == 0 or sum_out[p] == n:
            best_per_pixel[p] = [(0.0, -1)]
            continue
        scored = []
        out_col = output_cols[p]
        for b in range(512):
            if sum_in[b] == 0 or sum_in[b] == n:
                continue
            scored.append((mi(input_cols[b], out_col), b))
        scored.sort(reverse=True)
        best_per_pixel[p] = scored[:3]

    # Aggregate: how many pixels have a "strong" partner (MI > 0.3 bits)?
    # MI of two binary vars ≤ 1.0 (= H(min(p,q))). MI 0.3 is a clear signal.
    strong = sum(1 for sl in best_per_pixel if sl and sl[0][0] > 0.3)
    very_strong = sum(1 for sl in best_per_pixel if sl and sl[0][0] > 0.6)
    moderate = sum(1 for sl in best_per_pixel if sl and sl[0][0] > 0.1)

    print(f"\n  pixels with best-MI > 0.6 : {very_strong:3d} / 256  (near-deterministic mapping)")
    print(f"  pixels with best-MI > 0.3 : {strong:3d} / 256  (clear signal)")
    print(f"  pixels with best-MI > 0.1 : {moderate:3d} / 256  (any signal)")

    # Show the top 10 strongest pixel→bit mappings
    by_strength = sorted(
        ((sl[0][0], sl[0][1], p) for p, sl in enumerate(best_per_pixel) if sl and sl[0][1] >= 0),
        reverse=True,
    )[:10]
    print("\n  top-10 strongest (pixel, best_input_bit, MI):")
    for mi_val, b_idx, p_idx in by_strength:
        py, px = divmod(p_idx, TILE_W)
        bbyte, bbit = divmod(b_idx, 8)
        print(f"    pixel ({px:2d},{py:2d})  ← bit {b_idx:3d} (byte {bbyte:2d}, bit {bbit})   MI={mi_val:.3f}")

    # Save full map for follow-up inspection
    out = {
        "n_pairs": n,
        "best_per_pixel": [
            [{"mi": v, "bit": b} for v, b in sl] for sl in best_per_pixel
        ],
    }
    out_path = PROJ / "build" / "cn_decoder_mi.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    print(f"\n  full per-pixel best-bits saved to {out_path.relative_to(PROJ)}")


def hamming(a: bytes | list[int], b: bytes | list[int]) -> int:
    if isinstance(a, bytes):
        return sum(bin(x ^ y).count("1") for x, y in zip(a, b))
    return sum(p != q for p, q in zip(a, b))


def test_byteprofile(pairs, blocks) -> None:
    print("\n" + "=" * 60)
    print("TEST: per-position byte statistics")
    print("=" * 60)
    print("  For each of 64 byte positions, look at distribution across")
    print("  all 691 real-glyph blocks. Reveals header bytes, structure,")
    print("  or uniform scrambling.")

    n = len(blocks)
    print(f"\n  n blocks                 : {n}")
    print()
    print("  pos  | top_byte (count)    | unique | bit_set_rate | role hint")
    print("  -----+---------------------+--------+--------------+----------")
    for pos in range(64):
        col = [b[pos] for b in blocks]
        cnt = Counter(col)
        top, top_c = cnt.most_common(1)[0]
        unique = len(cnt)
        bits_set = sum(bin(b).count("1") for b in col)
        bit_rate = bits_set / (n * 8)
        role = ""
        if top_c / n > 0.5:
            role = "STRONG (header/marker?)"
        elif top_c / n > 0.2:
            role = "biased"
        elif unique > 200:
            role = "high-entropy (data)"
        elif 0.45 <= bit_rate <= 0.55:
            role = "uniform (~scrambled)"
        if pos < 16 or pos % 4 == 0:
            print(f"  {pos:3d}  | 0x{top:02X} ({top_c:4d}/{n}) | {unique:4d}   | {bit_rate:.3f}        | {role}")

    # Aggregate
    print()
    n_uniform = sum(1 for pos in range(64)
                    if 0.45 <= sum(bin(b[pos]).count("1") for b in blocks) / (n * 8) <= 0.55)
    n_marker = sum(1 for pos in range(64)
                   if Counter(b[pos] for b in blocks).most_common(1)[0][1] / n > 0.3)
    print(f"  positions w/ ~uniform bit rate (.45-.55): {n_uniform}/64")
    print(f"  positions w/ dominant byte (>30%)       : {n_marker}/64")


def test_hamming(pairs, blocks) -> None:
    print("\n" + "=" * 60)
    print("TEST: visual-similarity ↔ encoded-similarity correlation")
    print("=" * 60)

    refs = []
    for _, ch in pairs:
        bm, _ = render_noto_best(ch)
        refs.append(bm)

    n = len(pairs)
    # For tractability, sample up to 5000 pairs of pairs
    import random
    rng = random.Random(0)
    sample = []
    target = 5000
    seen = set()
    while len(sample) < target and len(seen) < n * (n - 1) // 2:
        i = rng.randrange(n)
        j = rng.randrange(n)
        if i == j or (i, j) in seen or (j, i) in seen:
            continue
        seen.add((i, j))
        sample.append((i, j))

    pixel_dists = []
    encoded_dists = []
    for i, j in sample:
        pixel_dists.append(hamming(refs[i], refs[j]))
        encoded_dists.append(hamming(blocks[i], blocks[j]))

    n_s = len(pixel_dists)
    sx = sum(pixel_dists)
    sy = sum(encoded_dists)
    sxy = sum(x * y for x, y in zip(pixel_dists, encoded_dists))
    sxx = sum(x * x for x in pixel_dists)
    syy = sum(y * y for y in encoded_dists)
    mx, my = sx / n_s, sy / n_s
    vx = sxx / n_s - mx ** 2
    vy = syy / n_s - my ** 2
    cv = sxy / n_s - mx * my
    r = cv / (math.sqrt(vx * vy) + 1e-9)

    print(f"\n  sampled pairs            : {n_s}")
    print(f"  mean pixel-Hamming       : {mx:.1f} / 256")
    print(f"  mean encoded-Hamming     : {my:.1f} / 512")
    print(f"  Pearson r                : {r:+.3f}")
    if r > 0.4:
        print("  → encoded space preserves spatial similarity (locality-preserving encoding)")
    elif r > 0.15:
        print("  → weak correlation: encoding partially preserves structure")
    else:
        print("  → ~no correlation: encoding is scrambled relative to glyph appearance")

    # Concrete examples: top-5 most-similar Noto pairs and their encoded dist
    sample_with_dists = sorted(zip(pixel_dists, encoded_dists, sample))
    print("\n  5 most pixel-similar pairs (low pixel-Hamming):")
    for pd, ed, (i, j) in sample_with_dists[:5]:
        ci, cj = pairs[i][1], pairs[j][1]
        print(f"    {ci}↔{cj}  pixel-d={pd:3d}  encoded-d={ed:3d}/512")
    print("\n  5 most pixel-DIFFERENT pairs (high pixel-Hamming):")
    for pd, ed, (i, j) in sample_with_dists[-5:]:
        ci, cj = pairs[i][1], pairs[j][1]
        print(f"    {ci}↔{cj}  pixel-d={pd:3d}  encoded-d={ed:3d}/512")


# ============================================================
# Main
# ============================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("test", nargs="?", default="all",
                    choices=["all", "bijection", "density", "mi", "hamming", "byteprofile"])
    args = ap.parse_args()

    pairs_all = load_pairs()
    blocks_all = load_blocks(pairs_all)
    print(f"loaded {len(pairs_all)} (tile_code → hanzi) pairs")
    print(f"font: {FONT.stat().st_size:,} bytes ({FONT.stat().st_size // SLOT_BYTES} slots)")

    if args.test in ("all", "bijection"):
        test_bijection(pairs_all, blocks_all)

    pairs, blocks = filter_real_glyphs(pairs_all, blocks_all)
    if args.test != "bijection":
        print(f"\nfiltered to {len(pairs)} real-glyph pairs (dropped blank + 0x55 placeholders)")

    if args.test in ("all", "density"):
        test_density(pairs, blocks)
    if args.test in ("all", "mi"):
        test_mi(pairs, blocks)
    if args.test in ("all", "hamming"):
        test_hamming(pairs, blocks)
    if args.test in ("all", "byteprofile"):
        test_byteprofile(pairs, blocks)


if __name__ == "__main__":
    main()
