#!/usr/bin/env python3
"""fix_wrap.py — Deterministic mid-word wrap fixer for Langrisser III dialogue.

Ported from ~/translation_analysis/balloon_viewer/tiles/parser.go::CheckWordWraps.

For each dialogue entry:
1. Simulate tile-by-tile rendering at the entry's balloon width (12 or 16)
2. Find every mid-word wrap point
3. Try to insert <$FFFC> at the last space BEFORE each wrap point
4. Validate: final balloon must be ≤ 5 lines AND no new mid-word wraps
5. If validation passes → emit fixed text. Else → flag for manual review.

Non-destructive: only inserts <$FFFC> at existing space positions. Entry text
characters are never removed. Failed fixes leave the entry untouched.

Usage:
    python3 tools/fix_wrap.py scen001E.txt          # dry-run one file
    python3 tools/fix_wrap.py --apply scen001E.txt  # write changes
"""
import argparse
import re
import sys
from pathlib import Path
from dataclasses import dataclass

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from font_tools import BIGRAM_TILE_MAP, CHAR_TILE_MAP
from balloon_opcodes import parse_d00_opcodes, BalloonType

PROJ = SCRIPT_DIR.parent
SCRIPTS_DIR = PROJ / 'scripts' / 'en'
D00_PATH   = PROJ / 'build' / 'd00_jp.dat'

# Escape-sequence pattern for <$XXXX> control codes
CTRL_RE = re.compile(r'<\$[0-9A-Fa-f]+>')
# Token that must be excluded when simulating word-wrap (all control codes)
FFFC = '<$FFFC>'
FFFE = '<$FFFE>'
FFFD = '<$FFFD>'
FFFF = '<$FFFF>'

MAX_LINES_PER_BALLOON = 5


@dataclass
class WrapIssue:
    line: int
    tile_pos: int
    char_index: int  # position in the balloon's rendered text
    context: str


def tokenize(text: str) -> list:
    """Greedy bigram tokenize. Returns list of (chars, tile_count) tuples."""
    # Replace '...' with ellipsis before tokenizing
    text = text.replace('...', '…')
    tokens = []
    i = 0
    while i < len(text):
        if i + 1 < len(text) and (text[i], text[i+1]) in BIGRAM_TILE_MAP:
            tokens.append((text[i:i+2], 1))
            i += 2
        elif text[i] in CHAR_TILE_MAP:
            tokens.append((text[i], 1))
            i += 1
        else:
            # Unmapped char — skip (encoder drops it, but track for tile count 0)
            i += 1
    return tokens


def simulate_render(text: str, max_tiles: int, name_tiles: int = 0):
    """Simulate tile-by-tile rendering. Text may contain <$FFFC> (line break)
    and <$FFFD> (new balloon). Returns (balloons, issues).

    balloons: list of list-of-line-strings (the rendered content per balloon)
    issues: list of WrapIssue for mid-word wraps
    """
    balloons_text = text.split(FFFD)
    balloons_render = []
    issues = []

    for bi, balloon_text in enumerate(balloons_text):
        # Strip any other control codes that are not line breaks or balloon-end.
        # FFFE should have been stripped by caller. <$XXXX> with other codes get
        # treated as zero-width tokens (their tile impact varies by game state).
        # For this pass, we strip them to simulate visible text flow.
        segments = balloon_text.split(FFFC)

        lines = [[]]  # lines[line_num] = list of chars rendered on that line
        line_num = 0
        tile_pos = 0
        line_limit = max_tiles - name_tiles if (bi == 0 and name_tiles) else max_tiles

        for si, seg in enumerate(segments):
            if si > 0:
                # Explicit FFFC — advance line
                line_num += 1
                lines.append([])
                tile_pos = 0
                line_limit = max_tiles  # name only on first line of first balloon

            # Strip other control codes (render as empty)
            seg_clean = CTRL_RE.sub('', seg)

            tokens = tokenize(seg_clean)
            for ti, (chars, tcount) in enumerate(tokens):
                if tile_pos + tcount > line_limit:
                    # Would overflow — wrap now
                    # Check if wrap is mid-word
                    prev = tokens[ti-1][0] if ti > 0 else ''
                    mid_word = (ti > 0
                                and (not prev.endswith(' '))
                                and (not chars.startswith(' ')))
                    if mid_word:
                        # Compute approx char index within balloon rendered text
                        rendered = ''.join(''.join(ln) for ln in lines)
                        issues.append(WrapIssue(
                            line=line_num, tile_pos=tile_pos,
                            char_index=len(rendered),
                            context=f'{prev[-4:]}|{chars[:4]}',
                        ))
                    line_num += 1
                    lines.append([])
                    tile_pos = 0
                    line_limit = max_tiles
                lines[-1].append(chars)
                tile_pos += tcount

        balloons_render.append([''.join(l) for l in lines])

    return balloons_render, issues


def total_line_count(balloons_render: list) -> int:
    """Max line count across all balloons."""
    return max((len(b) for b in balloons_render), default=0)


def any_balloon_overflows(balloons_render: list) -> bool:
    return any(len(b) > MAX_LINES_PER_BALLOON for b in balloons_render)


def try_fix(entry_text: str, max_tiles: int, name_tiles: int = 0):
    """Try to insert FFFC at safe positions to eliminate mid-word wraps.

    Returns (fixed_text_or_none, list_of_messages).
    If fix is not safe (creates >5 lines or fails validation), returns (None, reasons).
    """
    text = entry_text
    for iteration in range(20):   # safety cap
        balloons, issues = simulate_render(text, max_tiles, name_tiles)
        if not issues:
            # All good. If iteration > 0, we made fixes.
            return text, (['applied'] if iteration > 0 else ['no-issues'])

        # Find the FIRST issue and try to fix it.
        first = issues[0]
        # Reconstruct the "flat" text minus control codes to find char mappings
        # is complex. Simpler: split by FFFD balloons and FFFC lines, then find
        # the last ' ' BEFORE the wrap column position in the relevant segment.
        fix_applied = False

        # Navigate to the balloon + line that had the first wrap
        balloon_idx_hit = 0
        lines_before_hit = 0
        for bi, br in enumerate(balloons):
            if lines_before_hit + len(br) > first.line:
                balloon_idx_hit = bi
                target_line_in_balloon = first.line - lines_before_hit
                break
            lines_before_hit += len(br)
        else:
            return None, [f'cannot locate wrap location (line {first.line})']

        # Get the balloon's source text (from text split by FFFD)
        balloons_src = text.split(FFFD)
        if balloon_idx_hit >= len(balloons_src):
            return None, ['balloon index out of range']
        balloon_src = balloons_src[balloon_idx_hit]

        # Find the Nth occurrence of FFFC within this balloon to locate the line
        # that we're fixing (target_line_in_balloon).
        # The wrap is at tile_pos within THAT line.
        segments_with_fffc = balloon_src.split(FFFC)
        if target_line_in_balloon >= len(segments_with_fffc):
            # The line is AUTO-wrapped past an existing FFFC; find which segment
            # corresponds by simulating.
            # Fallback: operate on the last segment.
            seg_idx = len(segments_with_fffc) - 1
        else:
            seg_idx = target_line_in_balloon
        target_seg = segments_with_fffc[seg_idx]

        # Simulate rendering within target_seg to find the char position where
        # the wrap would occur. Need to account for prior auto-wraps in this seg.
        # For simplicity: find the FIRST auto-wrap point in target_seg that
        # matches the tile_pos. Then find last ' ' before that char in target_seg.
        # Walk tile-by-tile in target_seg_clean.
        target_clean = CTRL_RE.sub('', target_seg)
        tokens = tokenize(target_clean)
        # Within this segment, which token index causes the wrap?
        # Re-simulate just this segment to locate.
        effective_limit_line0 = max_tiles - (name_tiles if (balloon_idx_hit == 0 and seg_idx == 0) else 0)
        local_tp = 0
        local_limit = effective_limit_line0
        char_pos_in_seg = 0
        wrap_char_pos = None
        for ti, (chars, tcount) in enumerate(tokens):
            if local_tp + tcount > local_limit:
                # Wrap point here. Check if this matches our first issue.
                wrap_char_pos = char_pos_in_seg
                break
            local_tp += tcount
            char_pos_in_seg += len(chars)

        if wrap_char_pos is None:
            # No wrap found in this segment — can't fix this way
            return None, [f'could not locate wrap position in segment']

        # Find last space BEFORE wrap_char_pos in target_seg (note: target_seg
        # may contain control codes, so we need to work with target_seg directly
        # but account for control codes when mapping char_pos).
        # Build a map from "clean char position" → "target_seg position"
        pos_map = []
        i = 0
        while i < len(target_seg):
            if target_seg[i] == '<' and target_seg[i:i+2] == '<$':
                end = target_seg.find('>', i)
                if end >= 0:
                    i = end + 1
                    continue
            pos_map.append(i)
            i += 1

        if wrap_char_pos >= len(pos_map):
            return None, ['wrap position beyond clean text length']

        wrap_pos_in_seg = pos_map[wrap_char_pos]
        # Find last ' ' in target_seg BEFORE wrap_pos_in_seg
        last_space = target_seg.rfind(' ', 0, wrap_pos_in_seg)
        if last_space < 0:
            return None, [f'no safe space found before mid-word wrap at pos {wrap_pos_in_seg}']

        # Replace this space with FFFC
        new_seg = target_seg[:last_space] + FFFC + target_seg[last_space+1:]
        segments_with_fffc[seg_idx] = new_seg
        balloons_src[balloon_idx_hit] = FFFC.join(segments_with_fffc)
        text = FFFD.join(balloons_src)
        fix_applied = True

        if not fix_applied:
            return None, ['no fix applied in iteration']

    return None, ['exceeded iteration cap']


def process_file(script_path: Path, opcodes_map: dict, apply: bool = False):
    """Process a script file and attempt to fix mid-word wraps."""
    text = script_path.read_text(encoding='utf-8')
    # Parse entries
    entries = []
    buf = []
    for line in text.splitlines(keepends=True):
        buf.append(line)
        stripped = line.strip()
        if stripped.endswith(FFFF) or stripped.endswith(FFFE):
            entries.append(''.join(buf))
            buf = []
    trailing = ''.join(buf)

    section_idx = _section_index(script_path.name)
    sec_opcodes = opcodes_map.get(section_idx, {}) if section_idx is not None else {}

    total_entries = 0
    total_issues_before = 0
    fixed_count = 0
    flagged_count = 0
    flagged_entries = []
    applied_entries = []

    entry_idx = -1
    for raw_entry in entries:
        stripped = raw_entry.strip()
        if FFFF in stripped:
            entry_idx += 1
            continue  # name entry — not dialogue
        if FFFE not in stripped:
            continue  # header or empty
        entry_idx += 1
        total_entries += 1

        # Strip the terminator for wrap analysis
        entry_text = raw_entry.rstrip()
        if entry_text.endswith(FFFE):
            body = entry_text[:-len(FFFE)]
        else:
            body = entry_text

        # Determine balloon type
        info = sec_opcodes.get(entry_idx)
        if info is None:
            # Fallback: narration if section has no opcodes, otherwise leading-space heuristic
            if section_idx == 0 or not sec_opcodes:
                max_tiles = 16
                name_tiles = 0
            elif body.startswith(' '):
                max_tiles = 12
                name_tiles = 4  # rough average — placeholder
            else:
                max_tiles = 12
                name_tiles = 0
        elif info.btype == BalloonType.NARRATION:
            max_tiles = 16
            name_tiles = 0
        elif info.btype == BalloonType.PORTRAIT:
            max_tiles = 12
            name_tiles = 4  # placeholder; real speaker name would be resolved from context
        else:  # PORT_CONT
            max_tiles = 12
            name_tiles = 0

        # Check current wrap issues
        _, issues_before = simulate_render(body, max_tiles, name_tiles)
        if not issues_before:
            continue  # nothing to fix
        total_issues_before += len(issues_before)

        # Try fix
        fixed, msgs = try_fix(body, max_tiles, name_tiles)
        if fixed is not None:
            # Validate: balloons_render must not overflow 5 lines, no new issues
            new_balloons, new_issues = simulate_render(fixed, max_tiles, name_tiles)
            if new_issues:
                flagged_count += 1
                flagged_entries.append((entry_idx, body, len(issues_before), 'fix created new mid-word wraps'))
                continue
            if any_balloon_overflows(new_balloons):
                flagged_count += 1
                flagged_entries.append((entry_idx, body, len(issues_before), 'fix caused balloon >5 lines'))
                continue
            # Safe fix
            fixed_count += 1
            applied_entries.append((entry_idx, body, fixed, len(issues_before)))
        else:
            flagged_count += 1
            flagged_entries.append((entry_idx, body, len(issues_before), ';'.join(msgs)))

    return {
        'total_entries': total_entries,
        'total_issues_before': total_issues_before,
        'fixed': fixed_count,
        'flagged': flagged_count,
        'applied_entries': applied_entries,
        'flagged_entries': flagged_entries,
    }


def _section_index(filename: str) -> int:
    """scen002E.txt → 1. fntsys and plotE are not sections."""
    m = re.match(r'scen(\d+)E?\.txt', filename, re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1)) - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', help='Script filename under scripts/en/ (e.g. scen001E.txt)')
    ap.add_argument('--apply', action='store_true', help='Write fixes to file (default: dry-run)')
    ap.add_argument('--show-fixed', action='store_true', help='Show diff of successful fixes')
    args = ap.parse_args()

    script_path = SCRIPTS_DIR / args.file
    if not script_path.exists():
        print(f'ERROR: {script_path} not found')
        return 1

    d00 = D00_PATH.read_bytes()
    opmap = parse_d00_opcodes(d00)

    print(f'Dry-run on {args.file}')
    print('=' * 60)
    result = process_file(script_path, opmap, apply=args.apply)
    print(f'Total dialogue entries:          {result["total_entries"]}')
    print(f'Entries with mid-word wraps:     {result["fixed"] + result["flagged"]}')
    print(f'Total wrap issues (before):      {result["total_issues_before"]}')
    print(f'Successfully fixable (safe):     {result["fixed"]}')
    print(f'Needs manual review (flagged):   {result["flagged"]}')
    print()

    if args.show_fixed and result['applied_entries']:
        print('=' * 60)
        print('FIXES TO APPLY:')
        print('=' * 60)
        for entry_idx, before, after, issue_count in result['applied_entries'][:5]:
            print(f'\n--- entry #{entry_idx} ({issue_count} issues fixed) ---')
            print(f'  BEFORE: {before[:200]}')
            print(f'  AFTER:  {after[:200]}')

    if result['flagged_entries']:
        print('=' * 60)
        print('FLAGGED ENTRIES (need manual review):')
        print('=' * 60)
        for entry_idx, body, issue_count, reason in result['flagged_entries'][:10]:
            print(f'  entry #{entry_idx}: {issue_count} issues  — {reason}')
            print(f'    text: {body[:140]}...')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
