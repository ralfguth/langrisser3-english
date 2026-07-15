"""TDD gate for fntsys1 (system menu / command labels) — FNT_SYS pair 0.

Content locks from the JP<->EN eyeball parity sweep (roadmap T04, 242
records paired one-by-one against scripts/jp/fntsys1J.txt). Only records
whose MEANING diverged are locked here; stylistic latitude stays free.

Composition facts found during the sweep (do not "fix" these):
- rec60 'Select a new movement' + rec151 'mode' are ONE composed sentence
  (JP: 移動モードを + 選択してください) — a deliberate EN word-order split.
- rec81/109/142/183/232 are particle-suffixes the engine appends after a
  name (JP を/に/の glue). Their leading space IS the separator (the
  leading-space bigram renders a half-width gap) — load-bearing.
- rec91/92 carry a trailing space (separator before a composed value).
- rec96 (します) and rec124 (超) are JP composition fragments whose
  consumer is unidentified (needs RE); they ship EMPTY rather than the
  'uk 1'/'uk 2' placeholder garbage. Flagged for playtest/RE.
"""

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

FNTSYS1 = PROJ / "scripts" / "en" / "fntsys1E.txt"

EXPECTED_RECORDS = 242

# rec index -> exact text (terminator stripped). From the T04 sweep.
CONTENT_LOCKS = {
    15: "Balanced",                  # 通常思考 (AI: normal) — was 'General Planning'
    39: "Check targeting range?",    # typo 'targetting'
    48: "Confirm",                   # 決定 (button) — was literal 'Decide'
    66: "MV",                        # ＭＶ stat label — was 'Move'
    71: "Assign Troops",             # 兵士配属 — was 'Troop Officer'
    72: "Equip Items",               # アイテム装備 — was 'Inventory'
    74: "Equip",                     # 装備する (command) — was 'Equipping'
    96: "Equipment",                 # was します fragment; repurposed as the
                                     # equip-title centre piece (prog4_equip_title)
    105: "Cannot be used in the trial version",   # 体験版 — was 'not enough experience'
    122: "Ｌ",                        # Ｌ button label — full-width like JP Ｌ (was
                                     # ASCII 'L', which the new trailing rule would
                                     # have dropped to a half-width tile; the Saturn
                                     # button glyph must stay full-width/centered)
    124: "",                         # 超 fragment — empty until RE
    137: "Self-destruct!",           # 自爆！ — was 'Autodestruction!'
    142: " will be the new class",   # にクラスチェンジします suffix; trailing '.'
                                     # dropped 2026-06-13 — it overflowed the box
                                     # right border (leading space stays, load-bearing)
    144: "Path",                     # 成長属性 — class-access progression header
                                     # (LV 10/30/50 → Cavalry/Aerial/Priest). One
                                     # word so it doesn't collide with the value
                                     # cell. (Ralf 2026-06-26; was "Class Path",
                                     # "Growth Type", 'A. Growth')
    149: "Movement cancelled",       # 移動先指定を取り消します — actions aren't
    152: "View Map",                 # マップ参照 (2x2 box) — was '<$0000><$0000>Show Map'
    155: "Confirm?",                 # 決定？ (name-entry prompt) — 決定 is the
                                     # accept action (C button); EN must use the
                                     # same word as rec48 'Confirm' everywhere
                                     # (user 2026-06-10); was 'Finished?'
    157: "Sell Items",               # アイテム売却 — symmetric with 173
    170: "Troop MRES",               # 傭兵魔法耐性 — MRES per 2026-06-11 stat canon
    173: "Buy Items",                # アイテム購入 — was 'For Sale' (opposite POV)
    183: "Menu",                     # の選択 — draws at a FIXED SLOT (X=22) in
                                     # the equip title, NOT concatenated; the
                                     # old leading space pushed the u onto the
                                     # window border (instrumented-Ymir 2026-06-11)
    184: "Growth",                   # 成長度 — was 'Rating'
    237: "Retreats",                 # 撤退数 — was 'Defeats'
    240: "Cursed and unable to cast spells!",     # 呪われていて不可能 — curse lost
    241: "Monsters under your control will be dismissed.",  # 支配下 — was 'at the bottom'
}

# Composition suffixes whose leading space is load-bearing.
LEADING_SPACE_SUFFIXES = (142, 232)


def _records():
    return [l.rstrip("\n") for l in FNTSYS1.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def test_record_count():
    assert len(_records()) == EXPECTED_RECORDS


def test_content_locks():
    recs = _records()
    bad = {}
    for ri, want in CONTENT_LOCKS.items():
        got = recs[ri].replace("<$FFFF>", "")
        if got != want:
            bad[ri] = (got, want)
    assert not bad, f"fntsys1 parity locks diverge (rec: (got, want)): {bad}"


def test_no_uk_placeholders():
    recs = _records()
    bad = [i for i, r in enumerate(recs) if "uk 1" in r or "uk 2" in r]
    assert not bad, f"fntsys1 still carries 'uk N' placeholder garbage: {bad}"


def test_new_class_suffix_fits_box():
    """rec142 ' will be the new class.' overflowed: the trailing '.' covered
    the right box border (user playtest 2026-06-13, screenshot 155111). The
    box fits 11 encoder tiles; the period made it 12.

        Red state: ' will be the new class.' = 12 tiles.

    Fix drops the period (the leading space stays — it is load-bearing)."""
    from d00_tools import encode_text_to_entry
    import fnt_sys_tools as fs
    from font_tools import FNTSYS_BIGRAM_TILE_MAP
    rec = _records()[142]
    raw = encode_text_to_entry(rec, fs._build_fntsys_char_map(),
                               bigram_tile_map=FNTSYS_BIGRAM_TILE_MAP)
    width = sum(1 for i in range(0, len(raw) - 1, 2)
                if ((raw[i] << 8) | raw[i + 1]) < 0xFFFC)
    assert width <= 11, f"rec142 is {width} tiles, '.' overflows the 11-tile box"


def test_composition_suffixes_keep_leading_space():
    recs = _records()
    bad = []
    for ri in LEADING_SPACE_SUFFIXES:
        text = recs[ri].replace("<$FFFF>", "")
        if text and not text.startswith(" "):
            bad.append((ri, text))
    assert not bad, (
        f"composition suffix lost its load-bearing leading space "
        f"(renders glued to the composed name): {bad}"
    )


def test_only_scenario_turn_zenkaku_menus_ascii():
    """User decision 2026-06-26: the ONLY words that stay zenkaku are the title
    words SCENARIO and TURN. The menu labels START / OPTIONS / SAVE / LOAD are
    ASCII, so the bigram encoder renders them HALF-WIDTH. (Supersedes the older
    "all standalone UI titles stay full-width" rule for those menus.)
    """
    lines = _records()   # blank-line-immune (records, not raw lines)
    text = "\n".join(lines)
    # SCENARIO and TURN stay zenkaku (full-width).
    for label in ("ＳＣＥＮＡＲＩＯ", "ＴＵＲＮ"):
        assert label in text, f"title word {label} must stay zenkaku in fntsys1"
    # The menu labels are ASCII now (half-width); the full-width forms are gone.
    for ascii_label in ("START<$FFFF>", "OPTIONS<$FFFF>"):
        assert ascii_label in text, f"menu label {ascii_label} must be ASCII"
    for fullwidth in ("ＳＴＡＲＴ", "ＯＰＴＩＯＮＳ"):
        assert fullwidth not in text, f"menu label {fullwidth} must no longer be zenkaku"
    assert lines[19] == "LOAD<$FFFF>"
    assert lines[20] == "SAVE<$FFFF>"
    assert lines[84] == "SAVE<$FFFF>"
    assert lines[85] == "LOAD<$FFFF>"
