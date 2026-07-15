"""Guard: 魔動砲 renders only as the canonical faction-POV terms.

Canon (user, 2026-06-16): 魔動砲 → **Magic Cannon** corpus-wide (Larcuss POV);
**Demonic Cannon** only from the Rigüler POV. The two-word noun forms pair:
`Magic Cannon` / `Demonic Cannon`. NEVER `Magical Cannon`, never a lowercase
`cannon`, never lowercase `magic`/`demonic` as the term head.

This test enforces SPELLING + CASE only (deterministic). Which faction term a
given line uses (Magic vs Demonic) is a semantic POV call made by the editor and
documented in `lang3_local_docs/names-and-terms.md`; it is not machine-checkable.

Red state (pre-fix): scen002 ("Magical Cannon" ×2), scen019 ("magical cannon"
×2), scen069 ("demonic cannon") tripped this.
"""
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts' / 'en'
CANON = {'Magic Cannon', 'Demonic Cannon'}
# `magic|magical|demonic` as the head of a 2-word cannon term, any case.
TERM = re.compile(r'(?i)\b(magic|magical|demonic)\s+cannon\b')


def _iter_cannon_terms():
    for path in sorted(SCRIPTS.glob('*.txt')):
        text = path.read_text(encoding='utf-8')
        # Rejoin a term split across a line break (`Magic<$FFFC>Cannon`).
        flat = text.replace('<$FFFC>', ' ')
        for m in TERM.finditer(flat):
            # collapse internal whitespace the FFFC-join may have widened
            term = re.sub(r'\s+', ' ', m.group(0))
            yield path.name, term


def test_cannon_terms_are_canonical():
    bad = [(f, t) for f, t in _iter_cannon_terms() if t not in CANON]
    assert not bad, (
        '魔動砲 must render as "Magic Cannon" (Larcuss POV) or "Demonic Cannon" '
        f'(Rigüler POV) — never "Magical"/lowercase. Offenders: {bad}'
    )


def test_canon_terms_exist():
    # sanity: the corpus actually uses both faction terms
    seen = {t for _, t in _iter_cannon_terms()}
    assert 'Magic Cannon' in seen
    assert 'Demonic Cannon' in seen
