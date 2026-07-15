"""Guard: 魔動巨兵ガルツォーク (Galshook, the Empire's OWN giant) renders as the
"Arcane Giant"; its 魔動砲 renders as the "Magic Cannon" — never "Demonic".

Lore: 魔動 ("magic-driven") is the Rigüler Empire's own magitek. The Empire does
not demonize its own weapon, so "Demonic" is never used for Galshook — "Demonic"
is reserved for the Larcuss Floating Castle's 魔動砲 as demonized by the Empire
(the POV split enforced by test_cannon_term_canon.py).

Naming (Ralf 2026-06-23): 魔動 on the GIANT UNIT → **"Arcane"** ("Arcane Giant
Galshook" — more evocative, no POV split there). 魔動 on the CANNON (a weapon
CLASS shared by the Floating Castle and Galshook) stays **"Magic Cannon"** to
preserve the Magic/Demonic POV pair on 魔's magic/demon ambiguity.

Red state for this guard's earlier form: the title leaked as "Demonic Giant
Galshook" (scen019×3, scen071), "our demonic giant of old" (scen074), and
Galshook's own cannon as "Demonic Cannon" (scen019[89], scen074[50]); a later
pass rendered the giant as "Magic Giant" before the Arcane rename.
"""
import re
from pathlib import Path

EN = Path(__file__).resolve().parent.parent / "scripts" / "en"

# Galshook is the only 巨兵 in the script, so a "demonic giant" OR a "magic giant"
# is always the mis-render — the giant unit is the "Arcane Giant".
_NON_ARCANE_GIANT = re.compile(r"(?i)(demonic|magic)\s+giant")

# Battle scens where every 魔動砲 is Galshook's OWN cannon (no Floating-Castle
# cannon is present), so "Demonic Cannon" there is the Empire demonizing itself.
GALSHOOK_BATTLE_FILES = ["scen019E.txt", "scen074E.txt"]


def _strip(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<\$[0-9A-Fa-f]+>", " ", text))


def test_galshook_giant_is_arcane():
    """魔動巨兵 Galshook is the Empire's own → 'Arcane Giant', never Demonic/Magic Giant."""
    offenders = {}
    for path in sorted(EN.glob("scen*E.txt")):
        flat = _strip(path.read_text(encoding="utf-8"))
        hits = _NON_ARCANE_GIANT.findall(flat)
        if hits:
            offenders[path.name] = hits
    assert not offenders, f"Galshook giant must be 'Arcane Giant': {offenders}"


def test_galshook_battles_use_magic_cannon():
    """In Galshook's own battles the cannon it fires is the Magic Cannon."""
    offenders = {}
    for name in GALSHOOK_BATTLE_FILES:
        flat = _strip((EN / name).read_text(encoding="utf-8"))
        if "Demonic Cannon" in flat:
            offenders[name] = flat.count("Demonic Cannon")
    assert not offenders, (
        "Galshook's own 魔動砲 is the 'Magic Cannon', not 'Demonic Cannon' "
        f"(Demonic is reserved for the Floating Castle, Empire POV): {offenders}"
    )


def test_arcane_giant_title_exists():
    """Sanity: the canonical proper-noun title is actually present after the fix."""
    corpus = "".join(
        _strip((EN / n).read_text(encoding="utf-8"))
        for n in ("scen019E.txt", "scen071E.txt", "scen076E.txt")
    )
    assert "Arcane Giant Galshook" in corpus
