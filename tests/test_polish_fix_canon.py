"""Guard tests for the POLISH FIX backlog (deterministic items).

Source: polish-fix-prompt.md (digest of archive/docs/20260620_keigo_playthrough_review.md).
These pin the *deterministic* fixes — a wrong word, a dropped name, a banned bit of
modern slang, a typo, a non-canonical spelling — that a brittle string can guard.
Each test names its Red state (the offending corpus form before the fix) so the
Red→Green intent stays legible.

Editorial/voice fixes (Liffany's ojou register, empolado tics, flattened elder voice)
are NOT guarded here — a string test there false-positives (e.g. "Pray" is legitimate
as the verb). Those are judged by reading the line aloud against JP[N].
"""
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts' / 'en'


def _game_scripts():
    # in-game dialogue/narration only — fntsys*/syswin* are UI string tables.
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


# ── P0 — scen028 [68/69], Kirikaze's revenge climax ────────────────────────────
# JP: 殿‥‥お鈴‥‥仇は取ったでござるよ‥‥。 ("My lord… Osuzu… you are avenged at last…").
# Red state: "My lord…your murder has been indemnified…" — "indemnified" is a
# legal/financial term (wrong for 仇は取った = avenged), and the wife's name お鈴
# (Osuzu) was dropped entirely. Both restored.
def test_no_indemnified():
    bad = _scan(re.compile(r'(?i)\bindemn\w*'))
    assert not bad, (
        '仇は取った is "avenged", not the legal term "indemnified" '
        f'(scen028 Kirikaze revenge climax). Offenders: {bad}'
    )


# ── P0 — scen018 [192], the female rival's parting line ────────────────────────
# JP: ‥‥‥‥<$FFFD>強くなったわね‥‥<$F600><$0000>‥‥。 — a soft, rueful "……You have
# grown strong, [Name]……" (わね + trailing ‥‥ = wistful admiration). 強くなった is
# purely "grown strong"; there is NO condemnation in the JP.
# Red state: "…and brutal no less…" — an invented addition that injects a critique
# of brutality the JP does not carry. Removed (editorial-regression guard).
def test_no_invented_brutal_no_less():
    bad = _scan(re.compile(r'(?i)brutal no less'))
    assert not bad, (
        '強くなったわね is wistful admiration ("you have grown strong"), with no '
        f'notion of brutality — "brutal no less" is an invented addition. Offenders: {bad}'
    )


# ── P2 — crude modern slang breaks the fantasy register ────────────────────────
# These are out of register for a high-fantasy script. The JP is a battle cry or
# ordinary expletive, not modern profanity.
# Red state: scen007 [86/92] これでもくらえ ("Take/Eat this!") was "Screw you!";
# scen066 [32] クソッ (Geier's "Damn it!") was "Shit!".
def test_no_screw_you():
    bad = _scan(re.compile(r'(?i)screw you'))
    assert not bad, (
        'これでもくらえ is an attack cry ("Take/Eat this!"), not the slur "Screw you". '
        f'Offenders: {bad}'
    )


def test_no_modern_profanity():
    # クソッ → "Damn it!", not "Shit!"; high-fantasy register has no modern profanity.
    bad = _scan(re.compile(r'(?i)\b(shit|fuck\w*|asshole)\b'))
    assert not bad, (
        'Modern profanity breaks the fantasy register (クソッ → "Damn it!"). '
        f'Offenders: {bad}'
    )


# ── P3 — deterministic standardizations ────────────────────────────────────────
# Typo: scen067 [43] "Jugler joined the part!" → "party".
def test_no_joined_the_part_typo():
    bad = _scan(re.compile(r'joined the part\b(?!y)'))
    assert not bad, f'Typo "joined the part" should be "joined the party". Offenders: {bad}'


# Name canon (names-and-terms.md): リアナ → "Liana", never "Riana".
def test_liana_not_riana():
    bad = _scan(re.compile(r'\bRiana\b'))
    assert not bad, f'リアナ is canonically "Liana", not "Riana". Offenders: {bad}'


# Grove's epithet 死人使いグロブ → "Necromancer Grove" (names-and-terms.md). "Reaper"
# is reserved for Geier's 死神 airship fleet; the collision is confusing.
def test_grove_is_necromancer_not_reaper():
    bad = _scan(re.compile(r'Reaper Grove'))
    assert not bad, (
        '死人使いグロブ → "Necromancer Grove" (canon); "Reaper" is Geier\'s 死神 fleet. '
        f'Offenders: {bad}'
    )


# ロギール砦 is the fort "Rogier" — never the misspelling "Roguil". (The whole place
# is unified to "Fort Rogier".)
def test_rogier_not_roguil():
    bad = _scan(re.compile(r'(?i)\bRoguil\b'))
    assert not bad, f'ロギール is spelled "Rogier", not "Roguil". Offenders: {bad}'


# Opaque romaji: the yelp やんっ → "Ow!" (a pained/startled cry), never the
# untranslated "Yan!".
def test_no_opaque_yan():
    bad = _scan(re.compile(r'\bYan!'))
    assert not bad, f'やんっ is a yelp → "Ow!", not the opaque romaji "Yan!". Offenders: {bad}'


# ── Cenário 01 (scen002) — de-empolado: archaic inversions / courtly diction ───
# User playtest (2026-06-21): the Floating Castle battle read "muito empolado e
# arcaico" — out of nowhere casual childhood friends (Tiaris/Diehärte) and a rough
# general (Varna) spoke in pergaminho-style inversions. The JP here is plain casual
# (もうっ／だ／さ／わけね) or a blunt 貴様 challenge — NOT keigo, NOT archaic. These
# pin the three unambiguous archaic forms removed (the casual-register rewrites are
# editorial and judged by reading aloud, not string-guarded).

# [scen002 43] William, そうなれば、ラーカスの存亡にかかわる ("if it falls, Larcuss's
# very survival is at stake"). Red state: "Should it fall, so falls the Kingdom of
# Larcuss." — a fortune-cookie verb-subject inversion. Now plain: "If it falls, all
# Larcuss falls with it."
def test_no_so_falls_inversion():
    bad = _scan(re.compile(r'so falls the Kingdom'))
    assert not bad, (
        'そうなれば…存亡にかかわる is plain resolve, not the inversion "so falls the '
        f'Kingdom of Larcuss" (scen002 William). Offenders: {bad}'
    )


# [scen002 56] Varna (rough 私が相手だ), 今度は私が相手だ ("this time you face me").
# Red state: "your foe shall be me" — a theatrical inversion. Now "you face me."
def test_no_foe_shall_be_me():
    bad = _scan(re.compile(r'foe shall be me'))
    assert not bad, (
        '今度は私が相手だ is a blunt challenge ("you face me"), not the inversion '
        f'"your foe shall be me" (scen002 Varna). Offenders: {bad}'
    )


# [scen002 111] Varna (rough 貴様, 名は何という). Red state: "What name do you bear?"
# — courtly diction wrong for her register. Now plain "What's your name?".
def test_no_what_name_do_you_bear():
    bad = _scan(re.compile(r'name do you bear'))
    assert not bad, (
        '貴様、名は何という is a rough demand ("What\'s your name?"), not the courtly '
        f'"What name do you bear?" (scen002 Varna). Offenders: {bad}'
    )


# Render glitch: scen039 [179] spells the quiz answer ランス as "L.A.N.C.E!". The "A"
# was the full-width zenkaku glyph <$0650> (used legitimately elsewhere for ア/Ａ in
# roars) while L/N/C/E are ASCII — so it rendered a mismatched, oversized "A" and
# dropped a period. Must be uniform ASCII. (The <$0650> tile stays valid in roars;
# this guards only the LANCE spelling.) Note: _scan replaces <$FFFC> with space, so
# this matches the raw tile code in the answer line.
def test_lance_quiz_uniform_ascii():
    raw = (SCRIPTS / 'scen039E.txt').read_text(encoding='utf-8')
    assert '<$0650>N.C.E' not in raw, (
        'scen039 [179] quiz answer ランス must spell "L.A.N.C.E!" in uniform ASCII; '
        'the full-width <$0650> "Ａ" renders mismatched/oversized.'
    )
