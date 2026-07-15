"""Guard: every item GET-message in the scenarios must name the item exactly as
the fntsys inventory NAMEPLATE (the string the player searches inventory by).

Source of truth = fntsys, fully derived (no hard-coded item list here):
  - scripts/jp/fntsys10J.txt  — the JP nameplate table (item id = line index)
  - scripts/en/fntsys10E.txt  — the EN nameplate table (same index)
zipped by line index → {JP nameplate: EN nameplate}.

For every scenario JP entry that contains a get-message ``<item>を手に入れた``, the
JP ``<item>`` is looked up in the JP nameplate table (longest match, so 体力の実
beats its substring 力の実) and the PAIRED EN entry (same index) must contain the
EN nameplate for that id. Control codes are stripped first, so a name wrapped as
``Dark<$FFFC>Dragonstone`` still matches "Dark Dragonstone".

Why this shape: renaming an item in fntsys10E.txt must immediately flag every
scenario get-message that still uses the old name — the nameplate is the single
source of truth and the scen text follows it ([[feedback_item_names_match_fntsys]],
W3 of the v0.6 review). The message TEMPLATE ("Got the X!" / "X was obtained!")
is cosmetic and not checked — only the NAME.

Red state (v0.6 review): a cluster of get-messages used a paraphrase instead of
the nameplate — "Kusanagi Sword"≠Kusanagi, "Fruit of bravery"≠Valor Seed,
"Demon Stone"≠Dark Dragonstone, "Necklace of the Hegemon"≠Hegemon Necklace, etc.
"""
import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
EN = PROJ / "scripts" / "en"
JP = PROJ / "scripts" / "jp"

GET = "を手に入れた"
_CODE = re.compile(r"<\$[0-9A-Fa-f]+>")


def _table(path):
    return [l.replace("<$FFFF>", "").strip()
            for l in path.read_text(encoding="utf-8").splitlines()]


def _build_name_map():
    jp = _table(JP / "fntsys10J.txt")
    en = _table(EN / "fntsys10E.txt")
    name_map = {}
    for j, e in zip(jp, en):
        if j and e and j != "なし" and e != "None":
            name_map.setdefault(j, e)  # first id wins on duplicate name
    return name_map


NAME_MAP = _build_name_map()
# Longest JP nameplate first so a name that is a substring of another
# (力の実 ⊂ 体力の実) never shadows the real item.
JP_ITEMS = sorted(NAME_MAP, key=len, reverse=True)


def _norm(text):
    return re.sub(r"\s+", " ", _CODE.sub(" ", text)).strip()


def _items_in_get_message(jp_raw):
    """Yield the JP nameplate immediately preceding each を手に入れた in the entry."""
    for m in re.finditer(GET, jp_raw):
        head = jp_raw[:m.start()]
        for it in JP_ITEMS:           # longest-first
            if head.endswith(it):
                yield it
                break


def _entries(path):
    from layout_qa.parser import parse_scenario
    return parse_scenario(path)


def test_get_message_names_match_fntsys_nameplate():
    violations = []
    for jp_path in sorted(JP.glob("scen*J.txt")):
        en_path = EN / (jp_path.name[:-5] + "E.txt")
        if not en_path.exists():
            continue
        jp_entries = _entries(jp_path)
        en_entries = _entries(en_path)
        n = min(len(jp_entries), len(en_entries))
        for i in range(n):
            jp_raw = jp_entries[i].raw
            if GET not in jp_raw:
                continue
            en_norm = _norm(en_entries[i].raw)
            for jp_item in _items_in_get_message(jp_raw):
                want = NAME_MAP[jp_item]
                if want not in en_norm:
                    violations.append(
                        f"{en_path.name}[{i}] {jp_item}→ expected nameplate "
                        f"{want!r}, got: {en_norm!r}")
    assert not violations, (
        "Item get-messages must use the fntsys nameplate verbatim "
        f"(fix the scen to match fntsys10E):\n" + "\n".join(violations))


def test_name_map_loaded():
    # sanity: the nameplate tables actually loaded and aligned
    assert NAME_MAP.get("武勇の種") == "Valor Seed"
    assert NAME_MAP.get("魔竜石") == "Dark Dragonstone"
