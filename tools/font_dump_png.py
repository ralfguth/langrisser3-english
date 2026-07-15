#!/usr/bin/env python3
"""font_dump_png.py — extract LANG/FONT.BIN from a BUILT track01.bin and dump:

  1. build/font_glyphs.png  — every tile rendered 16x16, scaled 4x, labelled with
     its tile index in hex (the value used inside <$XXXX> script codes) + decimal.
  2. build/bigram_map.csv   — every (left,right) pair in the encoder's
     BIGRAM_TILE_MAP with its FONT.BIN tile position (dec + hex).

This reads the ACTUAL font that shipped in the build (not a regenerated one), so
the glyph you see at a given index is exactly what the engine renders for that
<$XXXX> code — the ground truth for decoding leftover 0.2 patch tile-position cruft.

Usage:
    python3 tools/font_dump_png.py [build/<current build dir>/track01.bin]
    (default: resolved from build.py's naming rule for the current git state)
"""
import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from iso_tools import build_file_index, extract_file_data  # noqa: E402
from font_tools import BIGRAM_TILE_MAP                       # noqa: E402

TILE = 16          # source glyph is 16x16, 1bpp, 32 bytes (2 bytes/row, MSB=left)
SCALE = 4
G = TILE * SCALE   # scaled glyph size (64)
LABEL_H = 16       # space under each glyph for the index label
COLS = 32
PAD = 2

def _default_track():
    """Resolve the current build dir via build.py's single naming rule."""
    sys.path.insert(0, str(PROJ))
    import build as _build
    stem = Path(_build._resolve_canonical_cue_name(
        _build.LANGUAGES[_build.DEFAULT_LANG])).stem
    return PROJ / "build" / stem / "track01.bin"


DEFAULT_TRACK = _default_track()
OUT_PNG = PROJ / "build" / "font_glyphs.png"
OUT_CSV = PROJ / "build" / "bigram_map.csv"


def extract_font(track01: Path) -> bytes:
    image = bytearray(track01.read_bytes())
    idx = build_file_index(image)
    e = idx.get("LANG/FONT.BIN")
    if e is None:
        raise SystemExit(f"LANG/FONT.BIN not found in {track01}")
    return extract_file_data(image, e.extent, e.size)


def render_tile(font: bytes, i: int) -> Image.Image:
    """One tile -> a TILExTILE '1' image (MSB of each byte = leftmost pixel)."""
    img = Image.new("1", (TILE, TILE), 0)
    px = img.load()
    base = i * 32
    for row in range(TILE):
        hi = font[base + row * 2]
        lo = font[base + row * 2 + 1]
        bits = (hi << 8) | lo
        for col in range(TILE):
            if bits & (0x8000 >> col):
                px[col, row] = 1
    return img


def main():
    track01 = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TRACK
    if not track01.exists():
        raise SystemExit(f"track01 not found: {track01}")

    font = extract_font(track01)
    ntiles = len(font) // 32
    print(f"FONT.BIN: {len(font):,} bytes ({ntiles} tiles) from {track01.name}")

    rows = (ntiles + COLS - 1) // COLS
    cell_w = G + PAD
    cell_h = G + LABEL_H + PAD
    W = COLS * cell_w + PAD
    H = rows * cell_h + PAD

    canvas = Image.new("RGB", (W, H), (32, 32, 32))
    draw = ImageDraw.Draw(canvas)
    try:
        fnt = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
    except OSError:
        fnt = ImageFont.load_default()

    for i in range(ntiles):
        r, c = divmod(i, COLS)
        x = PAD + c * cell_w
        y = PAD + r * cell_h
        glyph = render_tile(font, i).convert("L").resize((G, G), Image.NEAREST)
        # white glyph on dark cell
        cell = Image.new("RGB", (G, G), (0, 0, 0))
        cell.paste(Image.merge("RGB", (glyph, glyph, glyph)), (0, 0))
        canvas.paste(cell, (x, y))
        draw.rectangle([x, y, x + G - 1, y + G - 1], outline=(64, 64, 80))
        draw.text((x, y + G + 1), f"{i:04X}", fill=(150, 220, 150), font=fnt)
        draw.text((x + 32, y + G + 1), f"{i}", fill=(120, 120, 160), font=fnt)

    canvas.save(OUT_PNG)
    print(f"wrote {OUT_PNG} ({W}x{H})")

    with OUT_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["left", "right", "bigram", "tile_dec", "tile_hex"])
        for (l, r), t in sorted(BIGRAM_TILE_MAP.items(), key=lambda kv: kv[1]):
            w.writerow([l, r, f"{l}{r}", t, f"{t:04X}"])
    print(f"wrote {OUT_CSV} ({len(BIGRAM_TILE_MAP)} bigrams)")


if __name__ == "__main__":
    main()
