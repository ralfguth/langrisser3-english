#!/usr/bin/env python3
"""plot_reflow.py — re-wrap PLOT.DAT recap blocks to explicit <$FFFC> lines.

The PLOT.DAT recap box renders 16-tile-wide and uses the same
budget-exhaustion wrap engine as dialogue (it splits words mid-word and
drags leading spaces on auto-wrap). So every visual line needs an explicit
<$FFFC> at a WORD boundary, filling each line to <= 16 tiles. Only <$FFFD>
(scroll pages) must mirror the JP 1:1; <$FFFC> is English-driven and may be
inflated far past the JP count.

This re-wraps each block:
  - the title page (segment before the first <$FFFD>) is left verbatim
    (it carries the <$FFF8NNNN> code and its own centering);
  - every following <$FFFD> page has its existing <$FFFC> stripped and is
    re-wrapped greedily at word boundaries to <= 16 tiles;
  - inline style codes (<$FFF5/6/7>, <$001X>) travel glued to the word
    that follows them;
  - terminators (<$FFFE>, trailing <$FFFF>) are preserved.

Run with --apply to write; default is a dry-run diff of the named blocks.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from text_measure import measure_tiles  # noqa: E402

WIDTH = 16
CODE_RE = re.compile(r'<\$[0-9A-Fa-f]+>')
SPLIT_RE = re.compile(r'(<\$[0-9A-Fa-f]+>|\s+)')
# Story-route markers: each starts a new branch segment and MUST begin a
# fresh line (the engine shows one route at a time — merging two routes on
# a line would leak the alternative's text). Force a <$FFFC> before them.
ROUTE_CODES = {'<$FFF5>', '<$FFF6>', '<$FFF7>'}


def _visible(s: str) -> str:
    return CODE_RE.sub('', s)


def wrap_text(text: str) -> str:
    """Balanced (min-raggedness) word-wrap to <= WIDTH tiles, joined with
    <$FFFC>. Inline codes glue to the following word; story-route codes
    force a line break so routes never share a line."""
    # 1) Build word units: each carries its leading codes + the word, its
    #    visible width, and whether a route code forces a break before it.
    units: list[dict] = []
    pending_codes = ''
    brk = False
    for part in SPLIT_RE.split(text):
        if part == '':
            continue
        if CODE_RE.fullmatch(part):
            if part in ROUTE_CODES:
                brk = True
            pending_codes += part
        elif part.isspace():
            continue
        else:
            units.append({'raw': pending_codes + part, 'word': part,
                          'brk': brk})
            pending_codes = ''
            brk = False
    if pending_codes:
        if units:
            units[-1]['raw'] += pending_codes
        else:
            units.append({'raw': pending_codes, 'word': '', 'brk': False})
    if not units:
        return text

    # 2) Split into runs at forced route breaks; balance each independently.
    runs: list[list[dict]] = []
    cur: list[dict] = []
    for u in units:
        if u['brk'] and cur:
            runs.append(cur)
            cur = []
        cur.append(u)
    if cur:
        runs.append(cur)

    out_lines: list[str] = []
    for run in runs:
        out_lines.extend(_balance(run))
    return '<$FFFC>'.join(out_lines)


def _line_tiles(units: list[dict], i: int, j: int) -> int:
    return measure_tiles(' '.join(u['word'] for u in units[i:j]))


def _balance(units: list[dict]) -> list[str]:
    """Min-raggedness DP over one route-run: minimise sum of slack^2 on every
    line except the last, with a hard <= WIDTH cap. Returns line strings
    (codes preserved)."""
    n = len(units)
    INF = float('inf')
    dp = [0.0] * (n + 1)
    nxt = [n] * (n + 1)
    for i in range(n - 1, -1, -1):
        best = INF
        for j in range(i + 1, n + 1):
            w = _line_tiles(units, i, j)
            if w > WIDTH and j > i + 1:
                break  # adding more only grows the line
            slack = WIDTH - w
            penalty = 0.0 if j == n else slack * slack
            cost = penalty + dp[j]
            if cost < best:
                best = cost
                nxt[i] = j
        dp[i] = best
    lines: list[str] = []
    i = 0
    while i < n:
        j = nxt[i]
        lines.append(' '.join(u['raw'] for u in units[i:j]))
        i = j
    return lines


def reflow_block(block: str) -> str:
    # Separate any trailing terminator(s) so they ride with the last page.
    term = ''
    m = re.search(r'(<\$FFFE>(?:<\$FFFF>)?)\s*$', block)
    if m:
        term = m.group(1)
        block = block[:m.start()]
    pages = block.split('<$FFFD>')
    out_pages = [pages[0]]  # title page verbatim
    for page in pages[1:]:
        body = page.replace('<$FFFC>', ' ')
        out_pages.append(wrap_text(body))
    return '<$FFFD>'.join(out_pages) + term


def fix_emdash(text: str) -> str:
    # Two read better as sentence breaks; the rest become appositive commas.
    text = text.replace('proved futile — Marquis', 'proved futile. Marquis')
    text = text.replace("Barral's army — both", "Barral's army. Both")
    text = text.replace(' — ', ', ')
    return text.replace('—', ',')  # any stray unspaced em-dash


# Route codes that START a new route-conditional run inside a page. Each run
# is shown on its own (a branch the engine selects), so it must fit the 5-line
# scroll window independently.
_RUN_START_RE = re.compile(r'^(?:<\$[0-9A-Fa-f]+>)*<\$FFF[567]>')


def _page_runs(page: str) -> list[list[str]]:
    """Split a reflowed page (FFFC-joined lines) into route-runs. A new run
    begins at any line led by a route code (FFF5/6/7); the leading narrative
    before the first route code is its own run."""
    lines = page.split('<$FFFC>')
    runs: list[list[str]] = []
    cur: list[str] = []
    for ln in lines:
        if _RUN_START_RE.match(ln) and cur:
            runs.append(cur)
            cur = []
        cur.append(ln)
    if cur:
        runs.append(cur)
    return runs


# Layout-QA NARRATION polish gate: a non-final line is "well filled" when it
# reaches 85% of the 16-tile budget (>= 14 tiles) OR ends a sentence (the
# leftover width is then fluidity headroom, not a defect). A non-final line
# below that which does NOT end a sentence is `low_line_usage` — the warning
# that keeps a block out of POLISHED. Matching this rule exactly lets `check`
# drive a block to 100% POLISHED in layout_qa.
_LOW_FILL_MAX = 13           # <= 13 tiles trips the 85%-of-16 threshold
_SENTENCE_FINAL = set('.!?…')


def diagnose_block(block: str) -> list[dict]:
    """Reflow `block` and report every fit/polish violation. Two kinds:

    - ``overflow``: a route-run wraps to > 5 visual lines, spilling a thin
      orphan onto the next scroll page (the user's "<=5 lines/page" rule).
      Measured per route-run so branch segments count independently.
    - ``low_fill``: a non-final page line is <= 13 tiles AND does not end a
      sentence — the layout-QA ``low_line_usage`` warning that blocks
      POLISHED. Measured per FLAT page line (as layout-QA does), where only
      the page's very last line is final-exempt.

    Returns a list of violation dicts; empty list = clean AND POLISHED.
    """
    reflowed = reflow_block(fix_emdash(block))
    violations: list[dict] = []
    pages = reflowed.split('<$FFFD>')
    for pi, page in enumerate(pages):
        if pi == 0:
            continue  # title page
        # 1) overflow: per route-run, > 5 lines.
        for ri, run in enumerate(_page_runs(page)):
            widths = [measure_tiles(_visible(ln)) for ln in run]
            while len(widths) > 1 and widths[-1] == 0:
                widths.pop()  # phantom 0-width line before a route code
            if len(widths) > 5:
                violations.append({
                    'type': 'overflow', 'page': pi, 'run': ri,
                    'lines': len(widths), 'widths': widths,
                })
        # 2) low_fill: per flat page line (layout-QA view), skip the final.
        flat = page.split('<$FFFC>')
        for i, ln in enumerate(flat[:-1]):
            t = measure_tiles(_visible(ln))
            txt = _visible(ln).rstrip()
            if t == 0:
                continue  # phantom line, not rendered
            if t <= _LOW_FILL_MAX and (not txt or txt[-1] not in _SENTENCE_FINAL):
                violations.append({
                    'type': 'low_fill', 'page': pi, 'line': i,
                    'tiles': t, 'text': txt[-24:],
                })
    return violations


def _check(argv) -> int:
    """Read one candidate block line from --file or stdin, reflow it, and
    print a per-page/per-run width report with PASS/FAIL. Exit 0 = clean,
    1 = violations. Lets an editor self-check a rewrite without touching
    scripts/en/plotE.txt."""
    file_args = [a for a in argv if not a.startswith('-')]
    if file_args:
        block = Path(file_args[0]).read_text(encoding='utf-8').strip()
    else:
        block = sys.stdin.read().strip()
    block = block.splitlines()[0] if block else ''
    reflowed = reflow_block(fix_emdash(block))
    pages = reflowed.split('<$FFFD>')
    for pi, page in enumerate(pages):
        tag = 'TITLE' if pi == 0 else f'PAGE {pi}'
        for ri, run in enumerate(_page_runs(page)):
            label = f'  [{tag}]' + (f' run{ri}' if ri else '')
            print(label)
            for ln in run:
                print(f'    {measure_tiles(_visible(ln)):>2}  {ln}')
    viol = diagnose_block(block)
    if viol:
        for v in viol:
            if v['type'] == 'overflow':
                print(f"FAIL  page {v['page']} run {v['run']}: >5 lines "
                      f"({v['lines']})  widths={v['widths']}")
            else:
                print(f"FAIL  page {v['page']} line {v['line']}: low_fill "
                      f"({v['tiles']} tiles, not sentence-final) "
                      f"...{v['text']!r} — fill to >=14 tiles or end a "
                      f"sentence here")
        return 1
    print('PASS  POLISHED: every page <=5 lines; every non-final line '
          'reaches >=14 tiles or ends a sentence')
    return 0


def main(argv):
    if argv and argv[0] == 'check':
        return _check(argv[1:])
    path = Path('scripts/en/plotE.txt')
    raw_lines = path.read_text(encoding='utf-8').splitlines()
    # Keep blank-line layout: operate only on non-blank entry lines.
    apply = '--apply' in argv
    want = [a for a in argv if a.isdigit()]
    out_lines = []
    blk_idx = 0
    for line in raw_lines:
        if not line.strip():
            out_lines.append(line)
            continue
        blk_idx += 1
        fixed = fix_emdash(line)
        new = reflow_block(fixed)
        out_lines.append(new)
        if not apply and (not want or str(blk_idx) in want):
            print(f'===== BLOCK {blk_idx} =====')
            for seg in new.split('<$FFFD>'):
                print('  [PAGE]')
                for ln in seg.split('<$FFFC>'):
                    vis = _visible(ln)
                    print(f'    {measure_tiles(vis):>2}  {ln}')
    if apply:
        path.write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
        print(f'wrote {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
