"""simulator.py — deterministic budget-exhaustion wrap simulation.

Per decision C of the planning session: the engine wraps a line when
it exhausts the per-line tile budget. NOT greedy-word-wrap. When the
budget is hit, the engine cuts at that boundary even mid-word; the
only way to control cut placement is to insert `<$FFFC>` explicitly.

The simulator walks an entry's segments token-by-token, accumulates
tile count per line, and emits one of 8 issue codes when something
goes wrong:

  Errors:
    line_budget_exceeded       — explicit FFFC-bounded segment > budget
                                  (reserved; not currently emitted —
                                   multi-line profiles wrap before this
                                   triggers)
    label_overflow             — single-line LABEL_*X1 content > width
                                  (the label can't wrap, so it overflows
                                   the visible region)
    balloon_line_overflow      — more lines than the balloon allows
    broken_word_wrap           — implicit cut splits a word; OR a final
                                  line is punctuation-only (orphaned mark);
                                  OR (source-text) an explicit <$FFFC> was
                                  dropped inside a word / a space was lost
                                  after punctuation. See
                                  detect_source_wrap_defects().
    implicit_wrap_without_fffc — line wrapped without an explicit <$FFFC>.
                                  ERROR: the convention is an explicit cut
                                  on every visual break — engine auto-wrap
                                  drags a leading space onto the next line
                                  (ghost indent), so it is never clean.
    unknown_layout_profile     — emitted by metrics when profile=UNKNOWN

  Warnings:
    low_line_usage             — non-final line < 85% of budget
                                  (poor line utilization — playable but
                                  not polished)
    special_token_overflow_risk — protagonist token pushed line past budget
    encoding_risk              — text contains a char with no tile map entry

This module knows nothing about file I/O, JSON, or aggregation. It
operates on one (Entry, profile-spec) pair at a time.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from text_measure import iter_tiles, SPECIAL_TOKEN_WIDTHS  # noqa: E402

# Control codes that look 0-width as source text but RENDER as visible glyphs
# on screen, so they consume tile budget the same as letters. Counting them as
# zero (the old behavior) under-measures a line and lets it sail through QA
# while the engine overflows it in-game (the scen001 「Treatment」 word-break).
# Calibrated from a playtest screenshot: a 「term」 highlight pair eats ~3 tiles
# (the ornate full-width brackets 【 】 plus their rendered spacing); the
# formation glyphs 囗｜―＼／ are one full tile each. These codes appear only in
# scen001's tutorial.
VISIBLE_CTRL_WIDTHS = {
    '<$035C>': 1,   # 【  highlight-open bracket
    '<$035D>': 2,   #  】 highlight-close bracket + rendered spacing
    '<$014A>': 1, '<$014B>': 1, '<$014C>': 1,   # 囗 ｜ ―  formation glyphs
    '<$014D>': 1, '<$014E>': 1,                  # ＼ ／    formation glyphs
}
# (The special number tiles <$0613>=15 / <$0619>=30 used to live here too, but
# they were replaced by plain ASCII digits in the scripts — mechanics numbers
# stay digits, prose numbers are spelled out — so the analyzer now counts them
# natively and no width override is needed.)
# Use the SAME maps text_measure is measuring with, so the encoding-risk
# coverage check follows the LANG3_NEW_FONT toggle (the new font covers every
# script pair, so a char "droppable" under the old map is fine under the new).
from text_measure import ACTIVE_CHAR_MAP as CHAR_TILE_MAP  # noqa: E402
from text_measure import ACTIVE_BIGRAM_MAP as BIGRAM_TILE_MAP  # noqa: E402
from layout_qa.parser import Entry, Segment  # noqa: E402
from layout_qa.classifier import (  # noqa: E402
    BULLET_PATTERN, SCENARIO_PATTERN, visible_text,
)


# Trailing marks that close a sentence/beat. A short non-final line ending
# in one of these is treated as a paragraph-internal sentence boundary
# (fluidity_headroom advisory), not an under-filled line (low_line_usage).
_SENTENCE_FINAL = frozenset('.!?…')

# Matches any <$XXXX> control/token literal, used to strip the protagonist
# name token out of a reconstructed line to test whether the line is just a
# name slot.
_CTRL_LITERAL_RE = re.compile(r'<\$[0-9A-Fa-f]{4}>')


def _is_token_only_line(text: str) -> bool:
    """True when a reconstructed line's only visible content is the
    protagonist name token (`<$F600>...`), optionally with leading/trailing
    punctuation. Such a line is a NAME SLOT — its width is the player's
    chosen name, which cannot be 'filled' with prose, and it is frequently
    placed mid-balloon to match the JP voiced-line position. Exempt from
    low_line_usage. A line mixing real prose with the token is NOT a slot."""
    if '<$F600>' not in text:
        return False
    stripped = _CTRL_LITERAL_RE.sub('', text)
    return not any(c.isalnum() for c in stripped)


@dataclass
class Issue:
    """One reported layout problem on an entry."""
    code: str
    severity: str  # 'error' or 'warning'
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TileUsage:
    """Per-entry stats about how much of each line was used.

    `balloons` carries the structured per-balloon, per-line breakdown
    consumed by the Entry Inspector (schema 0.3.0):

        balloons = [
            {
                'index': 0,
                'lines': [
                    {'index': 0, 'tiles': 11, 'fillRatio': 0.917,
                     'text': 'Sir Diehärte,'},
                    ...
                ],
            },
            ...
        ]
    """
    max_line_tiles: int = 0
    min_line_tiles: int = 0
    avg_line_tiles: float = 0.0   # mean tile count across all emitted lines
    avg_fill_ratio: float = 0.0   # avg_line_tiles / width (0.0 if width=0)
    lines_used: int = 0           # total emitted lines across all balloons
    balloon_count: int = 1        # one balloon by default; bumped on <$FFFD>
    balloons: List[Dict[str, Any]] = field(default_factory=list)


def _percent(used: int, budget: int) -> float:
    return used / budget if budget else 0.0


def _is_structural_entry(entry: Entry) -> bool:
    """True for non-prose entries whose short lines are STRUCTURAL, not
    under-filled prose:

      - objective blocks (a ``*``/``•`` bullet list of victory/defeat
        conditions): the header/item lines are labels, not sentences.
      - SCENARIO title cards: a blank ``<$0000>`` centering line plus a
        centered title — scaffolding that cannot be "filled".

    Such entries are exempt from the prose fill checks
    (``low_line_usage`` / ``fluidity_headroom``). All hard errors
    (overflow, mid-word wrap, etc.) still apply — the exemption is narrow.
    Mirrors the classifier's bullet/SCENARIO detectors so the analyzer and
    classifier agree on what counts as structural.
    """
    try:
        if BULLET_PATTERN.match(visible_text(entry)):
            return True
    except Exception:
        pass
    return bool(SCENARIO_PATTERN.search(getattr(entry, 'raw', '') or ''))


# Single-line profile names (max_lines = 1). For these, the "line
# budget exceeded" error is raised when the entry's tile cost is
# greater than the profile width — there's no wrapping concept.
_SINGLE_LINE_PROFILES = ('LABEL_CHARACTER_12X1', 'LABEL_LOCATION_16X1')


# --- source-text wrap defects: explicit-<$FFFC> word splits + lost spaces ---
# A mechanical fixed-column hard-wrap (the scen025 codex regression) drops an
# explicit <$FFFC> inside a word ("Excelle<$FFFC>ncy") and eats the space after
# punctuation ("order,Varna"). Both render broken in-game, yet the width-based
# wrap simulation passes them: it trusts every explicit <$FFFC> as deliberate
# and only measures line width. This source-level pass catches them.
#
# The word-char class includes the apostrophe and Latin-1 accents so that
# contractions ("you're<$FFFC>safe") and accented names ("Master<$FFFC>Böser")
# read as whole words, not as 1-letter fragments — that is what keeps the
# false-positive rate at zero on the real corpus.
_WORDCHAR = "A-Za-zÀ-ÿ'"
_TRAIL_WORD = re.compile(f'[{_WORDCHAR}]+$')
_LEAD_WORD = re.compile(f'[{_WORDCHAR}]+')
# A complete English contraction suffix (closed set), NOT an opening quote
# before a lowercase word (``name<$FFFC>'genius strategist'`` must stay clean).
_CONTRACTION_TAIL = re.compile(r"'(?:t|s|d|m|ll|re|ve)(?![A-Za-zÀ-ÿ'])")
_GLUE_PUNCT = re.compile(r'[,!?.][A-Za-z]')
# Lone fragments that ARE legitimately whole words; never split markers.
_STANDALONE_ONE_LETTER = frozenset('aio')


def detect_source_wrap_defects(entry: Entry) -> List[Issue]:
    """Flag explicit-<$FFFC> word splits and lost spaces in the source text.

    Returns `broken_word_wrap` errors (severity 'error'); `detail.reason`
    distinguishes the fingerprint:

      - `missing_space_after_punctuation` — e.g. ``order,Varna``
      - `fffc_splits_contraction`         — e.g. ``can<$FFFC>'t``
      - `fffc_splits_word`                — e.g. ``Empir<$FFFC>e``

    Operates on the parsed `entry.segments`, so control codes and the
    protagonist token are never mistaken for word characters.
    """
    issues: List[Issue] = []
    segs = entry.segments

    # (1) Lost space after punctuation, inside one visible text run.
    # Require a real (>= 2-letter) word before the mark, so single-letter
    # stutters / initials / acronyms ("T.That", "G,G,Geier", "N.C.E") are
    # not flagged; skip ellipsis ("...X") and decimals ("3.14").
    for seg in segs:
        if seg.kind != 'text':
            continue
        t = seg.value
        for m in _GLUE_PUNCT.finditer(t):
            p = m.start()
            if p < 2 or not (t[p - 1].isalpha() and t[p - 2].isalpha()):
                continue
            if t[p] == '.' and (t[p - 1] == '.' or
                                (p + 1 < len(t) and t[p + 1].isdigit())):
                continue
            issues.append(Issue(
                code='broken_word_wrap', severity='error',
                detail={'reason': 'missing_space_after_punctuation',
                        'context': t[max(0, p - 8):p + 8]},
            ))

    # (2) Explicit <$FFFC> dropped inside a word.
    for i, seg in enumerate(segs):
        if not (seg.kind == 'ctrl' and seg.value == '<$FFFC>'):
            continue
        left = segs[i - 1].value if i > 0 and segs[i - 1].kind == 'text' else ''
        right = (segs[i + 1].value
                 if i + 1 < len(segs) and segs[i + 1].kind == 'text' else '')
        # Broke a contraction apart: ``can<$FFFC>'t``.
        if _CONTRACTION_TAIL.match(right):
            if _TRAIL_WORD.search(left):
                issues.append(Issue(
                    code='broken_word_wrap', severity='error',
                    detail={'reason': 'fffc_splits_contraction',
                            'context': f'{left[-8:]}<$FFFC>{right[:6]}'},
                ))
            continue
        lm = _TRAIL_WORD.search(left)
        rm = _LEAD_WORD.match(right)
        if not (lm and rm):
            continue
        # A lone lowercase letter (other than a/i/o) on either side of the
        # break means the <$FFFC> fell inside a word rather than between two.
        for frag in (lm.group(0), rm.group(0)):
            if (len(frag) == 1 and frag.islower()
                    and frag not in _STANDALONE_ONE_LETTER):
                issues.append(Issue(
                    code='broken_word_wrap', severity='error',
                    detail={'reason': 'fffc_splits_word',
                            'context': f'{lm.group(0)}<$FFFC>{rm.group(0)}'},
                ))
                break
    return issues


# --- spoken-punctuation gate: forbidden `:` `;` `—` anywhere in content ---
# Project-wide hard rule (user 2026-06-16): the colon, semicolon, and em-dash
# are written-prose typography that breaks a localized, spoken-feeling read —
# and the em-dash isn't in the tile map, so the font drops it silently. They
# must not appear ANYWHERE in scen/plot content (dialogue OR narration);
# location labels use comma/hyphen, never these. Allowed: `.` `,` `…` `?` `!`.
# Scans only `text` segments, so control codes and the protagonist token can
# never be mistaken for prose. The regular hyphen `-` (compound proper nouns
# like `Rigüler-Barral Border`) is allowed and NOT in this set.
_FORBIDDEN_PUNCT = {':': 'colon', ';': 'semicolon', '—': 'em_dash'}


def detect_forbidden_punctuation(entry: Entry) -> List[Issue]:
    """Flag every colon `:`, semicolon `;`, or em-dash `—` in the entry's prose.

    Returns one `forbidden_punctuation` ERROR per occurrence; `detail.reason`
    is `colon` / `semicolon` / `em_dash`, with a small `context` window. The
    width-based wrap simulator cannot see these (they fit fine on screen) —
    this is a source-level editorial gate, like detect_source_wrap_defects().
    """
    issues: List[Issue] = []
    for seg in entry.segments:
        if seg.kind != 'text':
            continue
        t = seg.value
        for p, ch in enumerate(t):
            reason = _FORBIDDEN_PUNCT.get(ch)
            if reason is None:
                continue
            issues.append(Issue(
                code='forbidden_punctuation', severity='error',
                detail={'reason': reason, 'char': ch,
                        'context': t[max(0, p - 8):p + 9]},
            ))
    return issues


def simulate_entry(
    entry: Entry,
    profile_spec: Dict[str, Any],
    approved_lines: set | None = None,
) -> Tuple[List[Issue], TileUsage]:
    """Run the budget-exhaustion wrap simulator on one entry.

    Args:
        entry: parsed Entry from layout_qa.parser.
        profile_spec: dict with at minimum
            'width' (int): tiles per line.
            'max_lines' (int): max lines per balloon (1 for LABEL).
            'low_line_usage_threshold' (float, default 0.85):
                ratio below which a non-final line gets the warning.
                A line at exactly the threshold passes (strict less-than).
        approved_lines: optional set of (balloon_index, line_index)
            tuples whitelisted by human review — for these, the
            `low_line_usage` warning is suppressed. ONLY honored for
            DIALOGUE_12X4 (the only profile that has a legitimate
            "intentional short line" use case, e.g. interjections
            with a `<$FFFB>` pause). All other issue codes are
            emitted normally regardless of approval.

    Returns:
        (issues, tile_usage).
    """
    width = int(profile_spec['width'])
    _ml = profile_spec.get('max_lines')
    max_lines = int(_ml) if _ml is not None else None
    low_thresh = float(profile_spec.get('low_line_usage_threshold', 0.85))
    # Scrolling regions (the PLOT.DAT recap box) auto-insert a <$FFFD>
    # when a page overflows the visible window, so a balloon may exceed
    # max_lines without breaking — suppress balloon_line_overflow there.
    # max_lines still bounds the visible window for reference.
    scrolls = bool(profile_spec.get('scrolls', False))

    profile_name = profile_spec.get('name', '?')
    is_single_line = profile_name in _SINGLE_LINE_PROFILES

    # Structural entries (objective lists, SCENARIO title cards) are not
    # prose — their short header/centering lines must not trip the fill
    # check. Hard errors still apply (the exemption is narrow).
    exempt_fill = _is_structural_entry(entry)

    # Approvals are honored only for DIALOGUE_12X4. Anything else
    # ignores the set even if passed.
    approvals_active = (
        profile_name == 'DIALOGUE_12X4' and approved_lines is not None
    )
    approved = approved_lines if approvals_active else frozenset()

    issues: List[Issue] = []
    usage = TileUsage()

    # State during the walk:
    balloon_idx = 0
    line_idx = 0          # within current balloon
    line_tiles = 0        # tiles emitted on current line
    saw_explicit_fffc_on_line = False
    line_tile_history: List[int] = []  # tiles used per emitted line in this balloon
    # Inspector data: text buffer for the current line + accumulated
    # line records for the current balloon. On _close_line() we push a
    # record; on FFFD we push the whole balloon record into usage.balloons.
    current_line_text: List[str] = []
    current_balloon_lines: List[Dict[str, Any]] = []

    def _close_line():
        """Record the just-finished line in history + per-line inspector
        record, then reset both counters and the text buffer."""
        nonlocal line_tiles, saw_explicit_fffc_on_line
        line_tile_history.append(line_tiles)
        current_balloon_lines.append({
            'index': len(current_balloon_lines),
            'tiles': line_tiles,
            'fillRatio': round(line_tiles / width, 4) if width else 0.0,
            'text': ''.join(current_line_text),
        })
        current_line_text.clear()
        line_tiles = 0
        saw_explicit_fffc_on_line = False

    def _close_balloon():
        """Push the accumulated lines onto usage.balloons under the
        current balloon_idx, then clear the accumulator."""
        if current_balloon_lines:
            usage.balloons.append({
                'index': balloon_idx,
                'lines': list(current_balloon_lines),
            })
        current_balloon_lines.clear()

    def _line_text(i: int) -> str:
        """Inspector text recorded for line i of the current balloon."""
        if 0 <= i < len(current_balloon_lines):
            return current_balloon_lines[i].get('text', '')
        return ''

    def _flush_balloon_warnings():
        """At balloon end, emit polish signals on the balloon's lines.

        Non-final short lines (< low_thresh fill):
          - if the line ENDS A SENTENCE (.!?…) it is not a defect — the
            balloon reads as a paragraph and the leftover width is room
            for fluidity (expand this sentence, or let the next start
            here). Emit `fluidity_headroom` at severity 'info', which
            does NOT block POLISHED.
          - otherwise the line is genuinely under-filled mid-thought →
            `low_line_usage` (warning).
        Lines pre-approved (DIALOGUE only) are skipped.

        Final line: punctuation must travel with at least its last word.
        A multi-line balloon whose final line is punctuation-only means a
        wrap tore the mark off its word → `broken_word_wrap` (error).
        """
        for i, t in enumerate(line_tile_history[:-1]):  # skip final line
            if not (width and _percent(t, width) < low_thresh):
                continue
            if (balloon_idx, i) in approved:
                continue
            if exempt_fill:  # structural entry — not prose, no fill check
                continue
            if not _line_text(i).strip():  # empty line = bottom-align <$FFFC>
                continue                   # padding (FFFC on top); not prose
            if _is_token_only_line(_line_text(i)):  # bare name slot
                continue
            sentence_final = _line_text(i).rstrip()[-1:] in _SENTENCE_FINAL
            # The FIRST line of a balloon may NOT be short, even sentence-final —
            # a thin lead line is wasted width (mechanical JP-mirroring). Only a
            # NON-first sentence-final short line earns the fluidity_headroom
            # pass; the per-scen budget (cli._apply_fluidity_budget) then caps how
            # many of those a scen may keep.
            if i != 0 and sentence_final:
                issues.append(Issue(
                    code='fluidity_headroom', severity='info',
                    detail={
                        'balloon': balloon_idx, 'line': i,
                        'tiles': t, 'budget': width,
                        'freeTiles': width - t,
                        'threshold': low_thresh,
                        'note': 'sentence-final line: room to expand this '
                                'sentence or start the next one here',
                    },
                ))
            else:
                detail = {
                    'balloon': balloon_idx, 'line': i,
                    'tiles': t, 'budget': width,
                    'threshold': low_thresh,
                }
                if i == 0 and sentence_final:
                    detail['note'] = ('first line of a balloon may not be short, '
                                      'even sentence-final — fill it or pull the '
                                      'next line up')
                issues.append(Issue(
                    code='low_line_usage', severity='warning', detail=detail,
                ))

        # final-line orphaned-punctuation check (needs a preceding line)
        if len(current_balloon_lines) >= 2:
            tail = _line_text(len(line_tile_history) - 1).strip()
            if tail and not any(c.isalnum() for c in tail):
                issues.append(Issue(
                    code='broken_word_wrap', severity='error',
                    detail={
                        'balloon': balloon_idx,
                        'line': len(line_tile_history) - 1,
                        'fragment': tail,
                        'reason': 'orphan_punctuation_on_final_line',
                    },
                ))

    def _check_encoding_risk(text: str):
        """Emit encoding_risk if any char in `text` would be silently
        dropped by the encoder (not in CHAR_TILE_MAP, not consumed by
        any bigram). Strict check — looks for ANY char not coverable."""
        for ch in text:
            if ch in CHAR_TILE_MAP:
                continue
            if any(ch == k[0] for k in BIGRAM_TILE_MAP):
                continue
            issues.append(Issue(
                code='encoding_risk', severity='warning',
                detail={'char': repr(ch), 'balloon': balloon_idx, 'line': line_idx},
            ))
            return  # one per entry is enough

    for seg in entry.segments:
        if seg.kind == 'ctrl':
            v = seg.value
            if v == '<$FFFC>':
                # explicit cut
                if is_single_line:
                    # FFFC inside a single-line profile is unusual — count it
                    # toward overflow.
                    saw_explicit_fffc_on_line = True
                _close_line()
                saw_explicit_fffc_on_line = True
                line_idx += 1
                if (not is_single_line and not scrolls and max_lines is not None
                        and line_idx >= max_lines):
                    issues.append(Issue(
                        code='balloon_line_overflow', severity='error',
                        detail={
                            'balloon': balloon_idx,
                            'actualLines': line_idx + 1,
                            'maxLines': max_lines,
                        },
                    ))
            elif v == '<$FFFD>':
                # balloon break — flush current line + warnings, push
                # the balloon record, reset for the next balloon
                _close_line()
                _flush_balloon_warnings()
                _close_balloon()
                line_tile_history.clear()
                balloon_idx += 1
                line_idx = 0
            elif v in ('<$FFFE>', '<$FFFF>'):
                # entry terminator — just close the trailing line
                pass
            elif v in VISIBLE_CTRL_WIDTHS:
                # Renders as a visible glyph (highlight bracket / formation
                # symbol): consumes tile budget like a letter. Atomic — it
                # cannot be split, so on overflow it wraps to the next line.
                w = VISIBLE_CTRL_WIDTHS[v]
                if line_tiles + w > width:
                    if not saw_explicit_fffc_on_line:
                        issues.append(Issue(
                            code='implicit_wrap_without_fffc', severity='error',
                            detail={'balloon': balloon_idx, 'line': line_idx,
                                    'tilesUsed': line_tiles, 'budget': width},
                        ))
                    _close_line()
                    line_idx += 1
                    if (not is_single_line and not scrolls and max_lines is not None
                        and line_idx >= max_lines):
                        issues.append(Issue(
                            code='balloon_line_overflow', severity='error',
                            detail={'balloon': balloon_idx,
                                    'actualLines': line_idx + 1,
                                    'maxLines': max_lines},
                        ))
                line_tiles += w
                current_line_text.append(v)
            # other ctrl codes (e.g. <$0000>, <$F702>): no impact on tiles
            continue

        if seg.kind == 'token':
            w = SPECIAL_TOKEN_WIDTHS.get(seg.value, 1)
            if line_tiles + w > width:
                issues.append(Issue(
                    code='special_token_overflow_risk', severity='warning',
                    detail={
                        'balloon': balloon_idx, 'line': line_idx,
                        'token': seg.value, 'tilesUsed': line_tiles, 'budget': width,
                    },
                ))
                # Treat as an implicit wrap before the token.
                if not saw_explicit_fffc_on_line:
                    issues.append(Issue(
                        code='implicit_wrap_without_fffc', severity='error',
                        detail={'balloon': balloon_idx, 'line': line_idx},
                    ))
                _close_line()
                line_idx += 1
                if (not is_single_line and not scrolls and max_lines is not None
                        and line_idx >= max_lines):
                    issues.append(Issue(
                        code='balloon_line_overflow', severity='error',
                        detail={
                            'balloon': balloon_idx,
                            'actualLines': line_idx + 1,
                            'maxLines': max_lines,
                        },
                    ))
            line_tiles += w
            # Record token literal on the current line so the Inspector
            # can render the F600/0000 placeholder visibly.
            current_line_text.append(seg.value)
            continue

        # text segment
        _check_encoding_risk(seg.value)
        for substr, tile_cost in iter_tiles(seg.value):
            if line_tiles + tile_cost > width:
                # wrap
                is_word_interior = bool(substr) and substr[0] not in ' \t'
                if is_word_interior:
                    issues.append(Issue(
                        code='broken_word_wrap', severity='error',
                        detail={
                            'balloon': balloon_idx, 'line': line_idx,
                            'fragment': substr,
                        },
                    ))
                if not saw_explicit_fffc_on_line:
                    issues.append(Issue(
                        code='implicit_wrap_without_fffc', severity='error',
                        detail={
                            'balloon': balloon_idx, 'line': line_idx,
                            'tilesUsed': line_tiles, 'budget': width,
                        },
                    ))
                _close_line()
                line_idx += 1
                if (not is_single_line and not scrolls and max_lines is not None
                        and line_idx >= max_lines):
                    issues.append(Issue(
                        code='balloon_line_overflow', severity='error',
                        detail={
                            'balloon': balloon_idx,
                            'actualLines': line_idx + 1,
                            'maxLines': max_lines,
                        },
                    ))
            line_tiles += tile_cost
            # Append the chunk to the current line buffer.
            current_line_text.append(substr)

    # close the final line of the final balloon
    _close_line()
    _flush_balloon_warnings()
    _close_balloon()

    # Single-line profiles: any content over budget is a hard error.
    # Even if the simulator wrapped internally, more than 1 line means
    # the total content didn't fit in the single line the engine renders.
    if is_single_line:
        total_tiles = sum(line_tile_history)
        if total_tiles > width or len(line_tile_history) > 1:
            issues.append(Issue(
                code='label_overflow', severity='error',
                detail={
                    'tilesUsed': total_tiles,
                    'budget': width,
                    'linesAttempted': len(line_tile_history),
                },
            ))
        # NOTE: labels have NO minimum-fill rule (user spec 2026-06-17).
        # A label is valid at ANY length up to its width cap; the only hard
        # limit is label_overflow (> width) above. There is deliberately no
        # low_line_usage warning for single-line label profiles.

    # line_padding_space — internal wrap boundaries must consume the space.
    # ERROR severity (2026-06-19, user spec): a padding space at an internal
    # wrap boundary is a real defect — the engine leaves a ghost gap / leading
    # indent on the rendered line — so it blocks readiness, not just polish.
    # Applies to profiles where text is meant to flow naturally (DIALOGUE);
    # exempt for profiles whose layout uses bigram-trick spacing (NARRATION,
    # OBJECTIVE, LABEL_*). Controlled by profile_spec['enforce_line_padding'].
    if profile_spec.get('enforce_line_padding', False):
        for b in usage.balloons:
            lines = b['lines']
            if len(lines) < 2:
                continue
            for idx, ln in enumerate(lines):
                text = ln['text']
                if not text:
                    continue
                is_last = (idx == len(lines) - 1)
                is_first = (idx == 0)
                if not is_last and text.endswith(' '):
                    issues.append(Issue(
                        code='line_padding_space', severity='error',
                        detail={
                            'balloon': b['index'], 'line': idx,
                            'position': 'trailing',
                        },
                    ))
                if not is_first and text.startswith(' '):
                    issues.append(Issue(
                        code='line_padding_space', severity='error',
                        detail={
                            'balloon': b['index'], 'line': idx,
                            'position': 'leading',
                        },
                    ))

    # Populate usage stats from the structured per-line records — the
    # single source of truth. line_tile_history was reset on each FFFD,
    # so deriving stats from it would only see the last balloon; the
    # balloons[*].lines[*] view sees the whole entry.
    all_line_tiles = [l['tiles'] for b in usage.balloons for l in b['lines']]
    if all_line_tiles:
        usage.max_line_tiles = max(all_line_tiles)
        usage.min_line_tiles = min(all_line_tiles)
        usage.lines_used = len(all_line_tiles)
        avg = sum(all_line_tiles) / len(all_line_tiles)
        usage.avg_line_tiles = round(avg, 2)
        if width > 0:
            usage.avg_fill_ratio = round(avg / width, 4)
    usage.balloon_count = balloon_idx + 1

    # Source-text defects the width-based wrap can't see: an explicit
    # <$FFFC> dropped inside a word, or a space lost after punctuation.
    issues.extend(detect_source_wrap_defects(entry))

    # Editorial gate: forbidden spoken punctuation (`:` `;` `—`) in prose.
    issues.extend(detect_forbidden_punctuation(entry))

    return issues, usage
