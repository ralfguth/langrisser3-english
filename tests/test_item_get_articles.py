"""Guard: item-get lines use the article that matches the item's nature.

Canon (user, 2026-07-05), refining the official-style "Acquired the X!" base
pattern (commit 24c335c):
  - generic consumables (multiple copies obtainable, used up on use) take the
    indefinite article  → "Acquired a Magic Herb!"
  - unique items/equipment keep the definite article → "Acquired the Decimation
    Sword!"
  - mass nouns (Nectar, Ambrosia, Vaseline) and proper names (Excalibur,
    Alhazard, Laurin's Ring…) stay bare — English grammar, no article.

This also normalizes three strays that predate the rule: bare "Acquired Magic
Symbol!" / "Acquired Blood Pact!" (unique commons → "the") and the lone
"Acquired the Divine Blessing!" in scen032 vs the 8 bare ones elsewhere
(consumable → "a").

Red state (2026-07-05): every consumable pickup uses "the" (or bare for
Divine Blessing / Hero's Stone / Runestone), and Magic Symbol / Blood Pact are
bare. All JP-verified as plain 〜を手に入れた！ pickups.

Enforces the article + spelling only (deterministic). Line wrapping (<$FFFC>)
is flattened before matching; fit stays layout_qa's job.
"""
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts' / 'en'

# generic consumables → "Acquired a <name>!"
CONSUMABLES = [
    'Magic Herb',
    'Valor Seed',
    'Vitality Leaf',
    'Wisdom Fruit',
    'Power Fruit',
    'Strength Fruit',
    'Protection Fruit',
    'Divine Blessing',
    "Hero's Stone",
    'Runestone',
]

# unique common-noun items → "Acquired the <name>!" (proper names stay bare)
UNIQUE_COMMONS = [
    'Magic Symbol',
    'Blood Pact',
]

# mass nouns → bare "Acquired <name>!"
MASS_NOUNS = ['Nectar', 'Ambrosia', 'Vaseline']


def _flat_scens():
    for path in sorted(SCRIPTS.glob('scen*.txt')):
        yield path.name, path.read_text(encoding='utf-8').replace('<$FFFC>', ' ')


def _offenders(bad_pattern):
    pat = re.compile(bad_pattern)
    return [
        f'{name}: {m.group(0)}'
        for name, flat in _flat_scens()
        for m in pat.finditer(flat)
    ]


def test_consumables_use_indefinite_article():
    for item in CONSUMABLES:
        bad = _offenders(rf'Acquired (?:the )?{re.escape(item)}!')
        assert not bad, f'consumable "{item}" must read "Acquired a {item}!": {bad}'


def test_unique_commons_use_definite_article():
    for item in UNIQUE_COMMONS:
        bad = _offenders(rf'Acquired (?:a )?{re.escape(item)}!')
        assert not bad, f'unique "{item}" must read "Acquired the {item}!": {bad}'


def test_mass_nouns_stay_bare():
    for item in MASS_NOUNS:
        bad = _offenders(rf'Acquired (?:a|an|the) {re.escape(item)}!')
        assert not bad, f'mass noun "{item}" takes no article: {bad}'
