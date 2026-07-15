#!/usr/bin/env python3
"""
test_cutscene_narration_subtitles.py — layout contract for the voiced
narration cutscene subtitles: scen122 (prologue backstory) and scen123
(pre-time-skip cutscene).

These narration entries are EN-only additions: the JP entries are blank
placeholders (a single full-width space) because the JP cutscenes carry
the narration as voice audio alone. That makes the EN layout OUR
contract, not a JP-parity question. Two rules, both from Ralf's
2026-07-06 playtest:

1. NO bottom-align padding. Pushing the text toward the balloon's last
   lines with leading blank `<$FFFC>` lines (introduced in aff517d) does
   not render well in these cutscenes. A narration entry must start
   with text.
   RED state pinned: scen122 [19]-[23] and scen123 [28]/[30] began with
   one or two `<$FFFC>`.

2. scen123 narration balloons must DWELL before the clear. Each of the
   four scen123 narration balloons ends in an empty clear-balloon
   (`<$FFFD>`) so the subtitle leaves the screen; the auto-scroll into
   that empty balloon was firing too early. Every scen123 narration entry
   must therefore end with at least two `<$FFFB>` waits before the
   `<$FFFD><$FFFE>` trailer. RED state pinned: entry [28] had no waits and
   no clear at all. (The exact wait count is a playtest-tuned knob — the
   guard pins the structure, not the timing.)

scen122's narrations scroll continuously without clear-balloons by
design, so rule 2 applies to scen123 only.
"""

import re
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent

JP_BLANK = '　<$FFFE>'
TRAILER_RE = re.compile(r'(<\$FFFB>){2,}<\$FFFD><\$FFFE>$')


def _entries(path: Path):
    return [l for l in path.read_text(encoding='utf-8').split('\n') if l.strip()]


def _narration_indices(scen: str):
    jp = _entries(PROJ / 'scripts' / 'jp' / f'{scen}J.txt')
    en = _entries(PROJ / 'scripts' / 'en' / f'{scen}E.txt')
    assert len(jp) == len(en), f'{scen}: EN/JP entry count mismatch'
    return en, [i for i, l in enumerate(jp) if l == JP_BLANK]


def test_no_bottom_align_padding():
    """Narration subtitles must not start with blank <$FFFC> lines."""
    offenders = []
    for scen in ('scen122', 'scen123'):
        en, idxs = _narration_indices(scen)
        for i in idxs:
            if en[i].startswith('<$FFFC>'):
                offenders.append(f'{scen}[{i}]: {en[i][:50]}…')
    assert not offenders, (
        'bottom-align padding retired (playtest 2026-07-06); '
        'entries still starting with <$FFFC>:\n' + '\n'.join(offenders)
    )


def test_scen123_narrations_wait_before_clear():
    """Each scen123 narration must end with >=2 waits + the clear balloon."""
    en, idxs = _narration_indices('scen123')
    offenders = [
        f'scen123[{i}]: …{en[i][-40:]}'
        for i in idxs
        if not TRAILER_RE.search(en[i])
    ]
    assert not offenders, (
        'scen123 narration balloons must dwell (<$FFFB> x2+) before the '
        '<$FFFD> clear-balloon:\n' + '\n'.join(offenders)
    )
