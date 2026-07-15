"""Guard: dialogue stutters must keep their hyphen ('M-my arm', not 'M my arm').

Surfaced by the font-bigram-expansion work — decoding the new encoder revealed
scen007 entry 85 rendered as 'M my arm…' (two broken words) where the JP
う、腕が‥‥ (a pained grunt + 'arm') intends a stammer. A dropped hyphen turns
the stutter into nonsense.

Detection signature (zero false positives on the current scripts): a lone
capital letter used as its own word, immediately followed (across a space OR a
comma) by a lowercase word that STARTS WITH THE SAME LETTER. The JP marks these
stammers as 「mora、same-mora-word」 (e.g. な、情けねぇ / バ、バカな); the EN must
mirror that with a hyphen, not leave the onset orphaned.

  * SPACE form  — lone CONSONANT + ' '  + same-initial LOWERCASE word ('M my arm').
    Consonant-only so the legitimate 'I insist' (subject 'I' + verb) is exempt;
    lowercase-only so the sleeping 'Zzz' ('Z Z Z', a capital follows) is exempt.
  * COMMA form  — lone capital + ', ' + same-initial word, EITHER case
    ('H, how', 'A, absurd', and the proper-noun 'C, Coty'). Excludes 'I,' so the
    legitimate aside 'I, in my opinion,' is exempt.

The Saturn 'Z' button ('Z and select') is a different letter, so it never trips.

Red state (pre-fix): scen007 #85 'M my arm…' + the 10 comma stammers trip it.
Green: each reads 'X-xword'.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EN = REPO / "scripts" / "en"

CTRL = re.compile(r"<\$[0-9A-Fa-f]*>")
STUTTER_SPACE = re.compile(r"(?:^|[ (\"])([B-DF-HJ-NP-TV-Z]) (?=([a-z]))")
STUTTER_COMMA = re.compile(r"(?:^|[ (\"])([A-HJ-Z]), (?=([A-Za-z]))")  # any cap but 'I'


def _entries(p):
    return p.read_text(encoding="utf-8", errors="replace").split("<$FFFE>")


def _scripts():
    return sorted(EN.glob("scen*E.txt")) + [EN / "plotE.txt"]


def test_no_dropped_hyphen_stutter():
    bad = []
    for f in _scripts():
        if not f.exists():
            continue
        for idx, ent in enumerate(_entries(f)):
            vis = CTRL.sub(" ", ent).replace("\n", " ").replace("\t", " ")
            for pat in (STUTTER_SPACE, STUTTER_COMMA):
                for m in pat.finditer(vis):
                    if m.group(1).lower() == m.group(2).lower():
                        ctx = vis[m.start():m.start() + 18].strip()
                        bad.append((f.name, idx, ctx))
    assert not bad, (
        "dropped-hyphen stutters (write 'X-xword', not 'X xword' / 'X, xword'):\n"
        + "\n".join(f"  {fn} #{i}: {ctx!r}" for fn, i, ctx in bad)
    )


def test_scen007_arm_stutter_is_hyphenated():
    """JP[85] う、腕が‥‥ (pained grunt + 'arm') -> the EN stammer keeps its hyphen."""
    assert _entries(EN / "scen007E.txt")[85].strip() == "M-my arm…"
