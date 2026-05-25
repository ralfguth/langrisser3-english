#!/usr/bin/env python3
"""
dump_cn_en_pairs.py — produce CN↔JP↔EN pair JSON for one or more scenarios.

For each scenario:
  - Parses CN D00.DAT to get raw entries.
  - Joins with the existing data/translation_pairs/scenNNN.json (JP/EN).
  - Writes data/translation_pairs_cn/scenNNN.json with cn_tile_codes,
    cn_codes (control codes), cn_byte_length per entry.
  - Renders each entry's tile sequence as a horizontal PNG strip
    (data/translation_pairs_cn/img/scenNNN/entry_NNN.png) so agents
    can read the actual Chinese glyphs via vision.

Usage:
    python3 tools/dump_cn_en_pairs.py SCEN [SCEN ...]   # one or more scenario ids
    python3 tools/dump_cn_en_pairs.py --all              # all 125 scenarios
"""
import argparse
import json
import struct
import sys
from pathlib import Path

from PIL import Image

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
from d00_tools import parse_d00
from cn_font_render import tile_pixels, load_font, TILE_W, TILE_H

CN_D00 = PROJ / "data" / "cn" / "d00_cn.dat"
EN_PAIRS = PROJ / "data" / "translation_pairs"
OUT_PAIRS = PROJ / "data" / "translation_pairs_cn"
OUT_IMG = OUT_PAIRS / "img"
SEED_MAP = PROJ / "data" / "cn" / "tile_char_map_seed.json"


def load_seed_map() -> dict[int, str]:
    """Tile-code → hanzi map seeded from gameplay-screenshot ground truth."""
    if not SEED_MAP.exists():
        return {}
    blob = json.loads(SEED_MAP.read_text())
    return {int(k): v for k, v in blob.get("map", {}).items()}


def decode_cn_text(tile_codes: list[int], seed: dict[int, str],
                   placeholder: str = "·") -> str:
    """Render a tile-code sequence to readable Chinese using the seed map.
    Unknown tiles become `placeholder`."""
    return "".join(seed.get(t, placeholder) for t in tile_codes)

CTRL_CODES = {
    0xFFFE: "<$FFFE>",
    0xFFFD: "<$FFFD>",
    0xFFFC: "<$FFFC>",
    0xFFFF: "<$FFFF>",
    0xF702: "<$F702>",
    0xF600: "<$F600>",  # has param
}


def parse_entry(entry_bytes: bytes):
    """Walk an entry's bytes; return (tile_codes, ctrl_tokens)."""
    tiles = []
    ctrls = []
    i = 0
    while i < len(entry_bytes) - 1:
        w = struct.unpack_from(">H", entry_bytes, i)[0]
        i += 2
        if w >= 0xF000:
            if w == 0xF600 and i < len(entry_bytes) - 1:
                param = struct.unpack_from(">H", entry_bytes, i)[0]
                ctrls.append(f"<$F600 {param:04X}>")
                i += 2
            elif w in CTRL_CODES:
                ctrls.append(CTRL_CODES[w])
            else:
                ctrls.append(f"<${w:04X}>")
        else:
            tiles.append(w)
    return tiles, ctrls


def render_entry_strip(font: bytes, tile_codes: list[int],
                        scale: int = 4, max_per_row: int = 8,
                        sep: int = 3) -> Image.Image:
    """Grid of tiles with light separators so each tile is visually distinct.
    Wraps every `max_per_row` tiles. Background light grey, glyph black,
    separator white.
    """
    if not tile_codes:
        img = Image.new("L", (TILE_W * scale + sep * 2,
                              TILE_H * scale + sep * 2), 240)
        return img
    n = len(tile_codes)
    rows = (n + max_per_row - 1) // max_per_row
    cols = min(n, max_per_row)
    cell_w = TILE_W * scale + sep
    cell_h = TILE_H * scale + sep
    iw = cols * cell_w + sep
    ih = rows * cell_h + sep
    img = Image.new("L", (iw, ih), 200)  # light grey backdrop
    for i, t in enumerate(tile_codes):
        row = i // max_per_row
        col = i % max_per_row
        x0 = sep + col * cell_w
        y0 = sep + row * cell_h
        # White cell background
        for y in range(TILE_H * scale):
            for x in range(TILE_W * scale):
                img.putpixel((x0 + x, y0 + y), 255)
        if t * 32 + 32 > len(font):
            continue
        px = tile_pixels(font, t)
        for y in range(TILE_H):
            for x in range(TILE_W):
                if px[y][x]:
                    for sy in range(scale):
                        for sx in range(scale):
                            img.putpixel((x0 + x * scale + sx,
                                          y0 + y * scale + sy), 0)
    return img


def process_scenario(scen_idx: int, cn_d00: bytes, font: bytes,
                     emit_images: bool = True, scale: int = 4,
                     seed: dict[int, str] | None = None) -> None:
    if seed is None:
        seed = {}
    secs = parse_d00(cn_d00)
    if scen_idx < 1 or scen_idx > len(secs):
        print(f"  scen{scen_idx:03d}: out of range (D00 has {len(secs)} sections)")
        return
    sec = secs[scen_idx - 1]

    # Load JP/EN pairs (may be missing for some scenarios)
    en_path = EN_PAIRS / f"scen{scen_idx:03d}.json"
    en_pairs = None
    if en_path.exists():
        en_pairs = json.loads(en_path.read_text())

    en_entries = en_pairs["entries"] if en_pairs else []
    cn_count = len(sec.entries)
    en_count = en_pairs["en_count"] if en_pairs else None
    jp_count = en_pairs["jp_count"] if en_pairs else None

    out_entries = []
    img_dir = OUT_IMG / f"scen{scen_idx:03d}"
    if emit_images:
        img_dir.mkdir(parents=True, exist_ok=True)

    for i, entry in enumerate(sec.entries, 1):
        tiles, ctrls = parse_entry(entry)
        # Look up JP/EN for the same index (1-based)
        jp_visible = en_visible = balloon_type = balloon_opcode = None
        tile_budget = jp_codes = en_codes = ctrl_match = None
        if i - 1 < len(en_entries):
            row = en_entries[i - 1]
            jp_visible = row.get("jp_visible")
            en_visible = row.get("en_visible")
            balloon_type = row.get("balloon_type")
            balloon_opcode = row.get("balloon_opcode")
            tile_budget = row.get("tile_budget")
            jp_codes = row.get("jp_codes")
            en_codes = row.get("en_codes")
            ctrl_match = row.get("ctrl_match")

        ctrl_match_cn_jp = (ctrls == jp_codes + ["<$FFFE>"]) if jp_codes is not None else None
        # Actually JP entries' jp_codes excludes the trailing <$FFFE>/<$FFFF>; just compare loosely
        # We'll provide the raw lists and let the consumer compare.

        img_rel = None
        if emit_images:
            img_path = img_dir / f"entry_{i:03d}.png"
            render_entry_strip(font, tiles, scale=scale).save(img_path)
            img_rel = str(img_path.relative_to(PROJ))

        cn_visible = decode_cn_text(tiles, seed) if seed else None
        cn_known = sum(1 for t in tiles if t in seed) if seed else 0
        cn_coverage = (cn_known / len(tiles)) if tiles else None

        out_entries.append({
            "index": i,
            "balloon_type": balloon_type,
            "balloon_opcode": balloon_opcode,
            "tile_budget": tile_budget,
            "jp_visible": jp_visible,
            "en_visible": en_visible,
            "cn_visible": cn_visible,
            "cn_coverage": round(cn_coverage, 2) if cn_coverage is not None else None,
            "jp_codes": jp_codes,
            "en_codes": en_codes,
            "cn_tile_codes": tiles,
            "cn_tile_count": len(tiles),
            "cn_codes": ctrls,
            "cn_byte_length": len(entry),
            "cn_is_empty": (len(tiles) == 0),
            "cn_image": img_rel,
        })

    out = {
        "scenario": scen_idx,
        "jp_count": jp_count,
        "en_count": en_count,
        "cn_count": cn_count,
        "delta_cn_jp": (cn_count - jp_count) if jp_count is not None else None,
        "entries": out_entries,
    }
    OUT_PAIRS.mkdir(parents=True, exist_ok=True)
    out_path = OUT_PAIRS / f"scen{scen_idx:03d}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"  scen{scen_idx:03d}: cn={cn_count} jp={jp_count} en={en_count}  → {out_path.name}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scen", type=int, nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--no-images", action="store_true")
    p.add_argument("--scale", type=int, default=4)
    args = p.parse_args()

    if not args.scen and not args.all:
        p.error("specify scen ids or --all")

    cn = CN_D00.read_bytes()
    font = load_font()
    secs = parse_d00(cn)
    seed = load_seed_map()
    print(f"CN D00: {len(secs)} sections; CN font: {len(font)} bytes; "
          f"seed map: {len(seed)} tile→char")

    targets = list(range(1, len(secs) + 1)) if args.all else args.scen
    for s in targets:
        process_scenario(s, cn, font, emit_images=not args.no_images,
                         scale=args.scale, seed=seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
