#!/usr/bin/env python3
"""build_fntsys12.py — generate scripts/en/fntsys12E.txt (class descriptions).

Same rigid grid + no-auto-wrap box as fntsys13 (see build_fntsys13.py and
archive/docs/20260607_fntsys13_handoff.md), different counts:

    class k (k=1..87) -> records [(k-1)*4 .. (k-1)*4+3]   (4 records each)
    entry 88          -> record  [348]                    (1 blank record)

Box = 18 tiles, encoded half-width (BIGRAM_PAIRS includes pair 11). The EN was
originally translated 1:1 per JP record (full sentences) and overflows the box;
this builder re-wraps each class's prose (from metadata/en/fntsys12_src.txt) to
<=18 encoded tiles, matching the JP record count.

Reuses the source format and wrap/measure helpers from build_fntsys13.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import build_fntsys13 as b13   # noqa: E402  (tile_width, wrap, parse_source, BLANK)

MAX_TILES = 18
TOTAL_RECORDS = 349
ITEM_RECORD_COUNTS = [4] * 87 + [1]   # class 1..87 = 4 recs, entry 88 = 1 blank

SRC = PROJ / "metadata" / "en" / "fntsys12_src.txt"   # build-input metadata (not shipped)
OUT = PROJ / "scripts" / "en" / "fntsys12E.txt"


def build_records():
    items = b13.parse_source(SRC.read_text(encoding="utf-8"))
    if len(items) != len(ITEM_RECORD_COUNTS):
        raise SystemExit(
            f"source has {len(items)} blocks, expected {len(ITEM_RECORD_COUNTS)}")
    out, overflows = [], []
    for idx, (item, want) in enumerate(zip(items, ITEM_RECORD_COUNTS), start=1):
        prose = " ".join(item["prose"]).strip()
        stat = item["stat"]
        recs = []
        prose_budget = want - 1 if stat is not None else want
        if prose:
            recs.extend(b13.wrap(prose, prose_budget))
        if len(recs) > prose_budget:
            overflows.append((idx, item["head"], len(recs), prose_budget, prose))
        if stat is not None:
            recs.append(stat if stat else b13.BLANK)
        while len(recs) < want:
            recs.append(b13.BLANK)
        out.extend(recs[:want])
    return out, overflows


def main():
    records, overflows = build_records()
    if overflows:
        print(f"=== {len(overflows)} classes OVER budget (tighten these) ===")
        for idx, head, got, budget, _ in overflows:
            print(f"  {head}: {got} lines > {budget}")
        print()
    if len(records) == TOTAL_RECORDS and not overflows:
        OUT.write_text("".join(r + "<$FFFF>\n" for r in records), encoding="utf-8")
        widths = [b13.tile_width(r) for r in records]
        print(f"wrote {OUT} ({len(records)} records)")
        print(f"max tile width: {max(widths)} (limit {MAX_TILES})")
    else:
        print(f"NOT written: {len(records)} records, {len(overflows)} overflows")


if __name__ == "__main__":
    main()
