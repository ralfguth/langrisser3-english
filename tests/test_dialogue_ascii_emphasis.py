"""Dialogue emphasis is ASCII caps, never zenkaku (user rule 2026-06-12).

Zenkaku full-width Latin is reserved for UI elements (composed titles,
SCENARIO headers, controller-button names the JP itself sets full-width).
Dramatic emphasis inside dialogue — scen033 "we ARE our true form",
scen038 "Let's eat, EAT!", scen107 "*GRIN*!" — must be plain ASCII caps
rendered tight by the bigram machinery, with no centered standalone
letters mid-word (the missing-bigram fallback, banned for word bodies).

The three words were zenkaku-PINNED on 2026-06-11 as a stopgap while the
stat-bigram pairs landed (archive/docs/20260611_desc_stat_bigram_plan.md,
"Dialogue regression sweep"). This test locks the conversion back.

('G','R') is the one pair the conversion needed; it lives at tile 1582 —
an UNMAPPED dead-kanji slot inside the old 0.2 patch range. The 2026-06-09
user note (archive/docs/20260609_fntsys_systems_and_encoder.md) ruled
the "1500-1620 renders with name-grid spacing in dialogue" caveat
OBSOLETE: it was a 0.2 patch-binary artifact, and we build engine+font from
the JP originals. scen107 playtest is the final visual confirmation.
"""

import re
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import font_tools as ft           # noqa: E402
from text_measure import iter_tiles  # noqa: E402

SCEN_DIR = PROJ / "scripts" / "en"

ZENKAKU_LATIN = re.compile(r"[Ａ-Ｚａ-ｚ０-９]")

# Controller buttons (user 2026-06-12: "A B C X Y Z L R pode ser zenkaku").
# ＨＰ/ＭＰ are NOT allowed: stat abbreviations are ASCII half-width
# everywhere (user 2026-06-12), same as the fnt_sys rule.
SCEN001_ALLOWED = set("ＡＢＣＸＹＺＬＲ")


# ---------------------------------------------------------------------------
# 1. The three pins are converted to ASCII
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scen,word", [
    ("scen033E.txt", "we ARE our"),
    ("scen038E.txt", "Let's eat, EAT!"),
    ("scen107E.txt", "*GRIN*!"),
    # HP/MP are ASCII stat abbreviations (user 2026-06-12). scen038's
    # stat-up entries are rephrased to the JP structure (体力が１上がった
    # = "HP rose by 1") so HP always sits in (H,P)/(P,' ') parity.
    ("scen001E.txt", "and soldiers recover some HP,"),
    ("scen001E.txt", "Use your MP to"),
    ("scen038E.txt", "Pierre's HP rose by 1!"),
    # token stat-line: the wrap break sits at the HP|rose word boundary with
    # NO padding space (line_padding_space is an error since 2026-06-19).
    ("scen038E.txt", "'s HP<$FFFC>rose by 1!"),
])
def test_pin_converted_to_ascii(scen, word):
    text = (SCEN_DIR / scen).read_text(encoding="utf-8")
    assert word in text, f"{scen}: ASCII emphasis {word!r} missing"


# ---------------------------------------------------------------------------
# 2. No zenkaku Latin anywhere in dialogue, outside the UI whitelist
# ---------------------------------------------------------------------------

def test_no_zenkaku_latin_in_dialogue():
    bad = []
    for path in sorted(SCEN_DIR.glob("scen*E.txt")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            chars = set(ZENKAKU_LATIN.findall(line))
            if not chars:
                continue
            if "ＳＣＥＮＡＲＩＯ" in line:
                continue  # composed scenario-title header (UI)
            if path.name == "scen001E.txt" and chars <= SCEN001_ALLOWED:
                continue  # controller buttons + ＨＰ/ＭＰ, zenkaku in JP too
            bad.append((path.name, n, "".join(sorted(chars)), line.strip()[:60]))
    assert not bad, f"zenkaku Latin in dialogue prose: {bad}"


# ---------------------------------------------------------------------------
# 3. The emphasis words render tight — no standalone letters mid-word
# ---------------------------------------------------------------------------

# IMPORTANT: greedy parity is decided by the WHOLE FFFC-delimited
# segment, not by an excerpt — "regain some HP," tokenized tight in
# isolation but emitted a standalone centered P inside the real scen001
# segment (caught only by the track01 byte check). Always test the full
# segment as the engine sees it.
@pytest.mark.parametrize("segment", [
    "see we ARE our", "Let's eat, EAT!", "……*GRIN*!",
    "and soldiers recover some HP,",
    "(Magic) Use your MP to", "(Summon) Use your MP to",
    "Pierre's HP rose by 1!", "Lewin's HP rose by 1!",
    "Gilbert's HP ", "rose by 1!", "'s HP ",
])
def test_emphasis_renders_without_standalone_caps(segment):
    """No standalone UPPERCASE tile may appear in these segments.

    Standalone caps/digits are the CENTERED zenkaku-style glyphs (7-42)
    — mid-text they break the half-width line (the missing-bigram
    fallback defect). Standalone lowercase at word end ('c' in
    "(Magic)") is the normal right-blank pattern and is fine
    (reference: encoder right-blank space rule).
    """
    singles = [s for s, cost in iter_tiles(segment)
               if cost == 1 and len(s) == 1 and s.isalpha() and s.isupper()]
    assert not singles, (
        f"{segment!r} emits standalone caps tiles {singles} — "
        f"missing word-body bigram (centered-fallback defect)"
    )


# ---------------------------------------------------------------------------
# 4. The (G,R) pair: mapped at 1582, standard Eagle interleave
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pair,tile", [
    (("G", "R"), 1582),
    (("H", "P"), 1583),
])
def test_caps_bigram_mapped(pair, tile):
    assert ft.BIGRAM_TILE_MAP[pair] == tile


@pytest.mark.parametrize("pair,tile", [
    (("G", "R"), 1582),
    (("H", "P"), 1583),
])
def test_caps_glyph_is_eagle_interleave(pair, tile):
    jp = PROJ / "data" / "jp" / "font_jp.bin"
    if not jp.exists():
        pytest.skip("JP FONT.BIN not present")
    font = ft.generate_english_font(jp.read_bytes())
    got = font[tile * 32:(tile + 1) * 32]
    want = ft._interleave(ft._LETTER_GLYPHS[pair[0]], ft._LETTER_GLYPHS[pair[1]])
    assert got == want
