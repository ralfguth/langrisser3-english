#!/usr/bin/env python3
"""pair_dump.py — entry-by-entry side-by-side JP|EN view for a scen.

Reads ``scripts/jp/scenNNNJ.txt`` and ``scripts/en/scenNNNE.txt`` (after the
header strip), aligns by ``parse_script_file`` entry index, and writes
``e001|J: ...`` / ``    |E: ...`` to stdout.

Usage:
    python3 tools/pair_dump.py scen031              # one scenario
    python3 tools/pair_dump.py 31                   # numeric form
    python3 tools/pair_dump.py scen031 > out.txt    # redirect for review
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from d00_tools import parse_script_file

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_JP = ROOT / 'scripts' / 'jp'
SCRIPTS_EN = ROOT / 'scripts' / 'en'


def _scen_num(arg: str) -> int:
    m = re.fullmatch(r'(?:scen)?0*(\d+)', arg, flags=re.IGNORECASE)
    if not m:
        raise SystemExit(f'cannot parse scen number from {arg!r}')
    return int(m.group(1))


def dump(scen: int, out=sys.stdout) -> None:
    jp_path = SCRIPTS_JP / f'scen{scen:03d}J.txt'
    en_path = SCRIPTS_EN / f'scen{scen:03d}E.txt'
    if not jp_path.exists():
        raise SystemExit(f'missing {jp_path}')
    if not en_path.exists():
        raise SystemExit(f'missing {en_path}')
    jp = parse_script_file(jp_path)
    en = parse_script_file(en_path)
    print(f'# scen{scen:03d}  JP={len(jp)}  EN={len(en)}'
          f'{"  Δ=" + str(len(en) - len(jp)) if len(jp) != len(en) else ""}',
          file=out)
    n = max(len(jp), len(en))
    for i in range(n):
        j = jp[i] if i < len(jp) else '(NO JP)'
        e = en[i] if i < len(en) else '(NO EN)'
        print(f'e{i+1:03d}|J: {j}', file=out)
        print(f'    |E: {e}', file=out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('scens', nargs='+', help='Scenario numbers (e.g. scen031, 31).')
    args = p.parse_args()
    for raw in args.scens:
        dump(_scen_num(raw))
    return 0


if __name__ == '__main__':
    sys.exit(main())
