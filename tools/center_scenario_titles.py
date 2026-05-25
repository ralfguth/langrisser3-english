"""Center SCENARIO subtitle text within the 16-tile balloon line.

The in-game SCENARIO title balloon (`scen042-scen121` cutscenes, format
`<$0000><$FFFC>  <$0000>SCENARIO-NN<$FFFC><subtitle><$FFFE>`) is 16 tiles wide.
Subtitles that exceed 16 tiles wrap to a second visible line, breaking the
intended centered layout.

This module computes proper centering padding using:
- `<$0000>` for whole-tile (16px) padding steps
- ASCII space (bigram-absorbed when adjacent to a letter) for half-tile (8px)
  nudges

When the subtitle does not fit on one 16-tile line, it is split at the most
natural break point (comma > 'of'/'the'/'and' > midpoint space) and each
half is centered independently with a `<$FFFC>` newline between.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow tests/scripts to import this with `from tools.center_scenario_titles import ...`
_PROJ = Path(__file__).resolve().parent.parent
if str(_PROJ) not in sys.path:
    sys.path.insert(0, str(_PROJ))

from tools.font_tools import BIGRAM_TILE_MAP, CHAR_TILE_MAP

BALLOON_WIDTH = 16


# ---------------------------------------------------------------------------
# Tile counting (control-code aware)
# ---------------------------------------------------------------------------

def count_tiles(text: str) -> int:
    """Count rendered tiles for a string with optional <$XXXX> control codes.

    Each control code = 1 raw tile. Plain text segments use greedy
    left-to-right bigram packing via BIGRAM_TILE_MAP, falling back to
    single-char tiles via CHAR_TILE_MAP. Unmapped chars are dropped.
    """
    n = 0
    i = 0
    while i < len(text):
        if text[i:i+2] == '<$':
            end = text.find('>', i + 2)
            if end > 0:
                n += 1
                i = end + 1
                continue
        # Plain-text segment up to next code (or end)
        j_end = text.find('<$', i)
        if j_end < 0:
            j_end = len(text)
        chunk = text[i:j_end]
        j = 0
        while j < len(chunk):
            if j + 1 < len(chunk) and (chunk[j], chunk[j+1]) in BIGRAM_TILE_MAP:
                n += 1
                j += 2
            elif chunk[j] in CHAR_TILE_MAP:
                n += 1
                j += 1
            else:
                j += 1   # silently dropped
        i = j_end
    return n


# ---------------------------------------------------------------------------
# Single-line centering
# ---------------------------------------------------------------------------

def center_line(text: str, width: int = BALLOON_WIDTH) -> str:
    """Pad `text` symmetrically so the result is exactly `width` tiles wide.

    Search strategy: enumerate small combinations of (leading <$0000>s,
    leading ASCII space, trailing ASCII space, trailing <$0000>s) and
    pick the combo whose tile count == width AND whose leading/trailing
    padding (in h-units) is most symmetric.

    Raises ValueError if `text` already exceeds `width`.
    """
    naked_tiles = count_tiles(text)
    if naked_tiles > width:
        raise ValueError(
            f'text {text!r} is {naked_tiles} tiles, exceeds width {width}'
        )

    # h-units convention: each <$0000> contributes 2 h-units of padding;
    # an ASCII space adjacent to a letter contributes 1 h-unit (bigram-absorbed)
    candidates = []
    max_codes = (width - naked_tiles) + 1   # never need more
    for l0 in range(max_codes + 1):
        for ls in (0, 1):
            for t0 in range(max_codes + 1):
                for ts in (0, 1):
                    lead = '<$0000>' * l0 + ' ' * ls
                    trail = ' ' * ts + '<$0000>' * t0
                    candidate = lead + text + trail
                    tiles = count_tiles(candidate)
                    if tiles == width:
                        lead_h = l0 * 2 + ls
                        trail_h = t0 * 2 + ts
                        symmetry = abs(lead_h - trail_h)
                        # Prefer fewer codes overall, then most symmetric
                        candidates.append((symmetry, l0 + t0, lead_h, trail_h, candidate))
    if not candidates:
        # Edge case: text fills width exactly — no padding possible
        if naked_tiles == width:
            return text
        raise RuntimeError(f'no centering found for {text!r} (naked={naked_tiles})')

    # Pick lowest symmetry score, ties broken by fewer codes
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][4]


# ---------------------------------------------------------------------------
# Two-line splitting
# ---------------------------------------------------------------------------

_SPLIT_PREFER = (', ', ': ', ' - ')  # high-priority break points
_SPLIT_WORDS = (' of ', ' the ', ' and ', ' in ', ' on ', ' to ')


def split_subtitle(text: str, max_tiles: int = BALLOON_WIDTH) -> tuple[str, str]:
    """Split `text` into two lines, each ≤ max_tiles tiles when centered.

    Prefer punctuation break points (comma, colon); fall back to common
    conjunctions; last resort: space nearest the midpoint.

    Returns (line1, line2) with surrounding whitespace stripped.
    """
    # Pad budget per line: aim for ≤ max_tiles - 2 to leave room for padding
    target_per_line = max_tiles - 2

    # Try comma-class breaks first
    for sep in _SPLIT_PREFER:
        idx = text.find(sep)
        if idx > 0:
            l1 = text[:idx].strip()
            # Drop the trailing punctuation+space; keep the comma on l1
            keep_punct = sep[0]
            l1_with = (text[:idx] + keep_punct).strip()
            l2 = text[idx + len(sep):].strip()
            if (count_tiles(l1_with) <= target_per_line and
                    count_tiles(l2) <= target_per_line):
                return l1_with, l2

    # Try conjunction breaks (start l2 with the conjunction word)
    for word in _SPLIT_WORDS:
        idx = text.find(word)
        if idx > 0:
            l1 = text[:idx].strip()
            l2 = text[idx + 1:].strip()   # keep the word, drop leading space
            if (count_tiles(l1) <= target_per_line and
                    count_tiles(l2) <= target_per_line):
                return l1, l2

    # Fall back: space nearest the midpoint of the string
    mid = len(text) // 2
    # Search outward from midpoint for a space
    for d in range(len(text)):
        for sign in (1, -1):
            i = mid + d * sign
            if 0 < i < len(text) and text[i] == ' ':
                l1 = text[:i].strip()
                l2 = text[i + 1:].strip()
                if (count_tiles(l1) <= target_per_line and
                        count_tiles(l2) <= target_per_line):
                    return l1, l2

    raise ValueError(f'could not split {text!r} into two ≤{target_per_line}-tile lines')


# ---------------------------------------------------------------------------
# Top-level fit
# ---------------------------------------------------------------------------

def fit_subtitle(text: str, width: int = BALLOON_WIDTH) -> str:
    """Return the final subtitle string to be placed after the second
    `<$FFFC>` in the SCENARIO title entry.

    - Single line if `text` fits within (width - 2) tiles after centering
      (leaves a tile of padding margin)
    - Two lines joined by `<$FFFC>` otherwise, each line independently
      centered to `width`
    """
    naked = count_tiles(text)
    # Single line if the naked subtitle itself fits within balloon width
    if naked <= width:
        return center_line(text, width)

    # 2-line split
    l1, l2 = split_subtitle(text, width)
    return center_line(l1, width) + '<$FFFC>' + center_line(l2, width)


# ---------------------------------------------------------------------------
# CLI: apply to scripts
# ---------------------------------------------------------------------------

# Match the full SCENARIO entry. Subtitle is everything between the SECOND
# <$FFFC> and the FIRST <$FFFE>. Subtitle may contain other codes (e.g.
# <$01E2> for the colon tile in scen17, or our <$0000> padding) but never
# <$FFFE> (entry terminator).
SCENARIO_PATTERN = re.compile(
    r'(<\$0000><\$FFFC>[^<]*<\$0000>SCENARIO-[?0-9]+<\$FFFC>)((?:(?!<\$FFFE>).)*?)(<\$FFFE>)'
)


def rewrite_file(path: Path, dry_run: bool = False) -> list[tuple[str, str]]:
    """Re-center every SCENARIO subtitle in `path`. Returns list of
    (old_subtitle, new_subtitle) tuples for changed entries."""
    text = path.read_text(encoding='utf-8')
    changes = []

    def replacer(m: re.Match) -> str:
        head, sub_raw, tail = m.group(1), m.group(2), m.group(3)
        # Strip leading/trailing padding (ASCII spaces and <$0000>) to recover the naked text
        naked = re.sub(r'^(?:\s|<\$0000>)+', '', sub_raw)
        naked = re.sub(r'(?:\s|<\$0000>)+$', '', naked)
        if not naked:
            return m.group(0)
        new_sub = fit_subtitle(naked)
        if new_sub != sub_raw:
            changes.append((sub_raw, new_sub))
        return head + new_sub + tail

    new_text = SCENARIO_PATTERN.sub(replacer, text)
    if changes and not dry_run:
        path.write_text(new_text, encoding='utf-8')
    return changes


def main(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true', help='show changes without writing')
    p.add_argument('paths', nargs='*', help='scen file(s); default = all scen0[4-9]/1[0-2]*E.txt')
    args = p.parse_args(argv[1:])

    if args.paths:
        files = [Path(p) for p in args.paths]
    else:
        # Cutscene files that may contain SCENARIO titles: scen042-scen121
        proj = Path(__file__).resolve().parent.parent
        files = sorted(proj.glob('scripts/en/scen*E.txt'))

    total = 0
    for f in files:
        changes = rewrite_file(f, dry_run=args.dry_run)
        for old, new in changes:
            print(f'{f.name}')
            print(f'  old: {old!r}')
            print(f'  new: {new!r}')
            total += 1
    action = 'would change' if args.dry_run else 'changed'
    print(f'\n{action} {total} subtitle(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
