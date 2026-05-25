#!/usr/bin/env python3
"""cn_seed_review.py — generate a frequency-ranked HTML review page
for unmapped CN font tiles.

Pipeline:
  1. Identify tiles used in real D00.DAT + PLOT.DAT but unmapped in the seed.
  2. Compute usage frequency for each.
  3. Render each tile bitmap (from font_cn_decoded.bin) as a PNG.
  4. Run a best-effort Noto matcher to suggest top-5 candidates.
  5. Emit build/cn_seed_review.html — for-each-tile row with bitmap +
     suggestions + an input box for the user to type the correct hanzi.
  6. The page POSTs nothing; a "Save JSON" button triggers a download
     of the user's annotations.

Then run cn_seed_apply.py (or hand-merge) to fold annotations into
tile_char_map_seed.json.
"""
import argparse
import base64
import json
import struct
from io import BytesIO
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
DECODED_FONT = PROJ / "data/cn/font_cn_decoded.bin"
SEED = PROJ / "data/cn/tile_char_map_seed.json"
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
OUT_HTML = PROJ / "build/cn_seed_review.html"

TILE_W = TILE_H = 16
SCALE = 6  # PNG render scale for visibility
TILE_BYTES = 32


def tile_bits(data: bytes, off: int) -> int:
    bits = 0
    for r in range(TILE_H):
        b1, b2 = data[off + r * 2], data[off + r * 2 + 1]
        for x in range(8):
            if b1 & (0x80 >> x):
                bits |= 1 << (r * TILE_W + x)
            if b2 & (0x80 >> x):
                bits |= 1 << (r * TILE_W + 8 + x)
    return bits


def bits_to_png(bits: int, scale: int = SCALE) -> str:
    """Encode 256-bit tile as a base64 PNG data URI."""
    from PIL import Image
    img = Image.new("L", (TILE_W * scale, TILE_H * scale), 255)
    px = img.load()
    for r in range(TILE_H):
        for x in range(TILE_W):
            if bits & (1 << (r * TILE_W + x)):
                for sy in range(scale):
                    for sx in range(scale):
                        px[x * scale + sx, r * scale + sy] = 0
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def render_char_png(char: str, font_obj, scale: int = SCALE) -> str:
    """Render a Noto char as 16x16, return base64 PNG."""
    from PIL import Image, ImageDraw
    big = Image.new("L", (TILE_W * scale, TILE_H * scale), 255)
    # Draw at scaled size for crisp display
    f_big = font_obj  # use as-is at requested point size; scale up image instead
    img = Image.new("L", (TILE_W, TILE_H), 0)
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), char, font=font_obj)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (TILE_W - w) / 2 - bbox[0]
    y = (TILE_H - h) / 2 - bbox[1]
    d.text((x, y), char, fill=255, font=font_obj)
    px = img.load()
    big_px = big.load()
    for r in range(TILE_H):
        for c in range(TILE_W):
            v = 0 if px[c, r] > 127 else 255
            for sy in range(scale):
                for sx in range(scale):
                    big_px[c * scale + sx, r * scale + sy] = v
    buf = BytesIO()
    big.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def collect_usage() -> dict[int, int]:
    """Return {tile_code: usage_count} across D00.DAT + PLOT.DAT."""
    counts: dict[int, int] = {}
    for p in sorted((PROJ / "data/translation_pairs_cn").glob("scen*.json")):
        d = json.loads(p.read_text())
        for e in d["entries"]:
            for t in e.get("cn_tile_codes", []):
                if t < 0xff00:
                    counts[t] = counts.get(t, 0) + 1
    plot = (PROJ / "data/cn/plot_cn.dat").read_bytes()
    file_size = struct.unpack(">I", plot[:4])[0]
    offsets = list(struct.unpack(">35H", plot[4:74])) + [file_size]
    for blk in range(35):
        s, e = offsets[blk], offsets[blk + 1]
        body = plot[s + 8:e]
        codes = struct.unpack(f">{len(body)//2}H", body[:len(body)//2*2])
        for c in codes:
            if c < 0xff00:
                counts[c] = counts.get(c, 0) + 1
    return counts


def build_refs():
    """Render Noto candidates: 21K Han + punct + ASCII, 3 sizes."""
    from PIL import ImageFont
    fonts = [ImageFont.truetype(NOTO, sz, index=2) for sz in (13, 14, 15)]
    refs: dict[str, list[int]] = {}

    def render(font_obj, char):
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

    print("  rendering Noto reference set …")
    for cp_range in [range(0x4E00, 0x9FA6), range(0x3000, 0x3040),
                     range(0x3040, 0x3100), range(0xFF00, 0xFFF0),
                     range(0x20, 0x7F)]:
        for cp in cp_range:
            char = chr(cp)
            bs = []
            empty = 0
            for f in fonts:
                b = render(f, char)
                bs.append(b)
                if b.bit_count() < 4:
                    empty += 1
            if empty == len(fonts):
                continue
            refs[char] = bs
    print(f"  ref set: {len(refs)} chars × {len(fonts)} sizes")
    return refs


def best_matches(tile_b: int, refs: dict, top_k: int = 5):
    n_t = tile_b.bit_count()
    if n_t < 4:
        return []
    scored = []
    for ch, bs in refs.items():
        best = 0
        for b in bs:
            inter = (tile_b & b).bit_count()
            union = (tile_b | b).bit_count()
            if union:
                iou = inter / union
                if iou > best:
                    best = iou
        if best > 0.20:
            scored.append((best, ch))
    scored.sort(reverse=True)
    return scored[:top_k]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top-n", type=int, default=300,
                    help="how many highest-frequency unmapped tiles to include")
    ap.add_argument("--out", type=Path, default=OUT_HTML)
    args = ap.parse_args()

    decoded = DECODED_FONT.read_bytes()
    seed = {int(k): v for k, v in
            json.loads(SEED.read_text())["map"].items() if v}
    print(f"seed: {len(seed)} entries")

    print("collecting usage …")
    usage = collect_usage()
    unmapped = [(t, c) for t, c in usage.items() if t not in seed]
    unmapped.sort(key=lambda x: -x[1])
    print(f"unmapped tiles in real text: {len(unmapped)}")
    print(f"top-{args.top_n} cover {sum(c for _, c in unmapped[:args.top_n])} usages "
          f"(out of {sum(c for _, c in unmapped)} total unmapped usages)")

    refs = build_refs()
    from PIL import ImageFont
    suggest_font = ImageFont.truetype(NOTO, 14, index=2)

    print(f"\nmatching top-{args.top_n} unmapped tiles …")
    rows = []
    for i, (code, freq) in enumerate(unmapped[:args.top_n]):
        if code * TILE_BYTES + TILE_BYTES > len(decoded):
            continue
        tile_b = tile_bits(decoded, code * TILE_BYTES)
        if tile_b.bit_count() < 4:
            continue
        tile_png = bits_to_png(tile_b)
        matches = best_matches(tile_b, refs, top_k=5)
        suggestions = []
        for iou, ch in matches:
            suggestions.append({
                "char": ch,
                "iou": round(iou, 3),
                "png": render_char_png(ch, suggest_font),
            })
        rows.append({
            "code": code,
            "freq": freq,
            "tile_png": tile_png,
            "suggestions": suggestions,
        })
        if (i + 1) % 50 == 0:
            print(f"    {i+1} / {args.top_n}")

    write_html(rows, args.out)
    print(f"\nwrote {args.out.relative_to(PROJ)}")
    print(f"  open in a browser, fill in correct hanzi, click 'Save JSON'.")


def write_html(rows, path: Path):
    parts = []
    parts.append("""<!doctype html>
<html lang=en><meta charset=utf-8>
<title>CN seed review</title>
<style>
  body { font: 14px/1.4 system-ui, sans-serif; margin: 1em; max-width: 1100px; }
  h1 { font-size: 18px; }
  .row { display: flex; align-items: center; gap: 1em; padding: 6px 0;
         border-bottom: 1px solid #ddd; }
  .tile { border: 1px solid #999; }
  .meta { width: 110px; font-family: monospace; font-size: 12px; }
  .sugs { display: flex; gap: 6px; }
  .sug { text-align: center; cursor: pointer; padding: 2px;
         border: 1px solid transparent; border-radius: 3px; }
  .sug:hover { border-color: #4af; background: #def; }
  .sug img { display: block; width: 48px; height: 48px; image-rendering: pixelated; }
  .sug small { color: #666; font-size: 10px; }
  input.ans { font-size: 24px; width: 64px; text-align: center;
              border: 2px solid #aaa; border-radius: 4px; padding: 4px; }
  input.ans:focus { border-color: #4af; outline: none; }
  input.ans.dirty { border-color: #393; background: #efe; }
  .toolbar { position: sticky; top: 0; background: white; padding: 8px 0;
             z-index: 10; border-bottom: 2px solid #333; margin-bottom: 12px; }
  button { font-size: 14px; padding: 6px 16px; cursor: pointer; }
  .stat { color: #666; margin-left: 12px; }
</style>
<h1>CN font seed review</h1>
<p>For each tile (game bitmap, large), pick the suggestion whose Noto
glyph matches it, OR type the correct hanzi directly. Click 'Save JSON'
to download annotations.</p>
<div class=toolbar>
  <button onclick=saveJson()>Save JSON</button>
  <span class=stat id=stat>0 annotated</span>
</div>
""")
    for r in rows:
        parts.append(f"""<div class=row data-code="{r['code']}">
  <img class=tile src="{r['tile_png']}" width="96" height="96"
       style="image-rendering: pixelated">
  <div class=meta>tile {r['code']}<br>×{r['freq']}</div>
  <div class=sugs>""")
        for s in r["suggestions"]:
            parts.append(
                f'<div class=sug onclick="pick({r["code"]}, {json.dumps(s["char"])})">'
                f'<img src="{s["png"]}"><small>{s["char"]} {s["iou"]:.2f}</small></div>'
            )
        parts.append(f"""</div>
  <input class=ans data-code="{r['code']}" maxlength=2
         oninput="dirty(this)" onfocus="this.select()">
</div>""")

    parts.append("""<script>
const STAT = document.getElementById('stat');
function refresh() {
  const n = document.querySelectorAll('input.ans.dirty').length;
  STAT.textContent = n + ' annotated';
}
function dirty(el) {
  if (el.value.trim()) el.classList.add('dirty');
  else el.classList.remove('dirty');
  refresh();
}
function pick(code, ch) {
  const inp = document.querySelector('input.ans[data-code="' + code + '"]');
  inp.value = ch;
  dirty(inp);
}
function saveJson() {
  const out = {};
  document.querySelectorAll('input.ans.dirty').forEach(el => {
    out[el.dataset.code] = el.value.trim();
  });
  const blob = new Blob([JSON.stringify(out, null, 1)],
                        {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'cn_seed_review_annotations.json';
  a.click();
}
</script>""")
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
