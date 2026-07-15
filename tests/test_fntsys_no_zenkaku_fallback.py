"""Guard: no fntsys word drops its trailing letter to the WIDE zenkaku single.

The user spotted "OPTIONS" rendering as "OPTION Ｓ" — the trailing S falling to
the wide centered full-width tile. Root cause: the new-font build's fntsys bigram
map (new_encoder.relocated_fntsys_bigram_map) was a relocation of the OLD,
INCOMPLETE fntsys map — it lacked the (c, space) trailing tiles (S_, M_, …) that
the complete dialogue layout (new_font.BIGRAM_LAYOUT) has. With the rigorous
trailing rule on, a composable char that cannot pair mid-word then fell to its
single — which for an uppercase letter is the wide zenkaku glyph.

Signature: an ASCII uppercase letter rendered via a zenkaku single tile (17..42).
The deliberate full-width labels — the Saturn button glyphs ＸＹＺＡＢＣＬＲ
(full-width in JP) and headers ＳＣＥＮＡＲＩＯ/ＴＵＲＮ — use the FULL-WIDTH
character in source, so they are not ASCII and never trip this.

Red state: OPTIONS/RAM/PCM/BGM (ASCII S/M → zenkaku) + the ASCII button labels.
Green: the map fills the (c,space) gap AND the button labels are full-width.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import new_encoder as ne                       # noqa: E402
from fnt_sys_tools import BIGRAM_PAIRS, _build_fntsys_char_map  # noqa: E402
from d00_tools import RIGHT_BLANK_STANDALONE_CHARS as RB        # noqa: E402

UC_ZENKAKU = set(range(17, 43))
ASCII_UC = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
CTRL = re.compile(r"<\$[0-9A-Fa-f]*>")
SCRIPTS = REPO / "scripts" / "en"


def _zenkaku_fallbacks(text, char_map, big):
    """Mirror encode_text_to_entry(trailing_bigram=True): list ASCII uppercase
    chars that get emitted as a wide zenkaku single tile."""
    s = text.replace("...", "…")
    j, n, lrb, bad = 0, len(s), False, []
    while j < n:
        if lrb and s[j] == " " and (j + 1 < n):
            j += 1; lrb = False; continue
        if j + 1 < n and (s[j], s[j + 1]) in big:
            lrb = (s[j + 1] == " "); j += 2; continue
        if (s[j], " ") in big:
            lrb = True; j += 1; continue
        if char_map.get(s[j]) in UC_ZENKAKU and s[j] in ASCII_UC:
            bad.append(s[j])
        lrb = s[j] in RB
        j += 1
    return bad


def test_fntsys_no_word_drops_to_zenkaku():
    char_map = _build_fntsys_char_map()
    big = ne.relocated_fntsys_bigram_map()
    offenders = []
    for n in range(1, 16):
        if (n - 1) not in BIGRAM_PAIRS:
            continue
        f = SCRIPTS / f"fntsys{n}E.txt"
        if not f.exists():
            continue
        for rec in f.read_text(encoding="utf-8", errors="replace").split("<$FFFF>"):
            vis = CTRL.sub("", rec).strip()
            if not vis:
                continue
            bad = _zenkaku_fallbacks(vis, char_map, big)
            if bad:
                offenders.append((f.name, vis[:32], bad))
    assert not offenders, (
        "fntsys ASCII letters fell to the wide zenkaku single (use a (c,space) "
        "half-width tile, or full-width source for a deliberate button/header):\n"
        + "\n".join(f"  {fn}: {ctx!r} -> {b}" for fn, ctx, b in offenders)
    )
