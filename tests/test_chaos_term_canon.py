"""Guard: the dark god カオス and the light goddess ルシリス render by canon.

Canon (user, 2026-06-21): Chaos is the **God of Darkness** worshipped by
demonkind and Velzeria; the exact counterpart to **Lushiris, the Goddess of
Light** (order/light). The two form a deliberate parallel pair.

Naming (honorific 様 → Lord/Lady; epithet 王 / 女神 → the capitalized title):
  - カオス様      → **Lord Chaos**            ↔  ルシリス様      → **Lady Lushiris**
  - 混沌の王カオス → **Chaos, Lord of Darkness** ↔ 光の女神ルシリス → **Lushiris, Goddess of Light**
  - カオス (plain) → **Chaos**                ↔  ルシリス (plain) → **Lushiris**

So `Lord Chaos` / `Lady Lushiris` (honorifics) are CORRECT and kept. The epithet
titles are always capitalized: **Lord of Darkness**, **Goddess of Light**. The
forbidden forms are the royal `King Chaos`, the ad-hoc lowercase
`Chaos, lord of disorder/darkness`, and lowercase `light goddess` /
`goddess of light` for the epithet.

Red state (2026-06-21): scen124 used "King Chaos"/"Chaos, lord of ..." (now
"Chaos, Lord of Darkness"); scen001/033/053/105/124/fntsys13 used lowercase
"goddess of light" / "light goddess" (now "Goddess of Light").

Enforces SPELLING + CASE only (deterministic). Whether a line uses the honorific
vs the epithet vs the bare name is a per-line JP call made by the editor.
"""
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts' / 'en'

KING = re.compile(r'(?i)\bKing\s+Chaos\b')
# any "Chaos, [Ll]ord of X" that is NOT the canonical "Chaos, Lord of Darkness"
CHAOS_EPITHET = re.compile(r'Chaos,\s+[Ll]ord\s+of\s+(\w+)')
# lowercase epithet for Lushiris (must be the capitalized title "Goddess of Light")
LC_GODDESS = re.compile(r'\b(light goddess|goddess of light)\b')
# the honorific カオス様 must render "Lord Chaos" (both words capitalized) — never the
# lowercase "lord chaos" / "lord Chaos". (Plain カオス → "Chaos" is unaffected; the
# common noun "chaos" = disorder is legitimately lowercase, so only the honorific is checked.)
LC_LORD_CHAOS = re.compile(r'\blord [Cc]haos\b')


def _game_scripts():
    # in-game dialogue/narration only — fntsys*/syswin* are UI string tables with
    # their own width budgets and a disk-match invariant (test_fntsys13), so the
    # epithet canon is enforced on the scenario + plot scripts the player reads.
    for path in sorted(SCRIPTS.glob('*.txt')):
        if path.name.startswith(('fntsys', 'syswin')):
            continue
        yield path


def _scan(pattern):
    hits = []
    for path in _game_scripts():
        flat = path.read_text(encoding='utf-8').replace('<$FFFC>', ' ')
        for m in pattern.finditer(flat):
            hits.append((path.name, re.sub(r'\s+', ' ', m.group(0))))
    return hits


def test_no_king_chaos():
    bad = _scan(KING)
    assert not bad, (
        'Chaos is the God of Darkness, NOT a king. 混沌の王カオス → '
        f'"Chaos, Lord of Darkness". Offenders: {bad}'
    )


def test_chaos_epithet_is_lord_of_darkness():
    bad = [(f, t) for f, t in _scan(CHAOS_EPITHET) if t != 'Chaos, Lord of Darkness']
    assert not bad, (
        '混沌の王カオス must render as "Chaos, Lord of Darkness" (capitalized, '
        f'never "lord of disorder/darkness"). Offenders: {bad}'
    )


def test_goddess_of_light_is_capitalized():
    bad = _scan(LC_GODDESS)
    assert not bad, (
        'Lushiris\' epithet 光の女神 is the title "Goddess of Light" (capitalized) '
        f'— never lowercase "goddess of light" / "light goddess". Offenders: {bad}'
    )


def test_lord_chaos_is_capitalized():
    bad = _scan(LC_LORD_CHAOS)
    assert not bad, (
        'The honorific カオス様 is the title "Lord Chaos" (both words capitalized) '
        f'— never lowercase "lord chaos" / "lord Chaos". Offenders: {bad}'
    )


def test_canonical_forms_exist():
    seen = lambda p: bool(_scan(re.compile(p)))
    assert seen(r'\bLord Chaos\b'), 'カオス様 → "Lord Chaos" expected in corpus'
    assert seen(r'\bLady Lushiris\b'), 'ルシリス様 → "Lady Lushiris" expected'
    assert seen(r'Chaos, Lord of Darkness'), '混沌の王カオス → "Chaos, Lord of Darkness" expected'
    assert seen(r'Goddess of Light'), '光の女神 → "Goddess of Light" expected'
