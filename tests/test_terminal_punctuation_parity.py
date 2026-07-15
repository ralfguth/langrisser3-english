"""Guard: JP terminal punctuation is mandatory in the EN (Ralf, 2026-07-06).

A JP entry ending ？ must reach the player as a question (?, ?!, !?) and one
ending ！ as an exclamation (!, ?!, !?) — softening a shout to "…"/"." or
flattening a question into a statement is a defect, not latitude. Rising-tone
？ on statement-shaped JP (わよ？/かな？/よ？) is rephrased into a natural EN
question (tag questions welcome), never dropped.

Red state (2026-07-06): 13 ？→"." statements + 25 ！→"…"/"." whispers across
the corpus (fixed in the two punctuation-audit commits).

Mechanics: compare the last text character of each entry pair, ignoring the
terminator (FFFE/FFFF), trailing control codes, and closing quotes (the
scen038 flower-spirit line ends !"). Only ？ and ！ are enforced — 。 maps to
., ! or … legitimately and stays editorial.
"""
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts'

_TAIL_JUNK = re.compile(r'(?:<\$[0-9A-F]{4}>|["”」])+$')


def _tail(line):
    s = _TAIL_JUNK.sub('', line.strip())
    return s[-1] if s else ''


def _pairs():
    for jp_path in sorted((SCRIPTS / 'jp').glob('scen*J.txt')):
        en_path = SCRIPTS / 'en' / jp_path.name.replace('J.txt', 'E.txt')
        if not en_path.exists():
            continue
        jp = jp_path.read_text(encoding='utf-8').splitlines()
        en = en_path.read_text(encoding='utf-8').splitlines()
        for lineno, (j, e) in enumerate(zip(jp, en), 1):
            yield f'{en_path.name}:{lineno}', _tail(j), _tail(e)


def test_jp_question_reaches_the_player():
    bad = [loc for loc, jt, et in _pairs() if jt == '？' and et not in '?!']
    assert not bad, f'JP ？ flattened out of the EN: {bad}'


def test_jp_exclamation_reaches_the_player():
    bad = [loc for loc, jt, et in _pairs() if jt == '！' and et not in '!?']
    assert not bad, f'JP ！ softened out of the EN: {bad}'
