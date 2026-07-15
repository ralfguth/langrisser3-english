#!/usr/bin/env python3
"""wordsplit_audit.py — surface every mid-word <$FFFC> break for LLM review.

This is the deterministic half of an LLM ROUTINE, not a gate. The layout-QA
analyzer only catches a <$FFFC> that splits off a lone letter ("Empir<$FFFC>e");
a split into two multi-letter fragments ("Empi<$FFFC>re") sails through and
renders broken in-game (the trick that pads a line to exactly the tile budget).

Fully separating a real split from a legitimate two-word break is NOT decidable
by a rule — "come<$FFFC>back" concatenates to the real word "comeback" yet
"come back" is a correct two-word break, while "Empi<$FFFC>re" -> "empire" is a
split. Only an LLM (or human) can tell them apart. So this tool does the
mechanical part — list every <$FFFC> with context, FLAG the concat/orphan
suspects — and the routine (skill `langrisser3-script-audit`) has the LLM
eyeball the flagged ones and fix the genuine splits by moving the break to a
word boundary (per the layout-fitting skill).

Usage:
    python3 tools/wordsplit_audit.py                 # all scens, suspects only
    python3 tools/wordsplit_audit.py scen025         # one scen
    python3 tools/wordsplit_audit.py scen025 --all-breaks   # every <$FFFC>
"""
from __future__ import annotations

import argparse
import gzip
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_HERE = Path(__file__).resolve().parent
_BUNDLED_WORDLIST = _HERE / 'layout_qa' / 'data' / 'wordlist.txt.gz'
_SYSTEM_WORDLIST = Path('/usr/share/dict/words')

PROJ = _HERE.parent
DEFAULT_SCRIPTS = PROJ / 'scripts' / 'en'

_CTRL = re.compile(r'<\$[0-9A-Fa-f]{4}>')
_WORDCHAR = "A-Za-zÀ-ÿ'"
_TRAIL = re.compile(f"[{_WORDCHAR}]+$")
_LEAD = re.compile(f"[{_WORDCHAR}]+")
_STANDALONE = frozenset("aio")
_SCEN_ARG = re.compile(r'^(?:scen)?(\d{1,3})(?:[eE])?$')

# Canonical names/terms a generic dictionary misses, so a proper-noun split
# ("Larc<$FFFC>uss" -> "larcuss") is flagged by the concat test too.
_GAME_TERMS = {
    'larcuss', 'larcussia', 'riguler', 'boser', 'dieharte', 'diaharte',
    'altemuller', 'torrand', 'laffel', 'barral', 'gilbert', 'geier', 'emerick',
    'tiaris', 'lewin', 'elwin', 'cherie', 'liana', 'narm', 'chris', 'ledin',
    'freya', 'liffany', 'sophia', 'bahamut', 'megingjardar', 'mjolnir',
    'jugler', 'galshook', 'feraquea', 'kalxath', 'uminin', 'olver', 'coty',
    'langrisser', 'velzeria', 'elthlead', 'alhazard',
}


def load_wordset(extra: Optional[Set[str]] = None) -> Set[str]:
    """Lowercased word set: bundled wordlist (or the system dict) + game terms.

    The bundled `layout_qa/data/wordlist.txt.gz` makes the flag reproducible
    across machines; the system dict is a fallback; an empty set (neither
    present) just disables the concat hint (orphan + --all-breaks still work).
    """
    words: Set[str] = set()
    if _BUNDLED_WORDLIST.exists():
        with gzip.open(_BUNDLED_WORDLIST, 'rt', encoding='utf-8') as f:
            words = {w.strip() for w in f if w.strip()}
    elif _SYSTEM_WORDLIST.exists():
        words = {w.strip().lower()
                 for w in _SYSTEM_WORDLIST.read_text(
                     encoding='utf-8', errors='ignore').splitlines()
                 if w.strip().isalpha()}
    words |= _GAME_TERMS
    if extra:
        words |= {w.lower() for w in extra}
    return words


def _norm(w: str) -> str:
    return w.lower().replace("'", '')


def iter_fffc_breaks(raw: str) -> List[Dict]:
    """Every <$FFFC> in `raw`, with the word fragments adjacent to each break.

    Fragments are the trailing/leading run of word-chars in the *visible* text
    (control codes stripped) on each side — so the protagonist token and other
    codes never count as word characters.
    """
    parts = raw.rstrip('\n').split('<$FFFC>')
    out: List[Dict] = []
    for i in range(len(parts) - 1):
        left_vis = _CTRL.sub('', parts[i])
        right_vis = _CTRL.sub('', parts[i + 1])
        lm = _TRAIL.search(left_vis)
        rm = _LEAD.match(right_vis)
        out.append({
            'left_frag': lm.group(0) if lm else '',
            'right_frag': rm.group(0) if rm else '',
            # Context keeps surrounding control codes VISIBLE (only the split
            # point is rendered as <$FFFC>) so the reader isn't fooled into
            # seeing "bridge.<$FFFD>Is" as a glued "bridge.Is".
            'context': f'{parts[i][-20:]}<$FFFC>{parts[i + 1][:20]}',
        })
    return out


def classify_break(left_frag: str, right_frag: str,
                   wordset: Set[str]) -> Tuple[bool, str]:
    """(suspicious, reason); reason in {'concat', 'orphan', ''}.

    - 'orphan' — a lone lowercase letter (not a/i/o) on one side: the break fell
      inside a word ("Empir<$FFFC>e").
    - 'concat' — both sides >=2 letters AND their concatenation is a real word
      ("Empi"+"re" = "empire"): the break fell inside that word.

    A break with no word-char on a side, or whose two halves are genuine words
    whose join is not a word ("the"+"sword"), is NOT flagged (clean). NOTE: a
    legitimate compound-sounding break ("come"+"back" = "comeback") IS flagged
    by concat — that is intentional; the LLM keeps it. The flag is a hint, not a
    verdict.
    """
    L, R = left_frag, right_frag
    if not L or not R:
        return (False, '')
    for frag in (L, R):
        if len(frag) == 1 and frag.islower() and frag not in _STANDALONE:
            return (True, 'orphan')
    if len(L) >= 2 and len(R) >= 2 and _norm(L + R) in wordset:
        return (True, 'concat')
    return (False, '')


def audit_file(path: Path, wordset: Set[str],
               all_breaks: bool = False) -> List[Dict]:
    """Findings for one scen file (1-based `line`, `reason`, `context`)."""
    findings: List[Dict] = []
    for lineno, raw in enumerate(
            path.read_text(encoding='utf-8').splitlines(), 1):
        if '<$FFFC>' not in raw:
            continue
        for b in iter_fffc_breaks(raw):
            sus, reason = classify_break(b['left_frag'], b['right_frag'], wordset)
            if sus or all_breaks:
                findings.append({
                    'line': lineno, 'reason': reason or 'break',
                    'context': b['context'],
                    'left_frag': b['left_frag'], 'right_frag': b['right_frag'],
                })
    return findings


def _resolve_files(scripts_dir: Path, scenarios: List[str]) -> List[Path]:
    if not scenarios:
        return sorted(scripts_dir.glob('scen*E.txt'))
    out: List[Path] = []
    for arg in scenarios:
        m = _SCEN_ARG.match(arg)
        sid = f'scen{int(m.group(1)):03d}' if m else arg
        out += sorted(scripts_dir.glob(f'{sid}*[Ee].txt'))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog='wordsplit_audit',
        description='List mid-word <$FFFC> break candidates for LLM review.')
    ap.add_argument('scenarios', nargs='*',
                    help='Scenario ids (scen025, 25). Default: all.')
    ap.add_argument('--scripts', type=Path, default=DEFAULT_SCRIPTS,
                    help=f'Source dir. Default: {DEFAULT_SCRIPTS}')
    ap.add_argument('--all-breaks', action='store_true',
                    help='Show every <$FFFC>, not just the flagged suspects.')
    args = ap.parse_args(argv)

    ws = load_wordset()
    files = _resolve_files(args.scripts, args.scenarios)
    if not files:
        sys.stderr.write(f'no scen files in {args.scripts}\n')
        return 3

    total_flagged = 0
    for path in files:
        findings = audit_file(path, ws, all_breaks=args.all_breaks)
        flagged = [f for f in findings if f['reason'] in ('concat', 'orphan')]
        total_flagged += len(flagged)
        if not findings:
            continue
        scen = path.stem.rstrip('Ee')
        print(f'\n{scen}  ({len(flagged)} flagged'
              + (f' / {len(findings)} breaks' if args.all_breaks else '') + ')')
        for f in findings:
            mark = {'concat': '  ⚠ SPLIT?', 'orphan': '  ⚠ ORPHAN'}.get(
                f['reason'], '')
            print(f'   L{f["line"]:<4} {f["context"]!r}{mark}')

    print(f'\n{total_flagged} flagged across {len(files)} file(s). '
          f'These are CANDIDATES — eyeball each: a real split (Empi|re=Empire) '
          f'vs a legit two-word break (come|back). Fix real splits by moving '
          f'the <$FFFC> to a word boundary (see the layout-fitting skill).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
