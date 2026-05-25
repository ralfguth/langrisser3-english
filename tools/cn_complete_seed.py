#!/usr/bin/env python3
"""cn_complete_seed.py — auto-label every tile in font_cn_decoded.bin.

Approach:
  1. Render a large CJK reference set (Unified Ideographs + punctuation
     + ASCII + halfwidth/fullwidth) in Noto Sans CJK SC across multiple
     sizes — store each glyph's 16×16 bitmap as a 256-bit packed int.
  2. For each of the 2253 decoded game tiles (32 B in
     `data/cn/font_cn_decoded.bin`, 1bpp 16×16 row-major MSB-first),
     find the reference char with highest IoU. Record the top-5
     candidates and a confidence score.
  3. Validate against the existing 708-entry seed
     (`data/cn/tile_char_map_seed.json`). If the matcher's top-1 ==
     seed for ≥90% of the 691 real-glyph entries, the matcher is
     trustworthy for the unmapped 1545.

Modes:
  --validate   only run validation against the seed (fast iteration)
  --build      build the full label map (slower, ~2 min)
  --debug TILE inspect a specific tile_code's match details

Output: build/cn_tile_label_map.json with entries like
        {"123": {"top": "国", "iou": 0.71, "candidates": [...]}}
"""
import argparse
import json
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
DECODED_FONT = PROJ / "data" / "cn" / "font_cn_decoded.bin"
SEED = PROJ / "data" / "cn" / "tile_char_map_seed.json"
NOTO_SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
NOTO_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"

TILE_W = TILE_H = 16
TILE_BYTES = 32


def char_ranges():
    """Iterate over candidate Unicode codepoints to render."""
    # CJK Unified Ideographs
    yield from range(0x4E00, 0x9FA6)
    # CJK Symbols & Punctuation
    yield from range(0x3000, 0x3040)
    # Hiragana / Katakana (just in case)
    yield from range(0x3040, 0x3100)
    # Halfwidth / Fullwidth Forms
    yield from range(0xFF00, 0xFFF0)
    # ASCII
    yield from range(0x20, 0x7F)


def tile_bits(data: bytes, off: int) -> int:
    """32 bytes → 256-bit packed int (1bpp 16×16 MSB row-major)."""
    bits = 0
    for r in range(TILE_H):
        b1, b2 = data[off + r * 2], data[off + r * 2 + 1]
        for x in range(8):
            if b1 & (0x80 >> x):
                bits |= 1 << (r * TILE_W + x)
            if b2 & (0x80 >> x):
                bits |= 1 << (r * TILE_W + 8 + x)
    return bits


def render_char(font_obj, char: str, size_target: int = 14) -> int:
    """Render char to 16×16, return as 256-bit int. size_target hints at
    cap height; actual size is the font.size that was loaded."""
    from PIL import Image, ImageDraw
    img = Image.new("L", (TILE_W, TILE_H), 0)
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), char, font=font_obj)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (TILE_W - w) / 2 - bbox[0]
    y = (TILE_H - h) / 2 - bbox[1]
    d.text((x, y), char, fill=255, font=font_obj)
    bits = 0
    px = img.load()
    for yy in range(TILE_H):
        for xx in range(TILE_W):
            if px[xx, yy] > 127:
                bits |= 1 << (yy * TILE_W + xx)
    return bits


def build_refs(sizes=(12, 13, 14, 15, 16),
               include_serif=False) -> dict[str, list[int]]:
    """Render all candidate chars at multiple sizes. Returns
    {char: [bits_at_size0, bits_at_size1, ...]}."""
    from PIL import ImageFont
    print(f"  loading fonts at sizes {sizes} …")

    fonts = []
    for sz in sizes:
        # index=2 in the .ttc selects SC variant for NotoSansCJK
        fonts.append(ImageFont.truetype(NOTO_SANS, sz, index=2))
    if include_serif:
        for sz in sizes:
            fonts.append(ImageFont.truetype(NOTO_SERIF, sz, index=2))

    refs: dict[str, list[int]] = {}
    n_rendered = 0
    skipped = 0
    for cp in char_ranges():
        char = chr(cp)
        bitss = []
        empty_count = 0
        for f in fonts:
            b = render_char(f, char)
            bitss.append(b)
            if b.bit_count() < 4:
                empty_count += 1
        # Skip chars where every size renders nearly-blank (font missing glyph)
        if empty_count == len(fonts):
            skipped += 1
            continue
        refs[char] = bitss
        n_rendered += 1
        if n_rendered % 2000 == 0:
            print(f"    rendered {n_rendered} chars …")
    print(f"  total: {n_rendered} chars rendered, {skipped} skipped (no glyph in Noto)")
    return refs


def best_match(tile: int, refs: dict[str, list[int]],
               top_k: int = 5) -> list[tuple[float, str]]:
    """For one tile, return top-k (iou, char) sorted desc."""
    n_tile = tile.bit_count()
    if n_tile < 4:
        return []  # blank tile
    scored = []
    for char, bitss in refs.items():
        best = 0.0
        for b in bitss:
            inter = (tile & b).bit_count()
            union = (tile | b).bit_count()
            if union:
                iou = inter / union
                if iou > best:
                    best = iou
        if best > 0.2:
            scored.append((best, char))
    scored.sort(reverse=True)
    return scored[:top_k]


def load_seed() -> dict[int, str]:
    raw = json.loads(SEED.read_text())["map"]
    return {int(k): v for k, v in raw.items() if v and len(v) == 1}


def validate(refs: dict, decoded: bytes) -> None:
    """Cross-check matcher against the 708-entry seed."""
    seed = load_seed()
    print(f"\nvalidating matcher against {len(seed)} seed entries …")
    correct = 0
    in_top5 = 0
    skipped = 0
    wrong_examples = []
    for code, expected in seed.items():
        off = code * TILE_BYTES
        if off + TILE_BYTES > len(decoded):
            skipped += 1
            continue
        tile = tile_bits(decoded, off)
        if tile.bit_count() < 4:
            skipped += 1
            continue
        # If the char isn't even in our reference set (e.g., not Han block),
        # we can't get it. Skip but note.
        if expected not in refs:
            skipped += 1
            continue
        top = best_match(tile, refs, top_k=5)
        if not top:
            continue
        if top[0][1] == expected:
            correct += 1
            in_top5 += 1
        else:
            in_t5 = any(c == expected for _, c in top)
            if in_t5:
                in_top5 += 1
            if len(wrong_examples) < 10:
                wrong_examples.append((code, expected, top))
    n_eval = len(seed) - skipped
    print(f"\n  evaluable     : {n_eval} / {len(seed)}  (skipped {skipped})")
    print(f"  top-1 correct : {correct} / {n_eval}  ({100*correct/n_eval:.1f}%)")
    print(f"  in top-5      : {in_top5} / {n_eval}  ({100*in_top5/n_eval:.1f}%)")
    if wrong_examples:
        print(f"\n  sample mismatches (matcher got top-1 wrong):")
        for code, exp, top in wrong_examples:
            tops = ", ".join(f"{c}({iou:.2f})" for iou, c in top[:3])
            print(f"    tile {code:4d}: expected {exp}  got [{tops}]")


def build_full(refs: dict, decoded: bytes, out_path: Path,
               n_tiles: int = 2253) -> None:
    """Match every tile and save the full map."""
    seed = load_seed()
    out = {}
    print(f"\nlabeling all {n_tiles} tiles …")
    for code in range(n_tiles):
        off = code * TILE_BYTES
        if off + TILE_BYTES > len(decoded):
            continue
        tile = tile_bits(decoded, off)
        bits_set = tile.bit_count()
        entry = {"bits": bits_set}
        if bits_set < 4:
            entry["status"] = "blank"
        else:
            top = best_match(tile, refs, top_k=5)
            if top:
                entry["top"] = top[0][1]
                entry["iou"] = round(top[0][0], 3)
                entry["candidates"] = [
                    {"char": c, "iou": round(iou, 3)} for iou, c in top
                ]
                entry["status"] = (
                    "high" if top[0][0] > 0.65
                    else "medium" if top[0][0] > 0.50
                    else "low"
                )
            else:
                entry["status"] = "no_match"
        if code in seed:
            entry["seed"] = seed[code]
            if entry.get("top") and entry["top"] != seed[code]:
                entry["seed_disagrees"] = True
        out[str(code)] = entry
        if (code + 1) % 200 == 0:
            print(f"    {code + 1} / {n_tiles}")

    # Coverage stats
    n_high = sum(1 for v in out.values() if v.get("status") == "high")
    n_med = sum(1 for v in out.values() if v.get("status") == "medium")
    n_low = sum(1 for v in out.values() if v.get("status") == "low")
    n_blank = sum(1 for v in out.values() if v.get("status") == "blank")
    n_seed_disagree = sum(1 for v in out.values() if v.get("seed_disagrees"))

    print(f"\n  high   confidence (IoU > 0.65) : {n_high:5d}")
    print(f"  medium confidence (IoU > 0.50) : {n_med:5d}")
    print(f"  low    confidence (IoU ≤ 0.50) : {n_low:5d}")
    print(f"  blank tiles                    : {n_blank:5d}")
    print(f"  seed disagreements (review!)   : {n_seed_disagree:5d}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"\n  wrote {out_path.relative_to(PROJ)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["validate", "build", "debug"],
                    help="validate against seed | build full map | debug TILE")
    ap.add_argument("--tile", type=int, default=0,
                    help="(debug only) tile_code to inspect")
    ap.add_argument("--include-serif", action="store_true",
                    help="also render Noto Serif CJK SC variants")
    ap.add_argument("--sizes", type=str, default="12,13,14,15,16",
                    help="comma-separated sizes to render at")
    ap.add_argument("--out", type=Path,
                    default=PROJ / "build" / "cn_tile_label_map.json")
    args = ap.parse_args()

    sizes = tuple(int(s) for s in args.sizes.split(","))
    print(f"sizes: {sizes}, include_serif: {args.include_serif}")

    decoded = DECODED_FONT.read_bytes()
    print(f"decoded font: {len(decoded)} bytes "
          f"({len(decoded) // TILE_BYTES} glyphs)")

    refs = build_refs(sizes, include_serif=args.include_serif)
    print(f"reference set: {len(refs)} chars × {len(sizes)}"
          f"{'×2' if args.include_serif else ''} sizes")

    if args.mode == "validate":
        validate(refs, decoded)
    elif args.mode == "build":
        validate(refs, decoded)
        build_full(refs, decoded, args.out)
    elif args.mode == "debug":
        off = args.tile * TILE_BYTES
        tile = tile_bits(decoded, off)
        print(f"\ntile {args.tile} bitmap ({tile.bit_count()} pixels):")
        for r in range(TILE_H):
            line = ""
            for x in range(TILE_W):
                line += "█" if tile & (1 << (r * TILE_W + x)) else "·"
            print(f"  {line}")
        top = best_match(tile, refs, top_k=10)
        print(f"\ntop-10 matches:")
        for iou, char in top:
            print(f"  {char}  IoU={iou:.3f}")


if __name__ == "__main__":
    main()
