#!/usr/bin/env python3
"""dump_cn_scripts.py — bulk-decode CN D00.DAT and PLOT.DAT into scripts/cn/.

For every section of CN D00.DAT, emits scripts/cn/scenNNN_cn.txt with each
entry rendered as interleaved hanzi + control codes. Tiles missing from the
seed map render as [?NNNN] (4-digit decimal tile id) so they can be looked up
directly in data/cn/font_cn_decoded.bin.

Also emits scripts/cn/plot_cn.txt for the 35-block PLOT.DAT, and
scripts/cn/_unmapped_ranking.txt listing entries ordered by count of
unmapped tiles (worst first) — that's the queue for individual hanzi
disambiguation.

Usage:
    python3 tools/dump_cn_scripts.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
from d00_tools import parse_d00

CN_D00 = PROJ / "data" / "cn" / "d00_cn.dat"
CN_PLOT = PROJ / "data" / "cn" / "plot_cn.dat"
SEED_MAP = PROJ / "data" / "cn" / "tile_char_map_seed.json"
OUT_DIR = PROJ / "scripts" / "cn"

CTRL_CODES = {
    0xFFFE: "<$FFFE>",
    0xFFFD: "<$FFFD>",
    0xFFFC: "<$FFFC>",
    0xFFFF: "<$FFFF>",
    0xF702: "<$F702>",
}


def load_seed() -> dict[int, str]:
    blob = json.loads(SEED_MAP.read_text())
    return {int(k): v for k, v in blob.get("map", {}).items()}


def render_entry(entry_bytes: bytes, seed: dict[int, str]) -> tuple[str, list[int]]:
    """Render one entry as a token stream. Returns (text, unmapped_tile_ids)."""
    tokens: list[str] = []
    unmapped: list[int] = []
    i = 0
    n = len(entry_bytes)
    while i < n - 1:
        w = struct.unpack_from(">H", entry_bytes, i)[0]
        i += 2
        if w >= 0xF000:
            if w == 0xF600 and i < n - 1:
                param = struct.unpack_from(">H", entry_bytes, i)[0]
                tokens.append(f"<$F600 {param:04X}>")
                i += 2
            elif w in CTRL_CODES:
                tokens.append(CTRL_CODES[w])
            else:
                tokens.append(f"<${w:04X}>")
        else:
            ch = seed.get(w)
            if ch is None:
                tokens.append(f"[?{w:04d}]")
                unmapped.append(w)
            else:
                tokens.append(ch)
    return "".join(tokens), unmapped


def parse_plot_blocks(data: bytes) -> list[bytes]:
    """Return one byte-blob per PLOT.DAT block, header (8B) stripped."""
    file_size = struct.unpack(">I", data[:4])[0]
    offsets = list(struct.unpack(">35H", data[4:74])) + [file_size]
    return [data[offsets[i] + 8: offsets[i + 1]] for i in range(35)]


def render_plot_block(body: bytes, seed: dict[int, str]) -> tuple[str, list[int]]:
    """Render a single PLOT block. \n at every 0xFFFD; entry ends at 0xFFFE."""
    tokens: list[str] = []
    unmapped: list[int] = []
    n_words = len(body) // 2
    codes = struct.unpack(f">{n_words}H", body[:n_words * 2])
    for w in codes:
        if w == 0xFFFD:
            tokens.append("\n")
        elif w == 0xFFFC:
            tokens.append("<$FFFC>")
        elif w == 0xFFFE:
            tokens.append("<$FFFE>")
            break
        elif w >= 0xF000:
            tokens.append(f"<${w:04X}>")
        else:
            ch = seed.get(w)
            if ch is None:
                tokens.append(f"[?{w:04d}]")
                unmapped.append(w)
            else:
                tokens.append(ch)
    return "".join(tokens), unmapped


def main() -> int:
    seed = load_seed()
    cn_data = CN_D00.read_bytes()
    secs = parse_d00(cn_data)
    print(f"seed: {len(seed)} mappings; CN D00: {len(secs)} sections")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # (kind, scen_or_block, entry_idx, unmapped_count, unmapped_tile_ids, text_excerpt)
    ranking: list[tuple[str, int, int, int, list[int], str]] = []

    total_entries = 0
    total_unmapped_tiles = 0
    total_tiles = 0

    # --- D00 sections ---
    for s_idx, sec in enumerate(secs, 1):
        lines = [f"Langrisser III CN dump — scen{s_idx:03d}",
                 f"# {len(sec.entries)} entries from data/cn/d00_cn.dat",
                 f"# Unmapped tiles render as [?NNNN] (decimal tile id;"
                 f" look up in data/cn/font_cn_decoded.bin at offset NNNN*32).",
                 ""]
        for e_idx, ebytes in enumerate(sec.entries, 1):
            text, unmapped = render_entry(ebytes, seed)
            lines.append(text)
            # Per-entry stats
            n_tiles = sum(1 for w in struct.unpack(
                f">{len(ebytes)//2}H", ebytes[:len(ebytes)//2*2]) if w < 0xF000)
            total_entries += 1
            total_tiles += n_tiles
            total_unmapped_tiles += len(unmapped)
            if unmapped:
                ranking.append((
                    "scen", s_idx, e_idx, len(unmapped), unmapped,
                    text[:80].replace("\n", " "),
                ))
        out = OUT_DIR / f"scen{s_idx:03d}_cn.txt"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # --- PLOT.DAT ---
    if CN_PLOT.exists():
        plot_data = CN_PLOT.read_bytes()
        blocks = parse_plot_blocks(plot_data)
        plines = [f"Langrisser III CN dump — PLOT.DAT",
                  f"# 35 chapter-recap blocks from data/cn/plot_cn.dat",
                  ""]
        for b_idx, body in enumerate(blocks):
            text, unmapped = render_plot_block(body, seed)
            plines.append(f"--- BLOCK {b_idx:02d} (SCENARIO-{b_idx+1:02d}) ---")
            plines.append(text)
            plines.append("")
            n_tiles = sum(1 for w in struct.unpack(
                f">{len(body)//2}H", body[:len(body)//2*2])
                if w < 0xF000 and w != 0xFFFE)
            total_entries += 1
            total_tiles += n_tiles
            total_unmapped_tiles += len(unmapped)
            if unmapped:
                ranking.append((
                    "plot", b_idx, 0, len(unmapped), unmapped,
                    text[:80].replace("\n", " "),
                ))
        (OUT_DIR / "plot_cn.txt").write_text(
            "\n".join(plines), encoding="utf-8")

    # --- ranking ---
    ranking.sort(key=lambda r: (-r[3], r[0], r[1], r[2]))
    rank_lines = [
        "# CN entries ranked by count of unmapped tiles (worst first).",
        "# Columns: rank | kind | scen/block | entry_idx | unmapped_count |"
        " distinct_unmapped | text_excerpt",
        "# Look up tile ids in data/cn/font_cn_decoded.bin (1bpp 16x16,"
        " stride 32B, tile_offset = id * 32).",
        f"# total entries: {total_entries}; total tiles: {total_tiles};"
        f" unmapped tiles: {total_unmapped_tiles}"
        f" ({total_unmapped_tiles/total_tiles*100:.1f}%).",
        "",
    ]
    for i, (kind, scen, eidx, count, tids, excerpt) in enumerate(ranking, 1):
        distinct = sorted(set(tids))
        ident = (f"scen{scen:03d}#{eidx:03d}" if kind == "scen"
                 else f"plot#{scen:02d}")
        rank_lines.append(
            f"{i:5d}  {ident}  unmapped={count:3d}"
            f"  distinct={len(distinct):3d}  ids={distinct[:12]}"
            f"{'...' if len(distinct) > 12 else ''}  text: {excerpt!r}"
        )
    (OUT_DIR / "_unmapped_ranking.txt").write_text(
        "\n".join(rank_lines) + "\n", encoding="utf-8")

    print(f"wrote {len(secs)} scen files + plot_cn.txt + _unmapped_ranking.txt")
    print(f"total entries: {total_entries};  total tiles: {total_tiles};"
          f"  unmapped: {total_unmapped_tiles}"
          f" ({total_unmapped_tiles/total_tiles*100:.1f}%)")
    print(f"entries with any unmapped tile: {len(ranking)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
