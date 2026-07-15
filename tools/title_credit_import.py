#!/usr/bin/env python3
"""Convert an edited title-credit PNG into the indexed asset the build consumes.

The artist edits a 320x224 RGBA canvas (the title with the logo as context and
the empty top/footer to draw the credit in). This tool tiles ONLY the cells that
are empty in the original logo art and writes them as an indexed (mode 'P') PNG
whose pixel values are TITLE.DG2 palette indices:

  - grayscale pixels  -> the credit grayscale ramp (slots 16..31, written into the
                         title palette by tools/title_dg2.py at build time)
  - colored pixels    -> the nearest existing title color (idx 1..8, 52)
  - transparent/empty -> index 0

The real palette is read straight from TITLE.DG2's embedded palette (res1), so no
external palette file is needed. Output feeds title_dg2.apply_footer_indexed.

Usage:
    python3 tools/title_credit_import.py INPUT.png [OUTPUT.png]
                                         [--jp-iso DIR]
Defaults: OUTPUT = assets/title_credit/title_credit_indexed.png
"""
import argparse
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tools import title_dg2  # noqa: E402
from tools.iso_tools import build_file_index, extract_file_data  # noqa: E402

DEFAULT_OUT = REPO / "assets" / "title_credit" / "title_credit_indexed.png"
USED_COLORS = (1, 2, 3, 4, 5, 6, 7, 8, 52)  # the stock title palette colors


def _load_jp_title(jp_dir: Path) -> bytes:
    img = bytearray(sorted(jp_dir.glob("*rack*01*.bin"))[0].read_bytes())
    idx = build_file_index(img)
    e = next(idx[k] for k in idx if k.upper().endswith("TITLE.DG2"))
    return extract_file_data(img, e.extent, e.size)


def _palette_rgb(dg2: bytes):
    cont = title_dg2.parse_container(dg2)
    res1 = dg2[cont.resources[1].offset:cont.resources[1].offset + cont.resources[1].size]
    P = title_dg2.PALETTE_RES1_OFFSET
    pal = []
    for i in range(256):
        v = struct.unpack_from(">H", res1, P + i * 2)[0]
        pal.append(((v & 0x1F) << 3, ((v >> 5) & 0x1F) << 3, ((v >> 10) & 0x1F) << 3))
    return pal


def convert(input_png: Path, output_png: Path, jp_dir: Path) -> int:
    from PIL import Image

    dg2 = _load_jp_title(jp_dir)
    pal = _palette_rgb(dg2)
    grid = title_dg2.decode_logo_grid(dg2)
    ramp = title_dg2.credit_ramp_rgb()

    def slot_for(rgb):
        r, g, b = rgb
        if abs(r - g) < 12 and abs(g - b) < 12:          # grayscale -> ramp
            return title_dg2.credit_ramp_slot(rgb)
        return min(USED_COLORS,                           # colored -> nearest title color
                   key=lambda i: sum((a - c) ** 2 for a, c in zip(pal[i], rgb)))

    src = Image.open(input_png).convert("RGBA")
    if src.size != (320, 224):
        raise SystemExit(f"{input_png}: expected 320x224, got {src.size}")
    sp = src.load()
    out = Image.new("P", (320, 224), 0)
    out.putpalette(sum((list(c) for c in pal), []))
    op = out.load()
    W, H = title_dg2.GRID_W, title_dg2.GRID_H
    painted = 0
    for row in range(H):
        for col in range(W):
            if grid.tile(row, col) != 0:
                continue  # original logo cell — leave empty in the overlay asset
            for y in range(8):
                for x in range(8):
                    px = sp[col * 8 + x, row * 8 + y]
                    if px[3] >= 128:
                        op[col * 8 + x, row * 8 + y] = slot_for(px[:3])
                        painted += 1
    output_png.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_png, transparency=0)
    return painted


def convert_full(input_png: Path, output_png: Path, jp_dir: Path,
                 new_colors: int = 247) -> int:
    """Convert a FULL-title RGBA edit into the indexed asset for
    title_dg2.apply_full_logo (the whole logo plane is rebuilt — moved elements
    work, transparent stays transparent so the sky shows).

    Stock title colors 0..8 are KEPT; the edit's opaque pixels are quantized into
    up to `new_colors` entries placed in palette slots 9.. (8bpp). Alpha < 128 is
    transparent (index 0). Feeds title_dg2.apply_full_logo, which injects only
    slots 9.. into the CRAM (0..8 stay intact) and rebuilds the grid append-only.
    """
    from PIL import Image

    dg2 = _load_jp_title(jp_dir)
    pal = _palette_rgb(dg2)
    base = title_dg2.PRESERVED_PALETTE_SLOTS
    cap = min(new_colors, 256 - base)

    src = Image.open(input_png).convert("RGBA")
    if src.size != (320, 224):
        raise SystemExit(f"{input_png}: expected 320x224, got {src.size}")
    sp = src.load()
    # composite on black to bake anti-aliasing, then quantize the content
    comp = Image.alpha_composite(Image.new("RGBA", src.size, (0, 0, 0, 255)),
                                 src).convert("RGB")
    q = comp.quantize(colors=cap, method=Image.MEDIANCUT)
    qp = q.getpalette()
    qpx = q.load()

    out = Image.new("P", src.size, 0)
    full_pal = sum(([r, g, b] for (r, g, b) in pal[:base]), [])   # keep 0..8
    full_pal += qp[:cap * 3]                                       # artist colors -> 9..
    full_pal += [0] * (768 - len(full_pal))
    out.putpalette(full_pal)
    op = out.load()
    painted = 0
    for y in range(src.size[1]):
        for x in range(src.size[0]):
            if sp[x, y][3] >= 128:
                op[x, y] = base + qpx[x, y]
                painted += 1
    output_png.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_png, transparency=0)
    return painted


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path, nargs="?", default=DEFAULT_OUT)
    ap.add_argument("--jp-iso", type=Path, default=Path(
        "/home/ralf/Jogos/emulacao/romsets/sega-saturn/cue-bin/Langrisser III (Japan)"))
    ap.add_argument("--full", action="store_true",
                    help="rebuild the WHOLE logo plane (moved elements + freeform "
                         "colors) instead of only filling the empty footer/margin")
    a = ap.parse_args()
    if a.full:
        n = convert_full(a.input, a.output, a.jp_iso)
        print(f"wrote {a.output} ({n} opaque px, full-logo rebuild)")
    else:
        n = convert(a.input, a.output, a.jp_iso)
        print(f"wrote {a.output} ({n} painted px in non-logo cells)")


if __name__ == "__main__":
    main()
