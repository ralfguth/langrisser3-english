#!/usr/bin/env python3
"""
test_canonical_names_in_scripts.py — EN scripts must use the canonical glossary
spelling for character/place names.

`lang3_local_docs/names-and-terms.md` is the single source of truth (the JP name
maps to one agreed EN form). A wrong variant in a shipping script is a MECHANICAL
defect, so it belongs to a deterministic gate — not an LLM judgement call
([[feedback_deterministic_vs_llm_gates]], [[reference_names_terms_canon]]). The
guide's romaji (e.g. "Refany", "Flare") is context only, NEVER spelling
([[reference_budianto_walkthrough]]).

Red state (found 2026-06-16 while auditing after using non-canonical names in
chat): scen018E[147] "Flare" (JP フレア = Freya) and scen024E[62] "Elslead"
(JP エルスリード = Elthlead).

Two layers:
- FLAT — tokens that are never a legitimate English word in this corpus, so a
  bare substring hit anywhere in scripts/en is a defect.
- JP-ANCHORED — for variants that *could* be ordinary English (e.g. "Flare"),
  only flag an EN entry whose paired JP actually names the character, so there
  are no false positives.
"""
import glob
import os
import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))
EN = PROJ / 'scripts' / 'en'
JP = PROJ / 'scripts' / 'jp'

# Never valid in an EN script (non-English proper-noun misspellings the glossary
# explicitly rejects, plus the romaji-draft variants of the heroine names).
FLAT_FORBIDDEN = [
    'Flaire',          # フレア → Freya (NOT the wiki "Flaire")
    'Refany', 'Riffany',  # リファニー → Liffany (guide romaji, never canonical)
    'Jügler',          # ジュグラー → Jugler
    'Elslead',         # エルスリード → Elthlead
    'Neref',           # ネルファス → Nelfas
    'Gal Shok',        # ガルシューク → Galshook
    'Kee Shikairo',    # ケー・ツカイロ → Keh Shikairo
    'Khe Shikairo',    # ケー・ツカイロ → Keh Shikairo (NOT the "Khe" transposition)
    'Do-Kahni',        # ド・カーニ → "Do Kahni" (space, NOT a hyphen)
    'deer god',        # シカ神 → "Shika god" (NOT "deer god")
    'Lord Lushiris',   # ルシリス is the GODDESS → "Lady Lushiris" (never "Lord")
    'Siegheart',       # ジークハルト → Sieghart (NOT "Siegheart")
    'Raylim',          # ライリム → Railym (baseline spelling; "Raylim" is the outlier)
    'Master Böser',    # ボーゼル様 → "Lord Böser" (established corpus form; honorific lock)
    'Master Olver',    # オーヴァ様 → "Lord Olver" (established corpus form; honorific lock)
    'Dark Prince',     # 闇の王子 → "Prince of Darkness" (glossary epithet for Böser)
    'dark prince',     # 闇の王子 → "Prince of Darkness" (also the lowercase leak)
    'Demon Tribe',     # 魔族 → "demons" (Ralf 2026-06-23; no Tribe/race/kind/clan variants)
    'demon race',      # 魔族 → "demons"
    'demonkind',       # 魔族 → "demons"
    'demonkin',        # 魔族 → "demons"
    'demon clan',      # 魔族 → "demons"
]

# Flagged only when the paired JP entry names the character (avoids matching the
# ordinary English word). jp_name -> (canonical, [forbidden variants]).
JP_ANCHORED = {
    'フレア': ('Freya', ['Flare']),
    'リファニー': ('Liffany', ['Refany', 'Riffany']),
}


def _entries(path):
    from layout_qa.parser import parse_scenario
    return parse_scenario(path)


def _en_for(jp_path):
    sid = os.path.basename(jp_path)[:-5]  # "scen018J.txt" -> "scen018"
    return EN / f'{sid}E.txt'


def test_no_flat_forbidden_spellings_in_en_scripts():
    violations = []
    files = sorted(glob.glob(str(EN / 'scen*E.txt'))) + [str(EN / 'plotE.txt')]
    for f in files:
        text = Path(f).read_text(encoding='utf-8')
        for tok in FLAT_FORBIDDEN:
            if re.search(rf'\b{re.escape(tok)}\b', text):
                violations.append(f'{os.path.basename(f)}: {tok!r}')
    assert not violations, (
        'Non-canonical name spelling in EN scripts (fix the script, not the '
        f'glossary): {violations}')


def test_jp_anchored_names_use_canonical_spelling():
    violations = []
    for f in sorted(glob.glob(str(JP / 'scen*J.txt'))):
        en_path = _en_for(f)
        if not en_path.exists():
            continue
        jp, en = _entries(Path(f)), _entries(en_path)
        for i in range(min(len(jp), len(en))):
            for jp_name, (canon, wrong) in JP_ANCHORED.items():
                if jp_name in jp[i].raw:
                    for w in wrong:
                        if re.search(rf'\b{re.escape(w)}\b', en[i].raw):
                            violations.append(
                                f'{en_path.name}[{i}] uses {w!r} '
                                f'(JP names {jp_name} → {canon}): {en[i].raw!r}')
    assert not violations, violations


_CODE = re.compile(r'<\$[0-9A-Fa-f]+>')


def _strip_codes(s):
    return _CODE.sub('', s)


def test_raymond_honorific_follows_jp():
    """レイモンド卿/様 (honorific of address) → 'Lord Raymond'; レイモンド子爵
    (the peerage RANK) → 'Viscount Raymond'. A Viscount is addressed as "Lord X"
    in English, so the JP word (rank-mention vs honorific) picks the EN form. The
    rank wins when both appear (子爵様 → Viscount). JP/EN are code-stripped so a
    line-split レイモンド<$FFFC>卿 is still matched.

    Red state (v0.6 review): the corpus tracked the JP in ~61/79 mentions but 12
    diverged (9 'Viscount'←卿, 2 'Lord'←子爵, plus a split レイモンド卿)."""
    violations = []
    for f in sorted(glob.glob(str(JP / 'scen*J.txt'))):
        en_path = _en_for(f)
        if not en_path.exists():
            continue
        jp, en = _entries(Path(f)), _entries(en_path)
        for i in range(min(len(jp), len(en))):
            j, e = _strip_codes(jp[i].raw), _strip_codes(en[i].raw)
            has_rank = 'レイモンド子爵' in j
            has_honorific = ('レイモンド卿' in j) or ('レイモンド様' in j)
            if has_rank and 'Lord Raymond' in e:
                violations.append(
                    f'{en_path.name}[{i}]: JP names 子爵 (rank) but EN says '
                    f'"Lord Raymond" — want "Viscount Raymond"')
            if has_honorific and not has_rank and 'Viscount Raymond' in e:
                violations.append(
                    f'{en_path.name}[{i}]: JP uses 卿/様 (honorific) but EN says '
                    f'"Viscount Raymond" — want "Lord Raymond"')
    assert not violations, violations
