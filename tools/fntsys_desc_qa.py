#!/usr/bin/env python3
"""fntsys_desc_qa.py — layout-QA for the FNT_SYS string sections.

Sibling of tools/layout_qa (which analyzes scen/plot dialogue). This one analyzes
the PRODUCTION scripts (scripts/en/fntsys{n}E.txt) per a LAYOUT PROFILE for each
section type, so we can ensure every entry uses its line budget well — no overflow
AND no excess of thin/under-filled lines.

Budget is DERIVED from the JP records at runtime: each section's box width = the
max JP record tile-width (each JP full-width glyph == one EN bigram tile). Where
many records pile on that max, it is a HARD box; where widths are scattered, the
max is the longest observed string (advisory).

Profiles:
  description — fntsys12 (class/troop), fntsys13 (item). 4-record grid; the LAST
                record is the stat/effect tail (exempt from under-fill); prose
                fills lines 0..2. Budget 18 tiles.
  name        — fntsys9/10/11. One record per entry; budget ~7-8 (nameplate).
  label       — fntsys1-8,15. One record per entry; overflow check vs JP max.

EXCLUDED: fntsys14 (name-entry keyboard) is a key grid, NOT prose — it is never
classified or touched here; it has its own dedicated scope/session.

Issue codes (severity):
  line_budget_exceeded (error)  — a line > budget → runs off the box.
  low_line_usage       (warning)— description prose under-fills the box (enrich
                                   candidate; tail/blank exempt). Enrich, never
                                   compress (memory feedback_enrich_dont_compress).

Status: ERROR if any line overflows; PLAYABLE if it fits but under-fills;
POLISHED if it fits and fills well.

Usage:
    python3 tools/fntsys_desc_qa.py analyze [--print]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from build_fntsys13 import tile_width, BLANK  # noqa: E402

SCHEMA_VERSION = "0.2.0"
REPORTS = PROJ / "reports"
DEFAULT_REPORT = REPORTS / "fntsys-desc-qa-report.json"
DEFAULT_WORKLIST = REPORTS / "fntsys-desc-qa-worklist.md"
EXEMPT_CONFIG = PROJ / "config" / "fntsys-desc-qa-exempt.json"
JP_BASELINE = PROJ / "cache" / "fnt_sys_jp.bin"

LOW_USAGE_RATIO = 0.66          # below this avg prose fill -> under-filled
BOX_CONFIDENCE_RATIO = 0.10     # >=10% of records at the max -> hard budget

ISSUE_CODES = ("line_budget_exceeded", "low_line_usage")
STATUS_VALUES = ("ERROR", "PLAYABLE", "POLISHED")

# pair (0-indexed) -> layout profile. Budget derived from JP at runtime.
# SCOPE: only the DESCRIPTION boxes (units/classes + items/equipment). The menu
# labels (fntsys1-8,15) are variable-layout — deferred. The nameplate/name
# sections (fntsys9-11) have a budget but are out of this focus. The keyboard
# (fntsys14) is a key grid — never classified here (own scope).
PROFILES = {
    9:  {"id": "fntsys10", "kind": "name", "name": "item/equipment names (label budget)"},
    11: {"id": "fntsys12", "kind": "description", "name": "class/troop/unit descriptions",
         "grid": 4, "tail": 1},
    12: {"id": "fntsys13", "kind": "description", "name": "item/equipment descriptions",
         "grid": 4, "tail": 1},
}
EN_PATTERN = "scripts/en/fntsys{n}E.txt"


def jp_budgets() -> dict:
    """Per-pair box budget from the JP baseline: {pair: {budget, hard, mode}}."""
    from fnt_sys_tools import parse_fnt_sys
    import collections
    fs = parse_fnt_sys(JP_BASELINE.read_bytes())
    out = {}
    for i, p in enumerate(fs.pairs):
        ws = [(len(r) - 2) // 2 for r in p.records]   # stored recs end with FFFF
        if not ws:
            out[i] = {"budget": 0, "hard": False, "mode": 0}
            continue
        mx = max(ws)
        at_max = sum(1 for w in ws if w == mx) / len(ws)
        out[i] = {"budget": mx, "hard": at_max >= BOX_CONFIDENCE_RATIO,
                  "mode": collections.Counter(ws).most_common(1)[0][0]}
    return out


def _read_records(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.append(line[:-len("<$FFFF>")] if line.endswith("<$FFFF>") else line)
    return out


def _is_blank(rec: str) -> bool:
    return rec.strip() == "" or rec.strip() == BLANK.strip()


def classify_entry(index: int, lines: list[str], budget: int, kind: str) -> dict:
    """Classify one entry (a description grid of records, or a single label)."""
    issues: list[dict] = []
    widths = [tile_width(l) for l in lines]
    n = len(lines)
    is_desc = (kind == "description")
    line_reports = []
    prose_fills = []
    for i, (line, w) in enumerate(zip(lines, widths)):
        is_tail = is_desc and (i == n - 1)         # stat/effect tail of the grid
        is_blank = _is_blank(line)
        lkind = "blank" if is_blank else ("tail" if is_tail else "prose")
        if budget and w > budget:
            issues.append({"code": "line_budget_exceeded", "severity": "error",
                           "detail": {"line": i, "tiles": w, "budget": budget,
                                      "text": line}})
        if lkind == "prose" and not is_blank and budget:
            prose_fills.append(w / budget)
        line_reports.append({"line": i, "kind": lkind, "tiles": w, "text": line})

    avg_fill = sum(prose_fills) / len(prose_fills) if prose_fills else 0.0
    # under-fill only meaningful for the multi-line description boxes
    if is_desc and prose_fills:
        prose_budget = n - 1            # last record reserved for the stat tail
        prose_used = len(prose_fills)
        if avg_fill < LOW_USAGE_RATIO or prose_used < prose_budget:
            issues.append({"code": "low_line_usage", "severity": "warning",
                           "detail": {"avgFill": round(avg_fill, 3),
                                      "proseLines": prose_used,
                                      "proseBudget": prose_budget}})

    if any(i["severity"] == "error" for i in issues):
        status = "ERROR"
    elif any(i["severity"] == "warning" for i in issues):
        status = "PLAYABLE"
    else:
        status = "POLISHED"
    return {"index": index, "status": status,
            "tileUsage": {"maxLine": max(widths) if widths else 0,
                          "avgFill": round(avg_fill, 3),
                          "linesUsed": n, "budget": [budget, n]},
            "lines": line_reports, "issues": issues}


def analyze_section(pair_idx: int, prof: dict, binfo: dict, exempt: dict):
    path = EN_PATTERN.format(n=pair_idx + 1)
    full = PROJ / path
    if not full.exists():
        return None
    recs = _read_records(full)
    budget = binfo["budget"]
    kind = prof["kind"]
    entries = []
    if kind == "description":
        grid, tail = prof.get("grid", 4), prof.get("tail", 1)
        nitems = (len(recs) - tail) // grid if len(recs) >= tail else 0
        pos = 0
        for k in range(1, nitems + 1):
            entries.append(classify_entry(k, recs[pos:pos + grid], budget, kind))
            pos += grid
        while pos < len(recs):            # trailing single-record remainder
            entries.append(classify_entry(len(entries) + 1,
                                           recs[pos:pos + tail], budget, kind))
            pos += tail
    else:
        for k, rec in enumerate(recs, 1):
            entries.append(classify_entry(k, [rec], budget, kind))

    by_status = {s: 0 for s in STATUS_VALUES}
    by_issue = {c: 0 for c in ISSUE_CODES}
    for e in entries:
        ex = exempt.get(prof["id"], {}).get(str(e["index"]))
        if ex and e["status"] != "ERROR":
            e["status"] = "POLISHED"
            e["exempt"] = ex
        by_status[e["status"]] += 1
        for iss in e["issues"]:
            if iss["code"] in by_issue:
                by_issue[iss["code"]] += 1
    n = len(entries)
    return {"id": prof["id"], "path": path, "name": prof["name"], "kind": kind,
            "budget": budget, "budgetHard": binfo["hard"], "entryCount": n,
            "byStatus": by_status, "byIssue": by_issue,
            "readinessRate": round((by_status["PLAYABLE"] + by_status["POLISHED"]) / n, 4) if n else 1.0,
            "polishRate": round(by_status["POLISHED"] / n, 4) if n else 1.0,
            "entries": entries}


def build_report(now=None) -> dict:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    exempt = json.loads(EXEMPT_CONFIG.read_text(encoding="utf-8")) if EXEMPT_CONFIG.exists() else {}
    budgets = jp_budgets()
    sections = []
    for pair_idx, prof in PROFILES.items():
        sec = analyze_section(pair_idx, prof, budgets[pair_idx], exempt)
        if sec:
            sections.append(sec)
    total = sum(s["entryCount"] for s in sections)
    by_status = {s: 0 for s in STATUS_VALUES}
    by_issue = {c: 0 for c in ISSUE_CODES}
    for sec in sections:
        for s in STATUS_VALUES:
            by_status[s] += sec["byStatus"][s]
        for c in ISSUE_CODES:
            by_issue[c] += sec["byIssue"][c]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now.isoformat(),
        "summary": {
            "total": total, "byStatus": by_status, "byIssue": by_issue,
            "readinessRate": round((by_status["PLAYABLE"] + by_status["POLISHED"]) / total, 4) if total else 1.0,
            "polishRate": round(by_status["POLISHED"] / total, 4) if total else 1.0,
        },
        "sections": sections,
    }


def write_worklist(report: dict, path: Path) -> None:
    out = ["# FNT_SYS layout QA — worklist", "",
           f"Generated {report['generatedAt']}", ""]
    for sec in report["sections"]:
        errs = [e for e in sec["entries"] if e["status"] == "ERROR"]
        play = [e for e in sec["entries"] if e["status"] == "PLAYABLE"]
        hard = "hard" if sec["budgetHard"] else "advisory"
        out.append(f"## {sec['id']} — {sec['name']} · {sec['kind']} · "
                   f"budget {sec['budget']} ({hard}) · {sec['entryCount']} entries")
        out.append(f"ERROR {sec['byStatus']['ERROR']} · "
                   f"PLAYABLE {sec['byStatus']['PLAYABLE']} · "
                   f"POLISHED {sec['byStatus']['POLISHED']}")
        out.append("")
        if errs:
            out.append("### 🔴 ERROR — overflow (must fit)")
            for e in errs:
                over = [f"line {i['detail']['line']}={i['detail']['tiles']}>{i['detail']['budget']}t"
                        for i in e["issues"] if i["code"] == "line_budget_exceeded"]
                out.append(f"- entry {e['index']}: {', '.join(over)}")
            out.append("")
        if play:
            out.append(f"### 🟡 PLAYABLE — under-filled (enrich): "
                       f"{len(play)} entries — {[e['index'] for e in play][:40]}")
            out.append("")
    path.write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("analyze", help="write report + worklist")
    pa.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    pa.add_argument("--worklist", type=Path, default=DEFAULT_WORKLIST)
    pa.add_argument("--print", action="store_true", dest="do_print")
    args = ap.parse_args()

    report = build_report()
    REPORTS.mkdir(exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    write_worklist(report, args.worklist)
    s = report["summary"]
    print(f"wrote {args.output}")
    print(f"wrote {args.worklist}")
    if args.do_print:
        print(f"\ntotal {s['total']} · ERROR {s['byStatus']['ERROR']} · "
              f"PLAYABLE {s['byStatus']['PLAYABLE']} · POLISHED {s['byStatus']['POLISHED']}")
        for sec in report["sections"]:
            print(f"  {sec['id']:<9} {sec['kind']:<11} budget {sec['budget']:>2} "
                  f"{'hard' if sec['budgetHard'] else 'adv '} | "
                  f"ERR {sec['byStatus']['ERROR']:>3} "
                  f"PLAY {sec['byStatus']['PLAYABLE']:>3} "
                  f"POL {sec['byStatus']['POLISHED']:>3}")


if __name__ == "__main__":
    main()
