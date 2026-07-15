"""Name-accuracy locks for fntsys4 (classes) and fntsys10 (items) — T05.

From the JP<->EN eyeball sweep against scripts/jp/fntsys{4,10}J.txt with
the langrisser.wiki + Norse/Celtic myth canon as cross-reference:

- The シカ classes are the SHIKA TRIBE (Do Kahni's people; canon
  'Shika' per NAMES AND TERMS.txt line 122 and langrisser.wiki 'Shika
  Tribe Characters'). シカシカ〜 is the JP devs' own doubled form —
  rendered 'Shika Shika …', never the 'ShikShika' mangle.
- Mythological proper nouns follow their canonical spelling (same rule
  that gave Hrunting/Gram/Gungnir): Gae Bolg, Mjolnir, Hadding,
  Gjallarhorn, Scathach, Dullahan, Minotaur.
- スターピアス is a pierced earring (ピアス), not a coin — its own
  fntsys13 description says 'platinum ear-stud'.
- Item 170 (<$0188>のルーン) is the THUNDER rune: tile 0x0188 is the
  same 雷 glyph fntsys1 rec166 renders as 'Thunder', and its fntsys13
  description says 'blessing of the thunder god'.
- グリーブ (greaves) was misspelled 'Grieves'.

The cross-file guard keeps the old forms from drifting back anywhere in
the live scripts or the fntsys12/13 build sources.
"""

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

FNTSYS4 = PROJ / "scripts" / "en" / "fntsys4E.txt"
FNTSYS10 = PROJ / "scripts" / "en" / "fntsys10E.txt"

FNTSYS4_LOCKS = {
    162: "Shika Shika Wolf",
    180: "Shika Shika Spear",
}

FNTSYS10_LOCKS = {
    30: "Gae Bolg",          # ゲイ・ボルグ — was 'Gei Voulge'
    38: "Mjolnir",           # ミョッルニル — was 'Mjollner'
    55: "Hadding",           # ハディング — was 'Harding' (no R in JP)
    114: "Gjallarhorn",      # ギャラルのホルン — was 'Gjaller Horn'
    126: "Star Earring",     # スターピアス — was 'Star Coin'
    135: "Greaves",          # グリーブ — was 'Grieves'
    150: "Scathach Tome",    # スカサハの書 — was 'Book of Sukasaha'
    170: "Thunder Rune",     # <$0188>(雷)のルーン — was 'Spirit Rune'
}

# T07 (user decision 2026-06-10): the UI name budget IS the JP maximum
# (8 tiles in fntsys10). UI table names fit the budget; DIALOGUE PROSE
# keeps the full canonical names (same split as Gilbert: bare in UI,
# full form in prose). 18 names shortened, all <=8 encoder tiles:
FNTSYS10_BUDGET_TILES = 8
FNTSYS10_SHORT_NAMES = {
    11: "Decimation Sword",     # was Sword of Decimation (10t)
    46: "Dragonlord Staff",     # was Staff of the Dragon Lord (12t)
    65: "Dragon Lance",         # was Lance of the Dragon Knight (13t)
    87: "Celestial Robe",       # was Feathered Robe of the Goddess (15t); 天女 = celestial maiden
    88: "Dark Vestments",       # was Vestments of Darkness (11t)
    92: "Guard Bracelet",       # was Protection Bracelet (10t)
    115: "Immortal Crest",      # was Crest of the Lord of Immortals (15t)
    120: "Holy Talisman",       # was Holy King's Talisman (11t)
    128: "Spiritstone Ring",    # was Ring of the Stone Spirit (12t)
    132: "Hegemon Necklace",    # was Necklace of the Hegemon (12t)
    147: "Hero's Stone",        # was Secret Stone of the Hero (12t)
    150: "Scathach Tome",       # was Book of Scathach (9t)
    152: "Secret Manual",       # was Book of Mysteries (9t)
    153: "Dead Man's Heart",    # was Heart of the Deceased (11t)
    154: "Demon Water",         # was Water of the Demon World (12t)
    156: "Dark Dragonstone",    # was Demon Dragon Stone (9t)
    157: "White Grimoire",      # was Book of White Magic (10t)
    159: "Black Grimoire",      # was Book of Black Magic (10t)
}

# old form -> files it must never reappear in
BANNED_FORMS = (
    "Gei Voulge", "Mjollner", "Harding", "Gjaller Horn", "Star Coin",
    "Grieves", "Sukasaha", "ShikShika", "Minotauros", "Durahan",
    # fntsys12 semantic-pass regressions (T06): タコ is an octopus (#35
    # had #34's lobster copy-pasted), 生き残り are survivors not corpses
    # (#48), and a missing space after the comma (#26).
    "oversized lobsters, supreme", "remains of dinosaurs", "But,they",
)
SWEEP_FILES = (
    list((PROJ / "scripts" / "en").glob("*.txt"))
    + list((PROJ / "metadata" / "en").glob("*.txt"))
)


def _records(path: Path):
    return [l.rstrip("\n") for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def test_fntsys4_class_name_locks():
    recs = _records(FNTSYS4)
    bad = {ri: (recs[ri].replace("<$FFFF>", ""), want)
           for ri, want in FNTSYS4_LOCKS.items()
           if recs[ri].replace("<$FFFF>", "") != want}
    assert not bad, f"fntsys4 name locks diverge (rec: (got, want)): {bad}"


def test_fntsys10_item_name_locks():
    recs = _records(FNTSYS10)
    bad = {ri: (recs[ri].replace("<$FFFF>", ""), want)
           for ri, want in FNTSYS10_LOCKS.items()
           if recs[ri].replace("<$FFFF>", "") != want}
    assert not bad, f"fntsys10 name locks diverge (rec: (got, want)): {bad}"


def test_old_forms_absent_everywhere():
    bad = []
    for f in SWEEP_FILES:
        text = f.read_text(encoding="utf-8")
        for form in BANNED_FORMS:
            if form in text:
                bad.append((f.name, form))
    assert not bad, f"obsolete name forms still present (file, form): {bad}"


def test_fntsys10_short_name_locks():
    recs = _records(FNTSYS10)
    bad = {ri: (recs[ri].replace("<$FFFF>", ""), want)
           for ri, want in FNTSYS10_SHORT_NAMES.items()
           if recs[ri].replace("<$FFFF>", "") != want}
    assert not bad, f"fntsys10 short-name locks diverge (rec: (got, want)): {bad}"


def test_fntsys10_every_name_fits_jp_budget():
    """Every item name must encode within the JP-derived 8-tile budget
    (user decision 2026-06-10: the budget IS the JP maximum)."""
    from fnt_sys_tools import _build_fntsys_char_map
    from d00_tools import encode_text_to_entry
    from font_tools import BIGRAM_TILE_MAP
    char_map = _build_fntsys_char_map()
    bad = []
    for ri, rec in enumerate(_records(FNTSYS10)):
        text = rec.replace("<$FFFF>", "")
        if not text or text.startswith("<$"):
            continue
        width = len(encode_text_to_entry(
            text, char_map, bigram_tile_map=BIGRAM_TILE_MAP)) // 2
        if width > FNTSYS10_BUDGET_TILES:
            bad.append((ri, text, width))
    assert not bad, (
        f"fntsys10 names over the {FNTSYS10_BUDGET_TILES}-tile JP budget "
        f"(rec, name, tiles): {bad}"
    )


def test_no_fraction_multipliers_in_desc_sources():
    """Stat effects render as percentages/direct reductions, never
    fractions (feedback_no_fraction_multipliers)."""
    bad = []
    for fname in ("fntsys12_src.txt", "fntsys13_src.txt"):
        text = (PROJ / "metadata" / "en" / fname).read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if line.startswith("@stat") and ("/4" in line or "/2" in line
                                             or "/3" in line):
                bad.append((fname, i, line))
    assert not bad, f"fraction multipliers in @stat lines: {bad}"
