#!/usr/bin/env python3
"""cn_render_unmapped.py — for the top-N highest-leverage unmapped CN tiles,
print 1bpp 16x16 ASCII bitmap + 5 context lines (entries where this tile is
the sole unmap, with surrounding text fully decoded).

Pipeline target: read the bitmap visually, identify the hanzi, append to
tools/cn_seed_bitmap.json, re-run cn_seed_screenshots.py + dump_cn_scripts.py.

Usage:
    python3 tools/cn_render_unmapped.py [--top N] [--ctx K]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
from d00_tools import parse_d00

FONT = PROJ / "data" / "cn" / "font_cn_decoded.bin"
SEED = PROJ / "data" / "cn" / "tile_char_map_seed.json"
BITMAP_OUT = PROJ / "tools" / "cn_seed_bitmap.json"
D00 = PROJ / "data" / "cn" / "d00_cn.dat"
PLOT = PROJ / "data" / "cn" / "plot_cn.dat"

CTRL = {0xFFFE: "/", 0xFFFD: "/", 0xFFFC: "/", 0xFFFF: ""}


def render_tile(font: bytes, tid: int) -> list[str]:
    buf = font[tid * 32:(tid + 1) * 32]
    rows = []
    for r in range(16):
        bits = (buf[r * 2] << 8) | buf[r * 2 + 1]
        rows.append("".join("█" if (bits >> (15 - c)) & 1 else "·"
                            for c in range(16)))
    return rows


def walk_tiles(words: tuple[int, ...]) -> list[int]:
    out = []
    i = 0
    while i < len(words):
        w = words[i]
        if w == 0xF600:
            i += 2
            continue
        if w >= 0xF000:
            i += 1
            continue
        out.append(w)
        i += 1
    return out


def render_text(words: tuple[int, ...], seed: dict[int, str],
                target: int) -> str:
    out = []
    i = 0
    while i < len(words):
        w = words[i]
        if w == 0xF600:
            i += 2
            out.append("«N»")
            continue
        if w in (0xFFFE, 0xFFFF):
            break
        if w == 0xFFFD:
            out.append(" / ")
            i += 1
            continue
        if w == 0xFFFC:
            out.append(" / ")
            i += 1
            continue
        if w >= 0xF000:
            i += 1
            continue
        if w == target:
            out.append(f"❰{w}❱")
        else:
            out.append(seed.get(w, f"[?{w}]"))
        i += 1
    return "".join(out)


def all_entries() -> list[tuple[str, int, int, tuple[int, ...]]]:
    """Yield (kind, scen_or_block, entry_idx, word_tuple)."""
    out = []
    d00 = D00.read_bytes()
    for s, sec in enumerate(parse_d00(d00), 1):
        for e_idx, ebytes in enumerate(sec.entries, 1):
            words = struct.unpack(f">{len(ebytes)//2}H",
                                  ebytes[:len(ebytes)//2*2])
            out.append(("scen", s, e_idx, words))
    plot = PLOT.read_bytes()
    file_size = struct.unpack(">I", plot[:4])[0]
    offsets = list(struct.unpack(">35H", plot[4:74])) + [file_size]
    for b in range(35):
        body = plot[offsets[b] + 8: offsets[b + 1]]
        words = struct.unpack(f">{len(body)//2}H", body[:len(body)//2*2])
        out.append(("plot", b, 0, words))
    return out


def load_pair(kind: str, scen: int, e_idx: int) -> tuple[str, str]:
    """Return (jp, en) for a scen/entry pair, or ('', '') if not found."""
    if kind != "scen":
        return ("", "")
    p = PROJ / "data" / "translation_pairs_cn" / f"scen{scen:03d}.json"
    if not p.exists():
        return ("", "")
    try:
        d = json.loads(p.read_text())
        e = next((x for x in d["entries"] if x["index"] == e_idx), None)
        if e is None:
            return ("", "")
        return (e.get("jp_visible") or "", e.get("en_visible") or "")
    except Exception:
        return ("", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10,
                    help="how many unmapped tiles to render (default: 10)")
    ap.add_argument("--ctx", type=int, default=5,
                    help="context examples per tile (default: 5)")
    ap.add_argument("--skip", type=int, default=0,
                    help="skip the first N highest-leverage tiles")
    args = ap.parse_args()

    seed = {int(k): v for k, v in
            json.loads(SEED.read_text())["map"].items()}
    font = FONT.read_bytes()

    entries = all_entries()
    # For each entry, list its unmapped tile occurrences.
    unmaps_per_entry = []
    for kind, s, e, words in entries:
        tiles = walk_tiles(words)
        u = [t for t in tiles if t not in seed]
        if u:
            unmaps_per_entry.append((kind, s, e, words, u))

    # Single-unmap rank: most-frequent tile id appearing as the sole unmap.
    single_freq = Counter()
    for _, _, _, _, u in unmaps_per_entry:
        if len(set(u)) == 1:
            single_freq[u[0]] += 1

    top = single_freq.most_common(args.skip + args.top)[args.skip:]
    if not top:
        print("no single-unmap tiles left — switch to multi-unmap strategy")
        return 0

    bm_existing = {}
    if BITMAP_OUT.exists():
        bm_existing = {int(k): v for k, v in
                        json.loads(BITMAP_OUT.read_text())
                        .get("map", {}).items()}

    print(f"# top {len(top)} unmapped tiles by single-unmap-entry count")
    print(f"# seed: {len(seed)} tiles; bitmap_seed: {len(bm_existing)} tiles\n")

    for tid, n_single in top:
        if tid in bm_existing:
            print(f"--- tile #{tid}: ALREADY in bitmap seed as {bm_existing[tid]!r}, skipping\n")
            continue
        print(f"=== tile #{tid}  ({n_single} single-unmap entries) ===")
        for line in render_tile(font, tid):
            print(line)

        # Pick K diverse single-unmap context examples
        ctx = [e for e in unmaps_per_entry
               if len(set(e[4])) == 1 and e[4][0] == tid]
        for kind, s, e, words, _ in ctx[:args.ctx]:
            ident = (f"scen{s:03d}#{e:03d}" if kind == "scen"
                     else f"plot#{s:02d}")
            txt = render_text(words, seed, tid)
            jp, en = load_pair(kind, s, e)
            print(f"  {ident}: CN={txt[:120]}")
            if jp:
                print(f"           JP={jp[:80]}")
            if en:
                print(f"           EN={en[:80]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
