#!/usr/bin/env python3
"""jp_tile_crack.py — recover unmapped JP tiles via the CyberWarriorX dump.

The JP decode table (``data/jp/tile_map.json``) is incomplete: some tile-words
appear in real text entries with no mapping, decoding as ``<$0xxx>`` holes.
This tool recovers them by *known-plaintext alignment* against CyberWarriorX's
full Saturn JP dump shipped with the Akari Dawn PC project — the SAME game
text, so a context lookup yields the exact character.

For each hole, it takes the already-decoded characters on both sides (L, R)
within the line and searches the matching AD scenario/menu file's normalised
stream for ``L(.)R``, longest anchor first. Votes are aggregated per tile.

The CWX dump carries a few of its own font mis-decodes (e.g. 籠→滝, 憑→懣), so
ALWAYS sanity-read the proposed reading against the word it forms and the tile
glyph before committing — this tool proposes, it does not decide.

Usage::

    python3 tools/jp_tile_crack.py                 # report candidates
    python3 tools/jp_tile_crack.py --ad DIR        # custom AD script/jp dir

Glyph cross-check helper::

    python3 tools/jp_tile_crack.py --glyph 0x0639  # ASCII-render a tile
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TILE_MAP = PROJECT / "data" / "jp" / "tile_map.json"
FONT = PROJECT / "data" / "jp" / "font_jp.bin"
SCRIPTS = PROJECT / "scripts" / "jp"
DEFAULT_AD = Path.home() / "romhack" / "langrisser3pc" / "script" / "jp"
TOK = re.compile(r"<\$([0-9A-F]{4})>")


def ad_stream(path: str) -> str | None:
    """Decode an AD .sjs file (Shift-JIS) to a whitespace/marker-free stream."""
    raw = open(path, "rb").read()
    for enc in ("cp932", "shift_jis"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        return re.sub(r"\s", "", re.sub(r"<\$[0-9A-Fa-f]{4}>", "", text))
    return None


def ad_path(ad_dir: Path, our_name: str) -> str | None:
    if our_name.startswith("scen"):
        n = int(re.search(r"scen(\d+)J", our_name).group(1))
        return str(ad_dir / f"scen{n}.sjs")
    if our_name.startswith("fntsys"):
        n = int(re.search(r"fntsys(\d+)J", our_name).group(1))
        return str(ad_dir / f"fntsys{n}.sjs")
    if our_name.startswith("plot"):
        return str(ad_dir / "plot.sjs")
    return None


def render_glyph(tile: int) -> str:
    data = open(FONT, "rb").read()
    o = tile * 32
    out = []
    for i in range(16):
        bits = (data[o + i * 2] << 8) | data[o + i * 2 + 1]
        out.append("".join("#" if bits & (1 << (15 - c)) else "." for c in range(16)))
    return "\n".join(out)


def crack(ad_dir: Path):
    tile_map = {int(k): v for k, v in json.loads(TILE_MAP.read_text()).items()}
    votes: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    no_match: collections.Counter = collections.Counter()
    total: collections.Counter = collections.Counter()

    for fn in sorted(glob.glob(str(SCRIPTS / "*J.txt"))):
        base = os.path.basename(fn)
        adp = ad_path(ad_dir, base)
        stream = ad_stream(adp) if adp and os.path.exists(adp) else None
        for line in open(fn, encoding="utf-8"):
            line = line.rstrip("\n")
            toks, i = [], 0
            for mm in TOK.finditer(line):
                toks.extend(("CH", c) for c in line[i:mm.start()])
                w = int(mm.group(1), 16)
                toks.append(("CTRL", w) if w >= 0xF000 else ("TILE", w))
                i = mm.end()
            toks.extend(("CH", c) for c in line[i:])
            for j in range(len(toks) - 1):  # F600 param is not text
                if toks[j] == ("CTRL", 0xF600):
                    toks[j + 1] = ("CTRL", toks[j + 1][1])
            rt = [("CH", tile_map[str(v)]) if k == "TILE" and str(v) in tile_map
                  else (k, v) for k, v in toks]
            for idx, (k, v) in enumerate(rt):
                if k != "TILE":
                    continue
                total[v] += 1
                if stream is None:
                    no_match[v] += 1
                    continue

                def grab(rng):
                    s = []
                    for j in rng:
                        kk, vv = rt[j]
                        if kk == "CH" and not re.match(r"\s", vv):
                            s.append(vv)
                        else:
                            break
                    return s

                L = "".join(reversed(grab(range(idx - 1, -1, -1))))
                R = "".join(grab(range(idx + 1, len(rt))))
                hit = None
                for tl in range(min(10, len(L)), -1, -1):
                    for tr in range(min(10, len(R)), -1, -1):
                        if tl + tr < 2:
                            continue
                        lft, rgt = (L[-tl:] if tl else ""), (R[:tr] if tr else "")
                        found = set(mo.group(1) for mo in
                                    re.finditer(re.escape(lft) + r"(.)" + re.escape(rgt), stream))
                        if len(found) == 1:
                            hit = next(iter(found))
                            break
                    if hit:
                        break
                if hit:
                    votes[v][hit] += 1
                else:
                    no_match[v] += 1

    solved, conflict = {}, {}
    for w, c in votes.items():
        top = c.most_common()
        if len(top) == 1 or top[0][1] >= top[1][1] + 2:
            solved[w] = top[0][0]
        else:
            conflict[w] = dict(c)
    unresolved = [w for w in total if w not in votes]
    return solved, conflict, unresolved, total


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ad", type=Path, default=DEFAULT_AD, help="AD script/jp dir")
    ap.add_argument("--glyph", help="render one tile (hex like 0x0639) and exit")
    args = ap.parse_args(argv)

    if args.glyph:
        t = int(args.glyph, 16)
        print(f"tile 0x{t:04X} ({t}):\n{render_glyph(t)}")
        return 0

    if not args.ad.exists():
        print(f"ERROR: AD dump dir not found: {args.ad}", file=sys.stderr)
        return 1

    solved, conflict, unresolved, total = crack(args.ad)
    n_hole = sum(total.values())
    print(f"{len(total)} unmapped tiles, {n_hole} occurrences")
    print(f"SOLVED {len(solved)} | CONFLICT {len(conflict)} | NO-MATCH {len(unresolved)}")
    print("\n# Proposed (VERIFY each reading against word + glyph before committing):")
    for w in sorted(solved):
        print(f"  0x{w:04X}: {solved[w]!r},   # x{total[w]}")
    if conflict:
        print("\n# CONFLICT (multiple candidates):")
        for w in sorted(conflict):
            print(f"  0x{w:04X}: {conflict[w]}  x{total[w]}")
    if unresolved:
        print("\n# NO AD MATCH (terrain/menu not in dump — use glyph + word):")
        for w in sorted(unresolved):
            print(f"  0x{w:04X}  x{total[w]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
