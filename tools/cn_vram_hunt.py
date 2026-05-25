#!/usr/bin/env python3
"""cn_vram_hunt.py — locate the decoded CN font in a Saturn memory dump.

Strategy: render reference bitmaps of known hanzi (Noto Sans CJK SC),
slide a 32-byte window across each dump file, score each position by
IoU vs the reference. Top hits reveal where the decoded font sits.

Targets characters that appear in the scen122 attract screenshot AND
have known tile codes in the seed. Once a hit is found, we have the
mapping (encoded 64 bytes ↔ decoded 32 bytes) that cracks the format.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parent.parent
DUMP_DIR = Path.home() / "Jogos/emulacao/tools/lang3_tests/dump"
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

# Targets visible on the scen122 attract screenshot, with tile codes
# from the seed.
TARGETS = {
    "国": 440,
    "帝": 434,
    "利": 275,
    "古": 652,
    "里": 597,
    "亚": 468,
    "的": 163,
}

TILE_W, TILE_H = 16, 16


def render_ref(char: str, size: int = 14) -> int:
    """Return Noto bitmap as 256-bit packed int (row-major, MSB-first)."""
    font = ImageFont.truetype(NOTO, size, index=2)
    img = Image.new("L", (TILE_W, TILE_H), 0)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), char, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
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


def bytes_to_bits_msb(data: bytes, off: int) -> int:
    """Read 32 bytes as 1bpp 16x16 row-major MSB-first → 256-bit int."""
    bits = 0
    for r in range(TILE_H):
        b1 = data[off + r * 2]
        b2 = data[off + r * 2 + 1]
        for x in range(8):
            if b1 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + x)
            if b2 & (1 << (7 - x)):
                bits |= 1 << (r * TILE_W + 8 + x)
    return bits


def iou(a: int, b: int) -> float:
    inter = (a & b).bit_count()
    union = (a | b).bit_count()
    return inter / union if union else 0.0


def hunt(dump_path: Path, char: str, refs: list[int],
         stride: int = 1, top_k: int = 5,
         min_iou: float = 0.45) -> list[tuple[float, int]]:
    """Slide window over dump, score IoU. Return top-K (iou, offset)."""
    data = dump_path.read_bytes()
    n = len(data) - 32
    best: list[tuple[float, int]] = []
    for off in range(0, n, stride):
        bits = bytes_to_bits_msb(data, off)
        n_bits = bits.bit_count()
        # Skip blank or fully-on regions
        if n_bits < 8 or n_bits > 200:
            continue
        score = max(iou(bits, r) for r in refs)
        if score >= min_iou:
            best.append((score, off))
    best.sort(reverse=True)
    return best[:top_k]


def render_at(data: bytes, off: int) -> str:
    """ASCII-render the 16x16 tile at offset (for human inspection)."""
    rows = []
    for r in range(TILE_H):
        b1 = data[off + r * 2]
        b2 = data[off + r * 2 + 1]
        line = ""
        for x in range(8):
            line += "█" if b1 & (1 << (7 - x)) else "·"
        for x in range(8):
            line += "█" if b2 & (1 << (7 - x)) else "·"
        rows.append(line)
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--char", default="国",
                    help="hanzi to hunt (must be in TARGETS)")
    ap.add_argument("--dump", default=None,
                    help="single dump file; default = scan all")
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--min-iou", type=float, default=0.45)
    args = ap.parse_args()

    if args.char not in TARGETS:
        print(f"unknown target {args.char!r}; choose from {list(TARGETS)}")
        return 1

    print(f"hunting {args.char} (tile_code {TARGETS[args.char]}) across dump files")
    print(f"using Noto Sans CJK SC reference at sizes 12-16 (max IoU)\n")

    refs = [render_ref(args.char, sz) for sz in (12, 13, 14, 15, 16)]
    print("Noto reference at size 14:")
    img = Image.new("L", (TILE_W, TILE_H), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(NOTO, 14, index=2)
    bbox = d.textbbox((0, 0), args.char, font=f)
    w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
    x = (TILE_W-w)/2 - bbox[0]
    y = (TILE_H-h)/2 - bbox[1]
    d.text((x, y), args.char, fill=255, font=f)
    px = img.load()
    for yy in range(TILE_H):
        line = ""
        for xx in range(TILE_W):
            line += "█" if px[xx, yy] > 127 else "·"
        print(f"  {line}")
    print()

    if args.dump:
        targets = [DUMP_DIR / args.dump]
    else:
        targets = sorted(DUMP_DIR.glob("*.bin"))

    all_hits = []
    for p in targets:
        if p.stat().st_size < 65536:
            continue  # skip tiny dumps (DSP regs etc)
        hits = hunt(p, args.char, refs, args.stride, top_k=3, min_iou=args.min_iou)
        if hits:
            print(f"\n{p.name}  ({p.stat().st_size//1024}K)")
            data = p.read_bytes()
            for score, off in hits:
                print(f"  IoU={score:.3f} at offset 0x{off:08x}:")
                for line in render_at(data, off).split("\n"):
                    print(f"    {line}")
            all_hits.extend((score, p.name, off) for score, off in hits)

    if all_hits:
        all_hits.sort(reverse=True)
        print(f"\n=== Best across all dumps ===")
        for score, name, off in all_hits[:5]:
            print(f"  IoU={score:.3f}  {name} @ 0x{off:08x}")
    else:
        print(f"\nNo strong hits (IoU ≥ {args.min_iou}). Try lower --min-iou,")
        print("a different character, or non-MSB bit ordering.")


if __name__ == "__main__":
    sys.exit(main() or 0)
