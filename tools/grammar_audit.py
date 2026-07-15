#!/usr/bin/env python3
"""grammar_audit.py — deterministic grammar/punctuation flag for the EN scripts.

A 0-dependency static linter for `scripts/en/*.txt`. It is the *deterministic*
companion to a periodic NLP grammar pass (LanguageTool/Codex): it encodes only
the mechanical defect classes that a regex/wordlist can decide for THIS corpus
with ~0 false positives, so it can run in `pytest` as a permanent regression
gate next to `layout_qa` and `wordsplit_audit`.

What it CANNOT decide — comma-after-vocative, comma splices, verb parallelism,
a missing article/verb — needs sentence parsing and would false-positive on the
game's invented vocabulary (names, onomatopoeia). Those stay an LLM/manual pass
driven by the human grammar report; this tool deliberately leaves them out.

Severities
  error    a clear mechanical defect — the corpus gate FAILS on any of these.
  warning  a review candidate (style / context-dependent) — reported, not gated.

Rules (calibrated against the corpus, FP-checked):
  [error]   semicolon              ';' anywhere (banned punctuation)
  [error]   comma_no_space        ','  glued to a letter            (ATK,DEF)
  [error]   space_before_punct     space before , ! ?               (word ,)
  [error]   space_before_ellipsis  letter, space, '…'  (stray)      (escape …)
  [error]   open_compound          open form of a closed/hyphen     (gate keeper)
  [error]   dup_func_word          doubled function word            (I I am)
  [warning] ellipsis_comma         '…,' or ',…'                     (Oh…, goddess)
  [warning] intro_adverb_comma     'Meanwhile …' missing its comma
  [warning] confusable             quiet/quite style confusion

Control codes (`<$FFFC>` …) are replaced by a space before the compound/word
rules run, so a wrap never glues two words; the punctuation rules read the raw
text (a comma before `<$FFFC>` ends a visual line and is NOT a defect).

Usage
  python3 tools/grammar_audit.py                 # whole corpus, errors+warnings
  python3 tools/grammar_audit.py scen100 plot    # selected files
  python3 tools/grammar_audit.py --severity error
  python3 tools/grammar_audit.py --json
Exit code is 1 when any error-level finding exists (so CI/pytest can gate).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional

_HERE = Path(__file__).resolve().parent
PROJ = _HERE.parent
DEFAULT_SCRIPTS = PROJ / 'scripts' / 'en'

_CTRL = re.compile(r'<\$[0-9A-Fa-f]{4,8}>')
_L = 'A-Za-zÀ-ÿ'  # "letter" incl. accented forms used in names (Diehärte, Rigüler)

# --- open / mis-joined compounds: open form -> canonical form ----------------
# Conservative: only forms that have no legitimate open reading in this corpus.
OPEN_COMPOUND = {
    'gate keeper': 'gatekeeper',
    'flood gate': 'floodgate',
    'so called': 'so-called',
    'run of the mill': 'run-of-the-mill',
    'hard pressed': 'hard-pressed',
    'ill mannered': 'ill-mannered',
    'shape shifting': 'shape-shifting',
    'shape shifter': 'shape-shifter',
    'father in law': 'father-in-law',
    'mother in law': 'mother-in-law',
    'brother in law': 'brother-in-law',
    'sister in law': 'sister-in-law',
}

# Function words that are virtually never legitimately doubled. Reduplicated
# onomatopoeia / emphasis ("Heh heh", "Ow ow", "Now now") is NOT in this set, so
# it is never flagged; an accidental "I I am" is. Words that DO double validly
# are deliberately excluded: "that" ("now that that's settled"), "so" ("so so"),
# "do" ("I do do my best"), "had" (past perfect), "but" (often a stutter b-but).
DUP_FUNC_WORDS = {
    'i', 'a', 'an', 'the', 'to', 'of', 'and', 'is', 'it', 'in', 'on', 'we',
    'you', 'he', 'she', 'they', 'this', 'was', 'will', 'for',
    'with', 'as', 'at', 'be', 'by', 'or', 'our', 'my', 'your', 'his', 'her',
    'their', 'are', 'am', 'if',
}

# Conjunctive adverbs that take a comma when they open a sentence. "However" is
# left out on purpose ("However much…" needs no comma).
INTRO_ADVERBS = ('Otherwise', 'Henceforth', 'Meanwhile', 'Therefore',
                 'Furthermore', 'Moreover', 'Nevertheless', 'Besides')

# --- outright misspellings: wrong form -> correct form -----------------------
# Single- or multi-word keys, matched on the lowercased visible text with word
# boundaries. Only forms that are NEVER correct in this corpus (FP-safe): "en
# garde" is the fencing call ("en guard" is always wrong); "guard" alone is a
# real word and is not in the list.
MISSPELLINGS = {
    'surrond': 'surround',
    'surronded': 'surrounded',
    'godess': 'goddess',
    'en guard': 'en garde',
}

# quiet/quite confusion: 'quiet' before one of these almost always means 'quite'.
_QUIET_NEXT = ('unusual', 'good', 'sure', 'certain', 'right', 'simply',
               'frankly', 'literally', 'nice', 'well', 'a', 'the')

_RE_SEMICOLON = re.compile(r';')
_RE_COMMA_NO_SPACE = re.compile(rf',(?=[{_L}])')
_RE_SPACE_BEFORE_PUNCT = re.compile(r' (?=[,!?])')
_RE_SPACE_BEFORE_ELLIPSIS = re.compile(rf'(?<=[{_L}]) …')
_RE_DUP = re.compile(rf'\b([{_L}]+) \1\b', re.IGNORECASE)
_RE_ELLIPSIS_COMMA = re.compile(r'…,|,…')
_RE_INTRO = re.compile(r'^(' + '|'.join(INTRO_ADVERBS) + r') (?![,])')
_RE_QUIET = re.compile(r'\bquiet (?=' + '|'.join(_QUIET_NEXT) + r')\b')
# possessive "its" can never precede a subject/object pronoun -> contraction "it's".
_RE_ITS_CONTRACTION = re.compile(
    r"\bits (?=(?:you|i|we|he|she|they|me|him|them|us)\b)", re.IGNORECASE)
# segment breaks: structural codes that start a new visual sentence/paragraph
_RE_SEGSPLIT = re.compile(r'<\$FFF[BD]>')


@dataclass
class Finding:
    file: str
    line: int
    rule: str
    severity: str
    text: str
    suggestion: str = ''

    def as_dict(self) -> dict:
        return asdict(self)


def _clean(s: str) -> str:
    """Control codes -> single space, whitespace collapsed (for word rules)."""
    return re.sub(r'\s+', ' ', _CTRL.sub(' ', s)).strip()


def _ctx(raw: str, pos: int, span: int = 0, width: int = 14) -> str:
    return raw[max(0, pos - width):pos + span + width]


def iter_line_findings(raw: str, fname: str, lineno: int) -> List[Finding]:
    out: List[Finding] = []
    if not raw.strip():
        return out
    vis = _clean(raw)
    low = vis.lower()

    for m in _RE_SEMICOLON.finditer(raw):
        out.append(Finding(fname, lineno, 'semicolon', 'error',
                           _ctx(raw, m.start(), 1), 'replace ; with . or , (semicolons are banned)'))
    for m in _RE_COMMA_NO_SPACE.finditer(raw):
        out.append(Finding(fname, lineno, 'comma_no_space', 'error',
                           _ctx(raw, m.start(), 1), 'insert a space after the comma'))
    for m in _RE_SPACE_BEFORE_PUNCT.finditer(raw):
        out.append(Finding(fname, lineno, 'space_before_punct', 'error',
                           _ctx(raw, m.start(), 1), 'remove the space before punctuation'))
    for m in _RE_SPACE_BEFORE_ELLIPSIS.finditer(raw):
        out.append(Finding(fname, lineno, 'space_before_ellipsis', 'error',
                           _ctx(raw, m.start(), 2), "remove the stray space before '…'"))
    for bad, good in OPEN_COMPOUND.items():
        for m in re.finditer(r'\b' + re.escape(bad) + r'\b', low):
            out.append(Finding(fname, lineno, 'open_compound', 'error',
                               vis[max(0, m.start() - 6):m.end() + 6],
                               f'{bad} -> {good}'))
    for m in _RE_DUP.finditer(vis):
        if m.group(1).lower() in DUP_FUNC_WORDS:
            out.append(Finding(fname, lineno, 'dup_func_word', 'error',
                               m.group(0), 'remove the doubled word'))
    for bad, good in MISSPELLINGS.items():
        for m in re.finditer(r'\b' + re.escape(bad) + r'\b', low):
            out.append(Finding(fname, lineno, 'misspelling', 'error',
                               vis[max(0, m.start() - 6):m.end() + 6],
                               f'{bad} -> {good}'))
    for m in _RE_ITS_CONTRACTION.finditer(vis):
        out.append(Finding(fname, lineno, 'its_contraction', 'error',
                           vis[max(0, m.start() - 4):m.start() + 12],
                           "possessive 'its' before a pronoun -> contraction \"it's\""))

    # --- warnings ---
    for m in _RE_ELLIPSIS_COMMA.finditer(raw):
        out.append(Finding(fname, lineno, 'ellipsis_comma', 'warning',
                           _ctx(raw, m.start(), 1, 8), "review '…,'/',…' sequence"))
    for m in _RE_QUIET.finditer(low):
        out.append(Finding(fname, lineno, 'confusable', 'warning',
                           vis[max(0, m.start() - 4):m.start() + 14], "quiet -> quite?"))
    for seg in _RE_SEGSPLIT.split(raw):
        sv = _clean(seg)
        m = _RE_INTRO.match(sv)
        if m:
            out.append(Finding(fname, lineno, 'intro_adverb_comma', 'warning',
                               sv[:32], f'{m.group(1)} -> {m.group(1)},'))
    return out


def audit_file(path: Path) -> List[Finding]:
    name = path.name
    out: List[Finding] = []
    for ln, raw in enumerate(path.read_text(encoding='utf-8').split('\n'), 1):
        out.extend(iter_line_findings(raw, name, ln))
    return out


def _resolve(args: Iterable[str], scripts: Path) -> List[Path]:
    if not args:
        return sorted(scripts.glob('*.txt'))
    paths: List[Path] = []
    for a in args:
        a = a.strip()
        cands = []
        if re.fullmatch(r'\d{1,3}', a):
            cands.append(scripts / f'scen{int(a):03d}E.txt')
        for stem in (a, a.rstrip('E'), a + 'E'):
            cands.append(scripts / f'{stem}.txt')
        hit = next((c for c in cands if c.exists()), None)
        if hit:
            paths.append(hit)
        else:
            print(f'warning: no file for {a!r}', file=sys.stderr)
    return paths


def audit(args: Iterable[str] = (), scripts: Path = DEFAULT_SCRIPTS) -> List[Finding]:
    out: List[Finding] = []
    for p in _resolve(list(args), scripts):
        out.extend(audit_file(p))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='*', help='scen ids / file stems (default: all)')
    ap.add_argument('--scripts', default=str(DEFAULT_SCRIPTS))
    ap.add_argument('--severity', choices=('error', 'warning', 'all'), default='all')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    findings = audit(a.files, Path(a.scripts))
    if a.severity != 'all':
        findings = [f for f in findings if f.severity == a.severity]

    errors = [f for f in findings if f.severity == 'error']
    if a.json:
        print(json.dumps([f.as_dict() for f in findings], ensure_ascii=False, indent=2))
    else:
        by_rule: dict = {}
        for f in findings:
            by_rule.setdefault((f.severity, f.rule), []).append(f)
        for (sev, rule), fs in sorted(by_rule.items()):
            print(f'\n[{sev}] {rule}: {len(fs)}')
            for f in fs:
                sg = f'   ⇒ {f.suggestion}' if f.suggestion else ''
                print(f'   {f.file}:{f.line}  {f.text!r}{sg}')
        print(f'\n{len(errors)} error(s), {len(findings) - len(errors)} warning(s) '
              f'across {len(set(f.file for f in findings))} file(s).')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
