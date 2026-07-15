#!/usr/bin/env python3
"""font_slot_audit.py — FONT.BIN tile-budget audit for the bigram expansion.

Answers, against the REAL final scripts and the REAL encoders: how many tile
slots does the English patch actually use, how many are dead (reusable), which
bands are RESERVED for engine-indexed glyphs, and what are the genuine bigram
"targets" the encoder currently splits into singles.

This is the reproducible basis for the in-place bigram expansion (v0.8 font
refactor, Stage 3 of 20260607_font_encoder_refactor_roadmap.md). See the durable
record archive/docs/20260625_font_bin_grow_spike.md.

Surfaces are encoded each with ITS OWN map so fntsys/syswin are counted correctly:
  - D00 (scenNNNE.txt) + PLOT (plotE.txt): CHAR_TILE_MAP / BIGRAM_TILE_MAP
  - FNT_SYS (fntsysNE.txt): _build_fntsys_char_map / FNTSYS_BIGRAM_TILE_MAP (prose)
  - SYSWIN (syswinE.txt): via encode_syswin (scanned against known map values)

Key definitions:
  USED      tile indices (0..1690) the encoder actually emits across all surfaces
  RESERVED  engine-indexed bands that must NOT be reassigned:
              - low glue 0..45   (mov #imm8 <=0x7F; numbers/menus; magic name
                                   tables store ASCII -> render via tiles 17-42)
              - menu/install 1500..1690 (0.2-patch menu/stat read by PROG_3/4 by
                                   tile index, intermixed with dialogue installs)
  DEAD POOL dialogue grid 46..1499 NOT used by scripts -> the in-place reuse pool
            (residual risk: confirm a chosen slot is not referenced by any PROG/
             A0LANG binary before reusing it)
  TARGETS   genuine half-width bigrams the greedy encoder splits into singles,
            EXCLUDING (a) full-width/zenkaku-involving pairs (render as singles by
            design) and (b) punct+space pairs the right-blank skip rule handles.

Usage:
  python3 tools/font_slot_audit.py            # report
  python3 tools/font_slot_audit.py --targets  # also print the target bigram list
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import font_tools as ft  # noqa: E402
from d00_tools import (  # noqa: E402
    parse_script_file, encode_text_to_entry, RIGHT_BLANK_STANDALONE_CHARS as RB,
)
import fnt_sys_tools as fst  # noqa: E402
import plot_tools  # noqa: E402
from plot_tools import encode_plot_script  # noqa: E402

SCRIPTS = REPO / "scripts" / "en"
TILE_CAP = 1691

# The half-width (composable) glyph alphabet — exactly what generate_english_font
# can interleave. Full-width (zenkaku) chars are NOT here (they render as singles).
def _half_alphabet() -> set:
    half = {" "}
    half |= set(ft._LETTER_GLYPHS) | set(ft._PUNCT_GLYPHS)
    half |= set(ft._EXTRA_PUNCT_GLYPHS) | set(ft._DIGIT_HALF_GLYPHS)
    half |= set(ft._UMLAUT_HALF_GLYPHS) | {"'"}
    return half


def _fallback_pairs(text: str, bigram_map: dict | None):
    """Pairs the GREEDY encoder emits as two singles (bigram_map miss)."""
    out = []
    for s in re.split(r"<\$[0-9A-Fa-f]*>|\[[^\]]*\]", text):
        s = s.replace("...", "…")
        j = 0
        while j < len(s) - 1:
            p = (s[j], s[j + 1])
            if bigram_map and p in bigram_map:
                j += 2
            else:
                out.append(p)
                j += 1
    return out


def audit():
    import collections
    HALF = _half_alphabet()
    used = set()
    targets = collections.Counter()       # genuine half-width bigram targets
    tgt_dlg = collections.Counter()
    tgt_fnt = collections.Counter()

    def add_used(b):
        for i in range(0, len(b) - 1, 2):
            w = struct.unpack_from(">H", b, i)[0]
            if w < TILE_CAP:
                used.add(w)

    def worth(p):
        return (p[0] in HALF and p[1] in HALF
                and not (p[1] == " " and p[0] in RB))  # punct+space = skip rule

    # D00 + PLOT (dialogue maps)
    for f in sorted(SCRIPTS.glob("scen*E.txt")):
        for t in parse_script_file(f):
            add_used(encode_text_to_entry(t, ft.CHAR_TILE_MAP, ft.BIGRAM_TILE_MAP))
            for p in _fallback_pairs(t, ft.BIGRAM_TILE_MAP):
                if worth(p):
                    targets[p] += 1; tgt_dlg[p] += 1
    add_used(encode_plot_script(SCRIPTS / "plotE.txt", ft.CHAR_TILE_MAP, ft.BIGRAM_TILE_MAP))
    for blk in plot_tools.parse_plot_script(SCRIPTS / "plotE.txt"):
        for p in _fallback_pairs(blk, ft.BIGRAM_TILE_MAP):
            if worth(p):
                targets[p] += 1; tgt_dlg[p] += 1

    # FNT_SYS (own maps, per BIGRAM_PAIRS)
    fnt_char = fst._build_fntsys_char_map()
    for i in range(15):
        sp = SCRIPTS / f"fntsys{i + 1}E.txt"
        if not sp.exists():
            continue
        bmap = ft.FNTSYS_BIGRAM_TILE_MAP if i in fst.BIGRAM_PAIRS else None
        for line in fst._parse_script_records(sp):
            add_used(encode_text_to_entry(line, fnt_char, bmap))
            for p in _fallback_pairs(line, bmap):
                if worth(p):
                    targets[p] += 1; tgt_fnt[p] += 1

    # SYSWIN (scan output against known map values to avoid header pollution)
    try:
        from syswin_tools import encode_syswin
        jp_sw = (REPO / "cache" / "syswin_jp.bin").read_bytes()
        sw = encode_syswin(jp_sw, SCRIPTS / "syswinE.txt")
        allmap = (set(ft.CHAR_TILE_MAP.values()) | set(ft.BIGRAM_TILE_MAP.values())
                  | set(fnt_char.values()) | set(ft.FNTSYS_BIGRAM_TILE_MAP.values()))
        for i in range(0, len(sw) - 1, 2):
            w = struct.unpack_from(">H", sw, i)[0]
            if w in allmap and w < TILE_CAP:
                used.add(w)
    except Exception as e:  # noqa: BLE001
        print(f"  (syswin skipped: {e})", file=sys.stderr)

    reserved = set(range(0, 46)) | set(range(1500, TILE_CAP))
    dead_pool = [t for t in range(46, 1500) if t not in used]

    return {
        "used": used,
        "reserved": reserved,
        "dead_pool": dead_pool,
        "targets": targets,
        "tgt_dlg": tgt_dlg,
        "tgt_fnt": tgt_fnt,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", action="store_true",
                    help="print the full genuine-target bigram list (by frequency)")
    a = ap.parse_args()
    r = audit()
    used, dead, tg = r["used"], r["dead_pool"], r["targets"]
    fnt_only = set(r["tgt_fnt"]) - set(r["tgt_dlg"])

    print(f"FONT.BIN tile budget audit  ({TILE_CAP} tiles total)")
    print(f"  USED by scripts (all surfaces, own maps): {len(used)}")
    print(f"  RESERVED (engine-indexed): low 0..45 + menu/install 1500..1690")
    print(f"  DEAD reuse pool (grid 46..1499, unused):  {len(dead)}")
    print(f"  genuine bigram TARGETS:                   {len(tg)}"
          f"  ({sum(tg.values()):,} occ; fntsys-only {len(fnt_only)})")
    fits = len(dead) >= len(tg)
    print(f"  in-place fit: {'YES' if fits else 'NO'} "
          f"(pool {len(dead)} {'>=' if fits else '<'} targets {len(tg)}, "
          f"margin {len(dead) - len(tg)})")
    if a.targets:
        print("\n# genuine half-width bigram targets (left,right,count):")
        for (l, ri), n in sorted(tg.items(), key=lambda kv: -kv[1]):
            print(f"{l}\t{ri}\t{n}")


if __name__ == "__main__":
    main()
