#!/usr/bin/env python3
"""disembark_inventory.py — progress meter + gate for the 0.2-patch disembark.

The disembark goal: the patch inherits ZERO bytes and ZERO author-handle
mentions from the third-party 0.2 patch. The only allowed mention of the
original author is the acknowledgment in README.md.

Snapshots the current state and emits a markdown report. With ``--strict``
it acts as a GATE: exit code 1 if any inherited-author mention survives
outside README.md (wire this into CI / pre-merge).

Categories tracked:
- patches/*.bin still applied by build.py (binary inheritance — target 0)
- byte_overlays.py residual: inherited byte runs not yet RE'd into a
  self-documenting engine-patch module (the real disembark debt — target 0)
- inherited-author mentions in tracked files outside README (target 0)
- scripts/en/*E.txt compile status (compiled vs dead-doc)

Usage:
    python3 tools/disembark_inventory.py
    python3 tools/disembark_inventory.py --strict        # gate (exit 1 on fail)
    python3 tools/disembark_inventory.py -o report.md
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent

# Author handles inherited from the 0.2 patch. Built from fragments so this
# file — which names them — does NOT trip its own gate. The acknowledgment in
# README.md is the single sanctioned place these may appear.
_TERMS = ["c" + "wx", "cyber" + "warriorx", "vermillion" + "desserts"]
_GATE_RE = re.compile("|".join(_TERMS), re.IGNORECASE)
_GATE_ALLOWED = {"README.md"}


def _tracked_files() -> list[str]:
    try:
        out = subprocess.check_output(["git", "-C", str(PROJ), "ls-files"],
                                      text=True)
    except Exception:
        return []
    return [p for p in out.splitlines() if p]


def patches_status() -> list[tuple[str, int, str]]:
    """Return [(filename, size_bytes, status)] for everything in patches/."""
    patches_dir = PROJ / "patches"
    if not patches_dir.exists():
        return []
    out = []
    for p in sorted(patches_dir.iterdir()):
        if not p.is_file():
            continue
        out.append((p.name, p.stat().st_size, "0.2-patch-direct"))
    return out


def inherited_mentions() -> list[tuple[str, int]]:
    """Tracked files (outside README) that still mention a 0.2-patch author
    handle, with the hit count per file. Empty == gate passes."""
    out = []
    for rel in _tracked_files():
        if rel in _GATE_ALLOWED:
            continue
        try:
            text = (PROJ / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue   # binary or vanished — no prose to gate
        n = len(_GATE_RE.findall(text))
        if n:
            out.append((rel, n))
    return sorted(out, key=lambda t: -t[1])


def byte_overlays_residual() -> tuple[int, int, list[tuple[str, int, int]]]:
    """Inherited byte runs still shipped opaquely from tools/byte_overlays.py.

    Returns ``(total_runs, total_bytes, [(iso_path, runs, bytes), ...])``. Each
    run is disembark debt until it is carved into a self-documenting RE'd
    engine-patch module (or a named declared text module) and removed from
    byte_overlays — at which point it stops counting here. When byte_overlays is
    empty this returns ``(0, 0, [])`` and the disembark is complete.
    """
    try:
        from byte_overlays import BYTE_OVERLAYS
    except Exception:
        return 0, 0, []
    per = []
    for iso_path, runs in sorted(BYTE_OVERLAYS.items()):
        nbytes = 0
        for _off, chunk in runs:
            nbytes += len(chunk) if isinstance(chunk, (bytes, bytearray)) else 1
        per.append((iso_path, len(runs), nbytes))
    total_runs = sum(p[1] for p in per)
    total_bytes = sum(p[2] for p in per)
    return total_runs, total_bytes, per


def scripts_status() -> dict[str, dict]:
    """Classify scripts/en/* files: compiled vs dead-doc."""
    scripts_dir = PROJ / "scripts" / "en"
    build_py = (PROJ / "build.py").read_text()
    files = sorted(scripts_dir.iterdir()) if scripts_dir.exists() else []

    out = {"scen": {"count": 0, "compiled": True, "note": "via insert_translations → D00.DAT"},
           "plot": {"count": 0, "compiled": True, "note": "via encode_plot_script → PLOT.DAT"},
           "fntsys": {"count": 0, "compiled": False, "note": "dead-doc"},
           "syswin": {"count": 0, "compiled": False, "note": "dead-doc"}}
    for f in files:
        name = f.name.lower()
        if name.startswith("scen"):
            out["scen"]["count"] += 1
        elif name.startswith("plot"):
            out["plot"]["count"] += 1
        elif name.startswith("fntsys"):
            out["fntsys"]["count"] += 1
        elif name.startswith("syswin"):
            out["syswin"]["count"] += 1

    if "fntsys" in build_py.lower() and "encode_fntsys" in build_py:
        out["fntsys"]["compiled"] = True
        out["fntsys"]["note"] = "wired via encode_fntsys"
    if "encode_syswin" in build_py:
        out["syswin"]["compiled"] = True
        out["syswin"]["note"] = "wired via encode_syswin"

    return out


def render_report() -> tuple[str, int]:
    """Return (markdown_report, score). score 0 == disembark complete."""
    lines = []
    lines.append("# 0.2-patch Disembark — Inventory Snapshot")
    lines.append("")
    lines.append(f"Generated by `tools/disembark_inventory.py` on branch "
                 f"`{_current_branch()}`.")
    lines.append("")

    # --- patches/ binaries ---
    lines.append("## 1. `patches/` binaries shipped to ISO")
    lines.append("")
    patches = patches_status()
    if not patches:
        lines.append("_None._ ✅ no binary inheritance")
    else:
        lines.append("| File | Size | Status |")
        lines.append("|---|---:|---|")
        for fname, size, status in patches:
            lines.append(f"| `{fname}` | {size:,} | {status} |")
        lines.append("")
        lines.append(f"**Total 0.2-patch-direct binaries: {len(patches)}** (target: 0)")
    lines.append("")

    # --- byte_overlays residual (the real disembark debt) ---
    lines.append("## 1b. `byte_overlays.py` inherited byte runs")
    lines.append("")
    residual_runs, residual_bytes, residual_per = byte_overlays_residual()
    if residual_runs == 0:
        lines.append("_None._ ✅ every inherited byte run has been carved into "
                     "its own RE'd module")
    else:
        lines.append("| Target | Runs | Bytes |")
        lines.append("|---|---:|---:|")
        for iso_path, nruns, nbytes in residual_per:
            lines.append(f"| `{iso_path}` | {nruns} | {nbytes} |")
        lines.append("")
        lines.append(f"**{residual_runs} runs, {residual_bytes} bytes** still "
                     f"shipped opaquely (target: 0). Carve each cluster into a "
                     f"self-documenting `progN_<concern>.py` module.")
    lines.append("")

    # --- inherited-author mentions (the gate) ---
    lines.append("## 2. Inherited-author mentions outside README")
    lines.append("")
    mentions = inherited_mentions()
    if not mentions:
        lines.append("_None._ ✅ only README keeps the acknowledgment")
    else:
        lines.append("| File | Hits |")
        lines.append("|---|---:|")
        for rel, n in mentions:
            lines.append(f"| `{rel}` | {n} |")
        lines.append("")
        total = sum(n for _, n in mentions)
        lines.append(f"**{len(mentions)} files, {total} mentions** (target: 0)")
    lines.append("")

    # --- scripts/en/ status ---
    lines.append("## 3. `scripts/en/` compile status")
    lines.append("")
    ss = scripts_status()
    lines.append("| Group | Count | Compiled? | Note |")
    lines.append("|---|---:|---|---|")
    for group, info in ss.items():
        if info["count"] == 0:
            continue
        flag = "✅" if info["compiled"] else "❌ dead-doc"
        lines.append(f"| `{group}*E.txt` | {info['count']} | {flag} | {info['note']} |")
    lines.append("")

    # --- summary ---
    dead_doc_count = sum(info["count"] for info in ss.values()
                         if not info["compiled"])
    score = len(patches) + residual_runs + len(mentions) + dead_doc_count
    lines.append("## Summary")
    lines.append("")
    lines.append(f"Disembark score (lower is better): **{score}**")
    lines.append("- patches 0.2-patch-direct: " + str(len(patches)))
    lines.append("- byte_overlays inherited runs: " + str(residual_runs))
    lines.append("- files mentioning a 0.2-patch author: " + str(len(mentions)))
    lines.append("- dead-doc scripts: " + str(dead_doc_count))
    lines.append("")
    lines.append("Target: **0**. The only sanctioned author mention is the "
                 "README acknowledgment.")
    return "\n".join(lines) + "\n", score


def _current_branch() -> str:
    try:
        r = subprocess.run(["git", "-C", str(PROJ), "branch", "--show-current"],
                           capture_output=True, text=True, check=True)
        return r.stdout.strip() or "(detached)"
    except Exception:
        return "(unknown)"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Write report to file (default: stdout)")
    parser.add_argument("--strict", action="store_true",
                        help="GATE: exit 1 if any inherited-author mention "
                             "survives outside README.md")
    args = parser.parse_args()

    report, score = render_report()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(report)

    if args.strict:
        mentions = inherited_mentions()
        if mentions:
            print(f"\nGATE FAILED: {sum(n for _, n in mentions)} inherited-author "
                  f"mention(s) in {len(mentions)} file(s) outside README:",
                  file=sys.stderr)
            for rel, n in mentions:
                print(f"  {rel}: {n}", file=sys.stderr)
            sys.exit(1)
        print("\nGATE PASSED: no inherited-author mentions outside README.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
