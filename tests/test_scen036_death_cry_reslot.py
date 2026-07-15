"""Guard the scen036[131]-[147] boss death-cry re-slot (B39, user-ordered).

The run carried a +1 slot misalignment: each EN word-line translated JP[N+1], so
two JP villain lines were lost as roars (体が崩れていく [131] "my body crumbles",
貴様らも道連れに [140] "I'll drag you down with me") and [147] was nonsense
("Humans are…mean…"). The user chose: realign the whole run so EN[N]=JP[N]. This
is the one structural re-slot permitted in the v0.6 fix pass; control-code parity
(one <$FFFE> per entry, no merges) is preserved — only the prose in each slot moves.

Red state (pre-fix): EN[131]="GOOOON!" (roar, no "crumbling"); EN[137]="Curse you…"
(a word-line where JP[137] is the roar ＷＯＯＯ); EN[147]="Humans are…mean…" (nonsense).
"""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.parser import parse_scenario  # noqa: E402

EN = PROJ / 'scripts' / 'en'


def _entries():
    return {e.index: e.raw for e in parse_scenario(EN / 'scen036E.txt')}


def test_scen036_death_cry_run_aligned_to_jp():
    e = _entries()
    # JP word-lines sit in their own slot (EN[N] translates JP[N])
    assert 'crumbling' in e[131].lower()        # JP[131] 体が崩れていく
    assert 'curse' in e[138].lower()            # JP[138] 呪ってやるぞ
    assert 'with me' in e[140].lower()          # JP[140] 貴様らも道連れに
    assert 'strength' in e[145].lower() or 'power' in e[145].lower()  # JP[145] なんという力
    assert 'chaos' in e[146].lower()            # JP[146] カオス様
    assert 'humans' in e[147].lower() or 'mere' in e[147].lower()     # JP[147] 人間ごときに
    # the two slots whose JP is the ＷＯＯＯ roar must NOT carry a displaced word-line
    assert 'curse' not in e[137].lower()        # JP[137] ＷＯＯＯ (roar)
    assert 'strength' not in e[144].lower() and 'power' not in e[144].lower()  # JP[144] roar
