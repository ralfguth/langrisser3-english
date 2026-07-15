#!/usr/bin/env python3
"""bigram_histogram.py — tally which bigrams the script TEXT needs.

Stage 2 of the font/encoder refactor. The font's text glyphs are half-width
bigrams; this raises the occurrence of every bigram the text would require, so we
know exactly what the font must contain.

ALGORITHM (per spec — NOT the current encoder's pairing):
  * Work on CLEAN text: codes that HIDE a common bigram (e.g. <$05DD>="PC",
    <$05E0>="Sc") are DECODED back to their letters so the bigram is counted.
  * A control code (and the 8 special dedicated glyphs: ✻ … 囗｜―＼／ ADV BAK END
    【 】) is a BOUNDARY — pairing never crosses it. A letter next to a boundary
    becomes a standalone ['letter',' '] bigram (never 'r<').
  * Within each text segment, pair raw 2-chars-at-a-time; spaces ARE part of
    bigrams. Odd trailing char -> (char,' ').
  Example: "Sophia, keeper of the southern" ->
    So ph ia ", " ke ep er " o" "f " th "e " so ut he rn

Usage: python3 tools/bigram_histogram.py [scripts/en]
Output: archive/docs/font_states/bigram_histogram.{txt,csv}
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import font_tools as ft   # noqa: E402

CODE_RE = re.compile(r"<\$([0-9A-Fa-f]{4,})>")
NAME_RE = re.compile(r"\[diehardt's name\]", re.IGNORECASE)
BOUNDARY = "\x01"

# The 8 special dedicated glyphs (tile ids) — boundaries, not bigrams.
SPECIAL_TILES = {0x01E9, 0x038A, 0x014A, 0x014B, 0x014C, 0x014D, 0x014E,
                 0x05D0, 0x05D1, 0x05D2, 0x035C, 0x035D}
# Literal chars for the same special glyphs — also boundaries.
# '•' (objective bullet) and '*' render as their own standalone tile, never a
# half-width bigram (user 2026-06-25: "* e • são sempre standalone").
SPECIAL_CHARS = set("✻…*•【】")
# Full-width / zenkaku chars (SCENARIO title letters/digits ＳＣＥＮＡＲＩＯ, the
# full-width space, the title dashes ‐ ―) render as ONE centered tile each, by
# design — never half-width bigrams. They are boundaries too.
FULLWIDTH_RE = re.compile(r"[　‐-―！-｠]")


def _common_bigram_decode() -> dict[int, str]:
    """tile id -> letters, for codes that hide a COMMON bigram (so the bigram is
    counted, not the code). Built from the 0.2 patch-area Eagle tiles, minus specials."""
    out: dict[int, str] = {}
    for t, spec in ft._MENU_GLYPHS.items():
        if t in SPECIAL_TILES:
            continue
        if spec[0] == "bigram":
            out[t] = spec[1] + spec[2]
        elif spec[0] == "left":
            out[t] = spec[1]          # half-width single letter
        # 'center' (keyboard zenkaku lowercase) left as boundary
    csvp = PROJ / "tests" / "tile_audit_truth.csv"
    if csvp.exists():
        for line in csvp.read_text().splitlines():
            p = line.split("|")
            if len(p) >= 2 and p[0].strip().isdigit() and "centralizado" not in line:
                t = int(p[0])
                if t in SPECIAL_TILES or t in out:
                    continue
                tok = p[1].strip().strip("[]")
                if 1 <= len(tok) <= 2:
                    out[t] = tok
    return out


def clean_to_segments(line: str, decode: dict[int, str]) -> list[str]:
    """Return text segments (boundaries removed). Common-bigram codes decoded
    to letters; control codes / specials become boundaries."""
    line = NAME_RE.sub(BOUNDARY, line)
    line = line.replace("...", "…")

    def repl(m):
        t = int(m.group(1)[:4], 16)
        if len(m.group(1)) == 4 and t in decode:
            return decode[t]
        return BOUNDARY                      # any other code = boundary
    line = CODE_RE.sub(repl, line)
    for ch in SPECIAL_CHARS:
        line = line.replace(ch, BOUNDARY)
    line = FULLWIDTH_RE.sub(BOUNDARY, line)      # zenkaku title chars = standalone
    return [seg for seg in line.split(BOUNDARY) if seg]


def pairs_of(segment: str):
    """Raw 2-chars-at-a-time; trailing single -> (char,' '). Spaces kept."""
    j = 0
    n = len(segment)
    while j < n:
        if j + 1 < n:
            yield (segment[j], segment[j + 1])
            j += 2
        else:
            yield (segment[j], " ")
            j += 1


def main():
    script_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJ / "scripts" / "en"
    decode = _common_bigram_decode()
    hist = Counter()
    files = 0
    for p in sorted(script_dir.glob("*.txt")):
        # only FINAL scripts the build embeds — skip working/source files
        # (_-prefixed scans, *_src.txt build sources with # comments / -> notes)
        if p.name.startswith("_") or p.stem.endswith("_src"):
            continue
        files += 1
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            for seg in clean_to_segments(line, decode):
                for pair in pairs_of(seg):
                    if pair == (" ", " "):
                        continue
                    hist[pair] += 1

    # coverage vs current font (informational only)
    def have(p):
        return p in ft.BIGRAM_TILE_MAP or (p[1] == " " and p[0] in ft.CHAR_TILE_MAP)
    missing = {p: n for p, n in hist.items() if not have(p)}

    out_dir = PROJ / "archive" / "docs" / "font_states"
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "bigram_histogram.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["left", "right", "count", "in_font"])
        for (l, r), n in hist.most_common():
            w.writerow([l, r, n, "yes" if have((l, r)) else "NO"])

    txt = [
        f"scripts: {script_dir.relative_to(PROJ)} ({files} files)",
        f"distinct bigrams needed: {len(hist)}",
        f"  present in current font: {len(hist) - len(missing)}",
        f"  MISSING from font: {len(missing)}",
        f"total bigram occurrences: {sum(hist.values())}",
        "",
        "=== MISSING bigrams (needed by text, no glyph yet), by count ===",
    ]
    for (l, r), n in sorted(missing.items(), key=lambda kv: -kv[1]):
        txt.append(f"  ({l!r:>4},{r!r:>4})  x{n}")
    txt += ["", "=== top 50 needed bigrams overall ==="]
    for (l, r), n in hist.most_common(50):
        txt.append(f"  ({l!r:>4},{r!r:>4})  x{n}"
                   + ("" if have((l, r)) else "   <-- MISSING"))
    (out_dir / "bigram_histogram.txt").write_text("\n".join(txt) + "\n",
                                                   encoding="utf-8")
    print("\n".join(txt[:6]))
    print(f"\nwrote archive/docs/font_states/bigram_histogram.{{txt,csv}}")


if __name__ == "__main__":
    main()
