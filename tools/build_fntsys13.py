#!/usr/bin/env python3
"""build_fntsys13.py — generate scripts/en/fntsys13E.txt (item descriptions).

fntsys13 (FNT_SYS.BIN pair 12) is the in-game item-description text. Its layout
is a RIGID 4-records-per-item grid (see archive/docs/20260607_fntsys13_handoff.md):

    item k (k=1..175) -> records [(k-1)*4 .. (k-1)*4+3]   (4 records each)
    item 176          -> record  [700]                    (1 blank record)

Each item occupies exactly the same number of records as the JP source, so the
total stays 701 and whatever index the engine uses (fixed stride or offset table)
remains valid. Records map 1:1 to RENDERED SCREEN LINES — the description box does
NOT auto-wrap (user-confirmed). The box is 18 tiles wide; fntsys13 is encoded with
the half-width BIGRAM map (BIGRAM_PAIRS={12}), so each line holds ~34-36 EN chars.

This builder reads a human-authored source (metadata/en/fntsys13_src.txt), word-
wraps each item's prose to <= MAX_TILES encoded tiles per line using the REAL
encoder (no rewrite-then-measure), appends the stat/effect line, pads to the JP
record count, and writes the 701-record fntsys13E.txt.

Source format (one block per described item, blocks separated by blank lines):

    # <fntsys10_line_number>  <item name, for reference only>
    <prose, free-flowing; may span multiple physical lines — joined with spaces>
    @stat <stat/effect line, verbatim one record; omit for no-stat items>
    @blank                      # optional: force a trailing blank record

The builder fills lines 0..2 with wrapped prose and the LAST record with the stat
(JP always puts the stat/effect/blank on the 4th line, record mod 4 == 3). If
prose + stat would exceed 4 records, it errors so the translation can be tightened.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from d00_tools import encode_text_to_entry           # noqa: E402
from font_tools import CHAR_TILE_MAP, FNTSYS_BIGRAM_TILE_MAP as BIGRAM_TILE_MAP  # noqa: E402
from fnt_sys_tools import _build_fntsys_char_map        # noqa: E402

MAX_TILES = 18          # description box width, in tiles
TOTAL_RECORDS = 701
ITEM_RECORD_COUNTS = [4] * 175 + [1]   # item 1..175 = 4 recs, item 176 = 1 rec
BLANK = "　"        # full-width space used by JP for pad records

SRC = PROJ / "metadata" / "en" / "fntsys13_src.txt"   # build-input metadata (not shipped)
OUT = PROJ / "scripts" / "en" / "fntsys13E.txt"

_CHAR_MAP = _build_fntsys_char_map()


def tile_width(text: str) -> int:
    """Encoded tile count of one record's visible text (bigram/half-width)."""
    rec = encode_text_to_entry(text, _CHAR_MAP, bigram_tile_map=BIGRAM_TILE_MAP)
    # encode_text_to_entry returns NO FFFF terminator; every BE16 is a rendered
    # tile (spaces are packed into bigram tiles too). Width = emitted tiles.
    return len(rec) // 2


def wrap(prose: str, max_lines: int) -> list[str]:
    """Greedy word-wrap to <= MAX_TILES encoded tiles per line (no line cap)."""
    words = prose.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = w if not cur else cur + " " + w
        if tile_width(cand) <= MAX_TILES:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
            if tile_width(cur) > MAX_TILES:
                raise ValueError(f"word does not fit in {MAX_TILES} tiles: {w!r}")
    if cur:
        lines.append(cur)
    return lines


def _is_item_header(line: str) -> bool:
    # item header is "# <fntsys10 line number> ..."; other "#" lines are comments
    return bool(re.match(r"#\s+\d", line))


def parse_source(text: str) -> list[dict]:
    items: list[dict] = []
    cur: dict | None = None
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if _is_item_header(line):
            if cur is not None:
                items.append(cur)
            cur = {"prose": [], "stat": None, "blank": False, "head": line}
        elif line.startswith("#"):
            continue   # comment line (header block / notes)
        elif line.startswith("@stat"):
            cur["stat"] = line[len("@stat"):].strip()
        elif line.startswith("@blank"):
            cur["blank"] = True
        elif line.strip() == "":
            continue
        else:
            cur["prose"].append(line.strip())
    if cur is not None:
        items.append(cur)
    return items


def build_records() -> list[str]:
    items = parse_source(SRC.read_text(encoding="utf-8"))
    if len(items) != len(ITEM_RECORD_COUNTS):
        raise SystemExit(
            f"source has {len(items)} item blocks, expected {len(ITEM_RECORD_COUNTS)}"
        )
    out: list[str] = []
    overflows: list[tuple[int, str, int, int, str]] = []
    for idx, (item, want) in enumerate(zip(items, ITEM_RECORD_COUNTS), start=1):
        prose = " ".join(item["prose"]).strip()
        stat = item["stat"]
        recs: list[str] = []
        # reserve the final record for the stat line when present
        prose_lines_budget = want - 1 if stat is not None else want
        if prose:
            recs.extend(wrap(prose, prose_lines_budget))
        n_prose = len(recs)
        if n_prose > prose_lines_budget:
            overflows.append((idx, item["head"], n_prose, prose_lines_budget, prose))
        if stat is not None:
            if stat:
                if tile_width(stat) > MAX_TILES:
                    overflows.append((idx, item["head"] + " [STAT]",
                                      tile_width(stat), MAX_TILES, stat))
                recs.append(stat)
            else:
                recs.append(BLANK)
        # pad with blank records to the JP record count
        while len(recs) < want:
            recs.append(BLANK)
        # truncate to want so the file is still buildable for inspection
        recs = recs[:want]
        out.extend(recs)
    return out, overflows


def main() -> None:
    records, overflows = build_records()
    if overflows:
        print(f"=== {len(overflows)} items OVER budget (tighten these) ===")
        for idx, head, got, budget, txt in overflows:
            print(f"  {head}: {got} lines/tiles > {budget}")
        print()
    if len(records) == TOTAL_RECORDS and not overflows:
        OUT.write_text("".join(r + "<$FFFF>\n" for r in records), encoding="utf-8")
        widths = [tile_width(r) for r in records]
        print(f"wrote {OUT} ({len(records)} records)")
        print(f"max tile width: {max(widths)} (limit {MAX_TILES})")
    else:
        print(f"NOT written: {len(records)} records, {len(overflows)} overflows")


if __name__ == "__main__":
    main()
