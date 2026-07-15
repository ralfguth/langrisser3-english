"""Disembark guard: NO hardcoded glyph-address codes in the final scripts.

The scripts must contain plain TEXT, not raw `<$xxxx>` tile addresses that point
at a (often CWX-inherited) pre-drawn glyph. Every such code is a piece of content
the project does not really own — it should be the literal letters/word so OUR
encoder pairs it into OUR own bigram (feedback_we_own_the_patch /
feedback_verify_bytes_not_screenshots).

This test SWEEPS every final script and FAILS while any forbidden code remains,
listing each as `file:line  <$XXXX>=meaning`. As the codes are converted to plain
text the list shrinks; GREEN == the inline-code disembark is complete.

LEGITIMATE codes (NOT glyph addresses for a word) are exempt:
  * control / structural codes  (tile >= 0xF000: FFFC/D/E/F, F600 name, F7xx
    voice, FFFB, FFF8xxxx routes …)
  * `<$0000>`  — the full-width blank tile used for CENTERING, not a word
  * the whole name-entry KEYBOARD (fntsys14E.txt) — a positional grid of tile
    codes by engine design (reference_name_entry_keyboard), never prose
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

SCRIPTS = REPO / "scripts" / "en"
CODE_RE = re.compile(r"<\$([0-9A-Fa-f]{4,})>")

# Files that legitimately ARE tile-code grids, not prose.
EXEMPT_FILES = {"fntsys14E.txt"}  # name-entry keyboard (positional, PROG_3)

# Dedicated TIGHT-rendering tiles that plain text cannot reproduce in the bigram
# era: the level-up stat labels STR/INT need the "R-left"/"T-left" half-glyphs so
# the trailing uppercase pairs tight (plain "STR" renders "ST R" with a gap, since
# standalone A-Z map to the centered full-width tiles until the v0.8 half-width
# font). Pinned via these codes; see tests/test_fntsys3_stat_labels.py. Allowed
# until the per-character font makes uppercase half-width.
ALLOWED_TIGHT_TILES = {0x05FB, 0x05FC, 0x05F6, 0x05F7}  # ST, R-left, IN, T-left
# Engine-coupled, not prose: the 's possessive (the (',s) tile) glued straight to
# the <$F600> name token in the level-up template "[Name]'s STR rose by 1!". It
# rides as the name token's parameter (prog3_statup_template); turning it into a
# literal "'s" pushes the engine-rendered line past width. Kept as the code.
ALLOWED_ENGINE_TILES = {0x05DA}
# PLOT.DAT story-route branch IDs: a full-width letter (A-Z, tiles 0x11-0x2A) that
# immediately follows a route CONTROL code is a structural branch label, not prose.
ROUTE_CONTROLS = {0xFFF5, 0xFFF6, 0xFFF7}


def _meaning(tile):
    """Best-effort label so the failure message is actionable."""
    try:
        import font_tools as ft
        inv_char = {v: k for k, v in ft.CHAR_TILE_MAP.items()}
        inv_big = {v: k for k, v in ft.BIGRAM_TILE_MAP.items()}
        if tile in inv_char:
            return repr(inv_char[tile])
        if tile in inv_big:
            return "".join(inv_big[tile])
    except Exception:  # noqa: BLE001
        pass
    return "?"


def _is_allowed(tile):
    return (int(tile) >= 0xF000 or tile == 0
            or tile in ALLOWED_TIGHT_TILES or tile in ALLOWED_ENGINE_TILES)


def find_hardcoded_glyph_codes():
    offenders = []
    for f in sorted(SCRIPTS.glob("*.txt")):
        if (f.name in EXEMPT_FILES or f.name.startswith("_")
                or f.stem.endswith("_src")):
            continue
        for ln, line in enumerate(
                f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            prev = None
            for m in CODE_RE.finditer(line):
                h = m.group(1)
                tile = int(h[:4], 16)
                is_route_id = prev in ROUTE_CONTROLS and 0x0011 <= tile <= 0x002A
                prev = tile
                if _is_allowed(tile) or is_route_id:
                    continue
                offenders.append((f.name, ln, h.upper(), tile))
    return offenders


def test_no_hardcoded_glyph_codes():
    offenders = find_hardcoded_glyph_codes()
    if offenders:
        lines = [f"  {fn}:{ln}  <${h}> = {_meaning(t)}"
                 for fn, ln, h, t in offenders]
        # distinct codes summary
        codes = sorted({(h, t) for _, _, h, t in offenders})
        summary = ", ".join(f"<${h}>={_meaning(t)}" for h, t in codes)
        raise AssertionError(
            f"{len(offenders)} hardcoded glyph-address codes remain in the "
            f"scripts ({len(codes)} distinct) — disembark them to plain text.\n"
            f"distinct: {summary}\n" + "\n".join(lines))
