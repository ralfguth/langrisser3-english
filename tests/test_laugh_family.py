"""Guard: a JP laugh form must render with its English SOUND FAMILY.

Standardised laugh map (Ralf 2026-06-23). The JP onomatopoeia cluster into three
sound families; the EN rendering must use the matching family (the main/variant
choice within a family, and the ALL-CAPS for a loud gargalhada, are editorial):

  contained chuckles (normal case)
    クックッ / くくく  →  "Heh heh heh"   (variant "Keh heh heh" = grotesque)
    ヒッヒッ(ヒ)      →  "Hee hee hee"   (variant "Kee hee hee" = Grove signature)
    フフフ / ふふふ   →  "Heh heh" or "Hee hee" (smug)
    うふふ          →  "Tee hee"       (variant "Hee hee", e.g. Tiaris)
  open gargalhadas (ALL CAPS — a belly-laugh is loud)
    ふははは        →  "BWAHAHA!"      (variant "HA HA HA!")
    ハハハ          →  "HA HA HA!"     (variant "HAH HAH HAH!" dry/arrogant)
    アッハッハ      →  "AH HA HA!"     (variant "HA! HA HA HA!" mocking)

This guard enforces only the SOUND FAMILY (eh / ee / ha) per JP form — that part
is deterministic. It catches the cross-family bug (e.g. Grove's ヒッヒッ rendered
"Heh heh heh", erasing his cackle) and the ふふふ scatter ("Hihihi"/"Ufufufu").

Red state (v0.6 review): ヒッヒッ rendered as the クックッ "Heh heh" sound (Grove),
ふふふ/うふふ as "Hihihi"/"Ufufufu"/"Hehehe", and クックッ deviations
("Kuh kuh kuh", "Hahaha").
"""
import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))
EN = PROJ / "scripts" / "en"
JP = PROJ / "scripts" / "jp"

EH = r"[hk]eh[ '-]?heh"           # Heh heh / Keh heh
EE = r"[hkt]ee[ '-]?hee"          # Hee hee / Kee hee / Tee hee
HA = r"(ha[ '-]?ha|bwah|ahah|gwah|mwah|kyah|muha)"  # any open ha-laugh

# (JP forms, required EN sound regex, family label)
RULES = [
    (["クックッ", "くくく"], EH, "Heh/Keh heh"),
    (["ヒッヒッ"], EE, "Hee/Kee hee (Grove)"),
    (["ふふふ", "フフフ"], f"({EH}|{EE})", "Heh heh / Hee hee"),
    (["うふふ"], EE, "Tee/Hee hee"),
    (["ふははは", "ハハハ", "アッハッハ"], HA, "Ha-gargalhada"),
]
_COMPILED = [(forms, re.compile(rx, re.I), label) for forms, rx, label in RULES]


def _entries(path):
    from layout_qa.parser import parse_scenario
    return parse_scenario(path)


def test_laugh_forms_match_sound_family():
    violations = []
    for jp_path in sorted(JP.glob("scen*J.txt")):
        en_path = EN / (jp_path.name[:-5] + "E.txt")
        if not en_path.exists():
            continue
        je, ee = _entries(jp_path), _entries(en_path)
        for i in range(min(len(je), len(ee))):
            jp_raw, en_raw = je[i].raw, ee[i].raw
            for forms, rx, label in _COMPILED:
                if any(f in jp_raw for f in forms) and not rx.search(en_raw):
                    sid = jp_path.name[:-5]
                    en_txt = re.sub(r"<\$[0-9A-Fa-f]+>", " ", en_raw).strip()[:46]
                    violations.append(f"{sid}[{i}] {forms[0]}→{label}: {en_txt!r}")
    assert not violations, (
        "Laugh must use its JP sound family (see the map in this file):\n"
        + "\n".join(violations))
