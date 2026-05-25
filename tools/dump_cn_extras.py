#!/usr/bin/env python3
"""dump_cn_extras.py — extract CN-modified strings from FNT_SYS, SYSWIN,
DEMO, A0LANG, PROG_7. Reads JP and CN ISOs directly (no need for
pre-extracted JP files).

Output: scripts/cn/<name>_cn.txt for each file with text content.

Strategy per file:
  - Same JP/CN size + small diff (SYSWIN, DEMO, A0LANG, PROG_7):
    diff-region scan with FFFF-delimited entry walk, same as dump_cn_prog4.
  - Different size (FNT_SYS):
    full dump of all FFFF-delimited entries — JP layout differs, so
    diff-filtering doesn't apply.

PROG_7 is included but typically yields no text (only ~7 byte diff).

Usage:
    python3 tools/dump_cn_extras.py [--jp-iso PATH] [--cn-iso PATH]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
from iso_tools import build_file_index, extract_file_data

SEED = PROJ / "data" / "cn" / "tile_char_map_seed.json"
FONT = PROJ / "data" / "cn" / "font_cn_decoded.bin"
OUT_DIR = PROJ / "scripts" / "cn"

JP_DEFAULT = Path(
    "/home/ralf/Jogos/emulacao/romsets/sega-saturn/cue-bin/"
    "Langrisser III (Japan)/Langrisser III (Japan) (3M) (Track 01).bin"
)
CN_DEFAULT = Path(
    "/home/ralf/Jogos/emulacao/tools/梦幻模拟战3[简][意志之路]/LANGRISSER_3.mdf"
)

# (iso_path, out_name, mode)
# mode: "diff" — same-size files, dump only diff regions
#       "full" — different size, dump all FFFF-delimited entries
TARGETS = [
    ("LANG/FNT_SYS.BIN", "fnt_sys", "full"),
    ("LANG/BATTLE/SYSWIN.BIN", "syswin", "diff"),
    ("LANG/DEMO.BIN", "demo", "diff"),
    ("A0LANG.BIN", "a0lang", "diff"),
    ("LANG/PROG_7.BIN", "prog_7", "diff"),
]

CTRL = {
    0xFFFE: "<$FFFE>",
    0xFFFD: "<$FFFD>",
    0xFFFC: "<$FFFC>",
    0xF702: "<$F702>",
}
KNOWN_HIGH = set(CTRL) | {0xFFFF, 0xF600}

GAP_MERGE = 32
SCAN_PAD = 64
MAX_ENTRY_WORDS = 400          # FNT_SYS has long entries; relaxed vs PROG_4
MIN_TEXT_RATIO = 0.6           # full-dump mode tolerates more punctuation
HEADER_SKIP_BYTES = 614        # FNT_SYS: first FFFF at byte 614 (font header)


def load_seed() -> dict[int, str]:
    return {int(k): v for k, v in json.loads(SEED.read_text())["map"].items()}


def render_entry(words: list[int], seed: dict[int, str], max_tile_id: int) -> tuple[str, list[int], bool]:
    toks: list[str] = []
    unmapped: list[int] = []
    is_text = True
    i = 0
    n = len(words)
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


def find_entry_start(cn: bytes, start: int) -> int:
    s = start & ~1
    lower = max(0, s - 256)
    pos = s - 2
    while pos >= lower:
        if cn[pos] == 0xFF and cn[pos + 1] == 0xFF:
            return pos + 2
        pos -= 2
    return s


def walk_diff_region(
    cn: bytes,
    rs: int,
    re: int,
    seed: dict[int, str],
    max_tile_id: int,
) -> list[tuple[int, list[int], str, list[int]]]:
    start = find_entry_start(cn, rs)
    limit = min(len(cn), re + SCAN_PAD)
    out = []
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
            cur = []
            cur_off = pos
            if pos >= re:
                break
        else:
            cur.append(w)
            if len(cur) > MAX_ENTRY_WORDS:
                break
    return out


def walk_full(
    cn: bytes,
    seed: dict[int, str],
    max_tile_id: int,
    skip_bytes: int = 0,
) -> list[tuple[int, list[int], str, list[int]]]:
    """Walk all FFFF-delimited entries from skip_bytes to end-of-file."""
    out = []
    pos = skip_bytes & ~1
    # Advance past any leading FFFF terminator at skip point
    while pos < len(cn) - 1 and cn[pos] == 0xFF and cn[pos + 1] == 0xFF:
        pos += 2
    cur: list[int] = []
    cur_off = pos
    while pos < len(cn) - 1:
        w = (cn[pos] << 8) | cn[pos + 1]
        pos += 2
        if w == 0xFFFF:
            if cur:
                text, unm, is_text = render_entry(cur, seed, max_tile_id)
                if is_text and 0 < len(cur) <= MAX_ENTRY_WORDS:
                    text_words = sum(1 for x in cur if x < 0xF000)
                    if text_words / len(cur) >= MIN_TEXT_RATIO:
                        out.append((cur_off, list(cur), text, unm))
            cur = []
            cur_off = pos
        else:
            cur.append(w)
            if len(cur) > MAX_ENTRY_WORDS:
                # bail out of malformed run, resync at next FFFF
                cur = []
                cur_off = pos
    return out


def dump_diff(
    name: str,
    jp: bytes,
    cn: bytes,
    seed: dict[int, str],
    max_tile_id: int,
) -> str:
    regions = diff_regions(jp, cn)
    body: list[str] = []
    text_regions = 0
    entries = 0
    seen: set[int] = set()
    total_tiles = 0
    total_unmapped = 0
    for rs, re in regions:
        ents = walk_diff_region(cn, rs, re, seed, max_tile_id)
        novel = [e for e in ents if e[0] not in seen]
        if not novel:
            continue
        text_regions += 1
        body.append(f"\n--- diff region 0x{rs:06x}..0x{re:06x} ({re - rs} bytes) ---")
        for off, words, text, unm in novel:
            seen.add(off)
            body.append(f'@0x{off:06x} ({len(words) * 2:3d}): "{text}"')
            entries += 1
            total_tiles += sum(1 for x in words if x < 0xF000)
            total_unmapped += len(unm)
    coverage = ((total_tiles - total_unmapped) / total_tiles * 100) if total_tiles else 0.0
    header = [
        f"Langrisser III CN dump — {name.upper()}",
        f"# JP size: {len(jp)} CN size: {len(cn)} (same)",
        f"# diff regions: {len(regions)}; with text: {text_regions}; entries: {entries}",
        f"# tiles: {total_tiles}; unmapped: {total_unmapped} ({coverage:.1f}% mapped)",
    ]
    return "\n".join(header) + "\n" + "\n".join(body) + "\n"


def dump_full(
    name: str,
    jp: bytes,
    cn: bytes,
    seed: dict[int, str],
    max_tile_id: int,
    skip: int,
) -> str:
    ents = walk_full(cn, seed, max_tile_id, skip_bytes=skip)
    body: list[str] = []
    total_tiles = 0
    total_unmapped = 0
    for off, words, text, unm in ents:
        body.append(f'@0x{off:06x} ({len(words) * 2:3d}): "{text}"')
        total_tiles += sum(1 for x in words if x < 0xF000)
        total_unmapped += len(unm)
    coverage = ((total_tiles - total_unmapped) / total_tiles * 100) if total_tiles else 0.0
    header = [
        f"Langrisser III CN dump — {name.upper()}",
        f"# JP size: {len(jp)}; CN size: {len(cn)} (differ — full CN dump)",
        f"# Skipping first {skip} bytes (non-text header).",
        f"# entries: {len(ents)}; tiles: {total_tiles};"
        f" unmapped: {total_unmapped} ({coverage:.1f}% mapped)",
    ]
    return "\n".join(header) + "\n" + "\n".join(body) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jp-iso", type=Path, default=JP_DEFAULT)
    ap.add_argument("--cn-iso", type=Path, default=CN_DEFAULT)
    args = ap.parse_args()

    if not args.jp_iso.exists():
        print(f"ERROR: JP ISO not found: {args.jp_iso}", file=sys.stderr)
        return 1
    if not args.cn_iso.exists():
        print(f"ERROR: CN ISO not found: {args.cn_iso}", file=sys.stderr)
        return 1

    seed = load_seed()
    max_tile_id = FONT.stat().st_size // 32
    print(f"seed: {len(seed)} mappings; font tiles: {max_tile_id}")

    jp_blob = args.jp_iso.read_bytes()
    cn_blob = args.cn_iso.read_bytes()
    jp_idx = build_file_index(jp_blob)
    cn_idx = build_file_index(cn_blob)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for iso_path, out_name, mode in TARGETS:
        je = jp_idx.get(iso_path)
        ce = cn_idx.get(iso_path)
        if not (je and ce):
            print(f"  {iso_path}: missing (JP={bool(je)}, CN={bool(ce)})")
            continue
        jp_b = extract_file_data(jp_blob, je.extent, je.size)
        cn_b = extract_file_data(cn_blob, ce.extent, ce.size)
        if mode == "diff" and len(jp_b) != len(cn_b):
            print(f"  {iso_path}: size mismatch — switching to full mode")
            mode = "full"
        if mode == "diff":
            text = dump_diff(out_name, jp_b, cn_b, seed, max_tile_id)
        else:
            skip = HEADER_SKIP_BYTES if out_name == "fnt_sys" else 0
            text = dump_full(out_name, jp_b, cn_b, seed, max_tile_id, skip)
        out_file = OUT_DIR / f"{out_name}_cn.txt"
        out_file.write_text(text, encoding="utf-8")
        # parse header line for summary
        first_line = text.split("\n", 1)[0]
        last_header = text.split("\n")[3] if len(text.split("\n")) > 3 else ""
        print(f"  → {out_file.relative_to(PROJ)}  ({mode})")
        print(f"    {last_header.lstrip('# ')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
