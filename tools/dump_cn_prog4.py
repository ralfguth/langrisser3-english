#!/usr/bin/env python3
"""dump_cn_prog4.py — extract FFFF-delimited CN-modified strings from PROG_4.BIN.

Strategy: locate byte-level diff regions JP↔CN (gap-merged at 32 bytes), then
within each region consume tile-id words (BE) terminated by 0xFFFF, rendered
via data/cn/tile_char_map_seed.json. Out-of-range tile-ids (>= max_tile_id)
flag the region as non-text and abort it; this filters code/data tweaks
(jump-table offsets, MP costs etc.) that look superficially text-like.

Output: scripts/cn/prog_4_cn.txt — one entry per line, grouped by region.

Usage:
    python3 tools/dump_cn_prog4.py
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
SEED = PROJ / "data" / "cn" / "tile_char_map_seed.json"
FONT = PROJ / "data" / "cn" / "font_cn_decoded.bin"
JP = PROJ / "data" / "jp" / "prog" / "prog_4.bin"
CN = PROJ / "data" / "cn" / "prog" / "prog_4.bin"
OUT = PROJ / "scripts" / "cn" / "prog_4_cn.txt"

CTRL = {
    0xFFFE: "<$FFFE>",
    0xFFFD: "<$FFFD>",
    0xFFFC: "<$FFFC>",
    0xF702: "<$F702>",
}
KNOWN_HIGH = set(CTRL) | {0xFFFF, 0xF600}

GAP_MERGE = 32          # diff bytes within this gap merge into one region
SCAN_PAD = 64           # extend forward past region end to find FFFF terminator
MAX_ENTRY_WORDS = 200


def load_seed() -> dict[int, str]:
    return {int(k): v for k, v in json.loads(SEED.read_text())["map"].items()}


def diff_regions(jp: bytes, cn: bytes) -> list[tuple[int, int]]:
    diffs = [i for i in range(min(len(jp), len(cn))) if jp[i] != cn[i]]
    if not diffs:
        return []
    regs: list[tuple[int, int]] = []
    s = diffs[0]
    p = s
    for d in diffs[1:]:
        if d - p < GAP_MERGE:
            p = d
        else:
            regs.append((s, p + 1))
            s = d
            p = d
    regs.append((s, p + 1))
    return regs


def render_entry(words: list[int], seed: dict[int, str], max_tile_id: int) -> tuple[str, list[int], bool]:
    """Render an entry word-list (without trailing 0xFFFF).

    Returns (text, unmapped_ids, is_text). is_text is False if the entry
    contains an unknown high-bit code OR a tile_id beyond the font, which
    means we accidentally walked into code/data instead of a string.
    """
    toks: list[str] = []
    unmapped: list[int] = []
    i = 0
    n = len(words)
    is_text = True
    while i < n:
        w = words[i]
        i += 1
        if w == 0xF600 and i < n:
            param = words[i]
            i += 1
            toks.append(f"<$F600 {param:04X}>")
        elif w in CTRL:
            toks.append(CTRL[w])
        elif w >= 0xF000:
            toks.append(f"<${w:04X}>")
            if w not in KNOWN_HIGH:
                is_text = False
        else:
            if w >= max_tile_id:
                is_text = False
            ch = seed.get(w)
            if ch is None:
                toks.append(f"[?{w:04d}]")
                unmapped.append(w)
            else:
                toks.append(ch)
    return "".join(toks), unmapped, is_text


def find_entry_start(cn: bytes, region_start: int) -> int:
    """Walk backwards from region_start to the byte after the previous 0xFFFF
    (so a small mid-string diff still yields the whole string). Aligned even.
    Capped at 256 bytes back.
    """
    s = region_start & ~1  # align even
    lower = max(0, s - 256)
    pos = s - 2
    while pos >= lower:
        if cn[pos] == 0xFF and cn[pos + 1] == 0xFF:
            return pos + 2
        pos -= 2
    return s


def walk_region(
    cn: bytes,
    region: tuple[int, int],
    seed: dict[int, str],
    max_tile_id: int,
) -> list[tuple[int, list[int], str, list[int]]]:
    """Yield (offset, words, text, unmapped) entries for a diff region."""
    rs, re = region
    start = find_entry_start(cn, rs)
    limit = min(len(cn), re + SCAN_PAD)
    out: list[tuple[int, list[int], str, list[int]]] = []
    pos = start
    cur: list[int] = []
    cur_off = pos
    while pos < limit - 1:
        w = (cn[pos] << 8) | cn[pos + 1]
        pos += 2
        if w == 0xFFFF:
            if cur:
                text, unm, is_text = render_entry(cur, seed, max_tile_id)
                if is_text and len(cur) <= MAX_ENTRY_WORDS:
                    out.append((cur_off, list(cur), text, unm))
                # whether or not this entry was text, reset and continue —
                # adjacent entries (e.g. spell table) deserve their own try.
            cur = []
            cur_off = pos
            # Stop once we've passed the diff region end and just terminated.
            if pos >= re:
                break
        else:
            cur.append(w)
            if len(cur) > MAX_ENTRY_WORDS:
                # No terminator found in a sane window → this region isn't text.
                break
    return out


def main() -> int:
    seed = load_seed()
    max_tile_id = FONT.stat().st_size // 32  # 2253 currently
    jp = JP.read_bytes()
    cn = CN.read_bytes()
    if len(jp) != len(cn):
        print(f"warn: JP/CN PROG_4 size differs ({len(jp)} vs {len(cn)})")

    regions = diff_regions(jp, cn)

    body: list[str] = []
    text_regions = 0
    entries_emitted = 0
    seen_offsets: set[int] = set()
    total_tiles = 0
    total_unmapped = 0

    for rs, re in regions:
        ents = walk_region(cn, (rs, re), seed, max_tile_id)
        # dedupe — adjacent diff regions can overlap a single shared entry
        novel = [e for e in ents if e[0] not in seen_offsets]
        if not novel:
            continue
        text_regions += 1
        body.append(f"\n--- diff region 0x{rs:06x}..0x{re:06x} ({re - rs} bytes) ---")
        for off, words, text, unm in novel:
            seen_offsets.add(off)
            body.append(f'@0x{off:06x} ({len(words) * 2:3d}): "{text}"')
            entries_emitted += 1
            total_tiles += sum(1 for w in words if w < 0xF000)
            total_unmapped += len(unm)

    coverage = ((total_tiles - total_unmapped) / total_tiles * 100) if total_tiles else 0.0

    header = [
        "Langrisser III CN dump — LANG/PROG_4.BIN",
        "# CN-modified FFFF-delimited entries from data/cn/prog/prog_4.bin",
        "# vs data/jp/prog/prog_4.bin. Unmapped tiles render as [?NNNN]",
        "# (decimal id; bitmap at data/cn/font_cn_decoded.bin offset id*32).",
        "# Format: @0xOFFSET (NN bytes): \"<rendered text>\"",
        f"# diff regions: {len(regions)}; regions with text: {text_regions};"
        f" entries: {entries_emitted}",
        f"# tiles: {total_tiles}; unmapped: {total_unmapped}"
        f" ({coverage:.1f}% mapped)",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(header) + "\n" + "\n".join(body) + "\n", encoding="utf-8")

    print(f"wrote {OUT.relative_to(PROJ)}")
    print(f"  {len(regions)} diff regions, {text_regions} contain text,"
          f" {entries_emitted} entries")
    print(f"  tiles {total_tiles}; unmapped {total_unmapped}"
          f" ({coverage:.1f}% mapped)")

    # Spell-table sanity check (per resume-prompt acceptance criterion):
    # 0x007f78..0x00808c should yield 34 spell entries.
    spell_offs = [o for o in seen_offsets if 0x007E58 <= o < 0x00808C]
    print(f"  spell-table entries (0x7e58..0x808c): {len(spell_offs)}"
          f" (expected 34)")
    if len(spell_offs) != 34:
        print("  WARN: spell-table count mismatch")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
