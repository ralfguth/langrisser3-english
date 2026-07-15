"""test_layout_qa_simulator.py — unit tests for budget-exhaustion wrap.

Per the implementation-plan checkpoint, each of the 8 issue codes must
be emitted at least once in fixtures (excluding `unknown_layout_profile`
which is the metrics-layer responsibility).
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.parser import Entry, Segment, PROTAGONIST_TOKEN  # noqa: E402
from layout_qa.simulator import simulate_entry, Issue, TileUsage  # noqa: E402
from layout_qa.cli import DEFAULT_PROFILE_SPECS  # noqa: E402


PROF_DIALOGUE = {
    'name': 'DIALOGUE_12X4', 'width': 12, 'max_lines': 4,
    'enforce_line_padding': True,
}
PROF_NARRATION = {'name': 'NARRATION_16X5', 'width': 16, 'max_lines': 5}
PROF_OBJECTIVE = {'name': 'OBJECTIVE_16X5', 'width': 16, 'max_lines': 5}
PROF_LABEL_CHAR = {'name': 'LABEL_CHARACTER_12X1', 'width': 12, 'max_lines': 1}
PROF_LABEL_LOC = {'name': 'LABEL_LOCATION_16X1', 'width': 16, 'max_lines': 1}


def _e(*segments, terminator='FFFE') -> Entry:
    """Helper to build an Entry from positional segment tuples."""
    segs = []
    for s in segments:
        if isinstance(s, Segment):
            segs.append(s)
        elif isinstance(s, tuple):
            kind, value = s
            segs.append(Segment(kind, value))
        elif s.startswith('<$') and s.endswith('>'):
            segs.append(Segment('ctrl', s))
        else:
            segs.append(Segment('text', s))
    # Add the terminator if not already at the tail
    if not (segs and segs[-1].kind == 'ctrl' and segs[-1].value.endswith(f'{terminator}>')):
        segs.append(Segment('ctrl', f'<${terminator}>'))
    return Entry('scenTEST', 0, ''.join(s.value for s in segs), terminator, segs)


def _codes(issues):
    return [i.code for i in issues]


# ---------------------------------------------------------------------------
# CLEAN — no issues
# ---------------------------------------------------------------------------

def test_clean_dialogue_no_issues():
    e = _e('Hello world.')  # 6 tiles (he-l-lo wo-r-ld.), well under 12
    issues, usage = simulate_entry(e, PROF_DIALOGUE)
    assert issues == []
    assert usage.lines_used == 1


# ---------------------------------------------------------------------------
# label_overflow (single-line LABEL profile content > width)
# ---------------------------------------------------------------------------

def test_label_overflow_for_long_label():
    # 26 chars — well over 12-tile LABEL budget.
    e = _e('abcdefghijklmnopqrstuvwxyz', terminator='FFFF')
    issues, usage = simulate_entry(e, PROF_LABEL_CHAR)
    assert 'label_overflow' in _codes(issues)


def test_label_at_budget_exactly_no_error():
    # 'Field Marshal Altemüller' = 12 tiles exact (measured earlier).
    e = _e('Field Marshal Altemüller', terminator='FFFF')
    issues, _ = simulate_entry(e, PROF_LABEL_CHAR)
    assert 'label_overflow' not in _codes(issues)


# ---------------------------------------------------------------------------
# balloon_line_overflow
# ---------------------------------------------------------------------------

def test_balloon_line_overflow_via_explicit_fffc():
    e = _e(
        'L1', '<$FFFC>', 'L2', '<$FFFC>',
        'L3', '<$FFFC>', 'L4', '<$FFFC>',
        'L5',  # 5th line in a 4-line balloon
    )
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'balloon_line_overflow' in _codes(issues)


# ---------------------------------------------------------------------------
# broken_word_wrap
# ---------------------------------------------------------------------------

def test_broken_word_wrap_mid_word():
    # 26-char word with no spaces forces mid-word cut at 12-tile boundary.
    e = _e('abcdefghijklmnopqrstuvwxyz')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'broken_word_wrap' in _codes(issues)


# ---------------------------------------------------------------------------
# implicit_wrap_without_fffc
# ---------------------------------------------------------------------------

def test_implicit_wrap_without_fffc():
    # Long line that wraps without an explicit FFFC anywhere.
    e = _e('the quick brown fox jumped over the lazy dog rapidly')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'implicit_wrap_without_fffc' in _codes(issues)


def test_explicit_fffc_suppresses_implicit_warning():
    """When an FFFC is placed at the wrap boundary, no implicit warning."""
    # Build a payload that hits exactly the boundary.
    # 'abcdefghijkl' = 12 chars; with bigrams, probably ~6-7 tiles.
    # Use lowercase chars that pair → bigrams reduce tile count.
    e = _e('hello', '<$FFFC>', 'world')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'implicit_wrap_without_fffc' not in _codes(issues)


# ---------------------------------------------------------------------------
# low_line_usage
# ---------------------------------------------------------------------------

def test_low_line_usage_warning_for_short_non_final_line():
    # Force a wrap with a too-short first line via explicit FFFC.
    # 'ab<$FFFC>def...' — first line is 1-2 tiles, way below 50% of 12.
    e = _e('ab', '<$FFFC>', 'cdefghijkl mnop qrst uvwx yz!')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'low_line_usage' in _codes(issues)


def test_polish_threshold_boundary_85pct_passes():
    """A non-final line at ≥ 85% fill (11/12 = 91.7%) emits no warning."""
    # 'A B C D E F G H I J K' = 11 single-char tiles separated by spaces.
    e = _e('A B C D E F G H I J K', '<$FFFC>', 'A B C')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'low_line_usage' not in _codes(issues)


def test_polish_threshold_below_85pct_warns():
    """A non-final line at < 85% fill (10/12 = 83.3%) triggers warning."""
    e = _e('A B C D E F G H I J', '<$FFFC>', 'A B C')  # 10 tiles, then short
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'low_line_usage' in _codes(issues)


def test_polish_threshold_16wide_boundary():
    """On 16-wide profiles, 14/16 = 87.5% passes; 13/16 = 81.25% fails."""
    e_pass = _e('A B C D E F G H I J K L M N', '<$FFFC>', 'tail')  # 14 tiles
    issues_pass, _ = simulate_entry(e_pass, PROF_NARRATION)
    assert 'low_line_usage' not in _codes(issues_pass)

    e_fail = _e('A B C D E F G H I J K L M', '<$FFFC>', 'tail')    # 13 tiles
    issues_fail, _ = simulate_entry(e_fail, PROF_NARRATION)
    assert 'low_line_usage' in _codes(issues_fail)


def test_polish_threshold_last_line_exempt():
    """The final line of a balloon is exempt from the polish threshold."""
    # Single line balloon, far below threshold — but it's the last line.
    e = _e('hi')  # 2 tiles, no FFFC/FFFD → balloon has 1 line which is final
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'low_line_usage' not in _codes(issues)


def test_polish_threshold_in_warning_detail():
    """The emitted warning carries the threshold that was crossed."""
    e = _e('A B', '<$FFFC>', 'tail')  # 2 tiles, well below 0.85 of 12
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    low = next(i for i in issues if i.code == 'low_line_usage')
    assert low.detail.get('threshold') == 0.85


# ---------------------------------------------------------------------------
# fluidity_headroom — a SHORT non-final line that ENDS A SENTENCE (.!?…) is
# not a polish defect. It's an advisory ('info') that space is available for
# fluidity: the ending sentence may be expanded, or the next sentence may
# start on this same line. Severity 'info' → does NOT block POLISHED.
# See memory feedback_explicit_fffc_every_line (balão = parágrafo).
# ---------------------------------------------------------------------------

def test_sentence_final_short_line_emits_fluidity_headroom_not_low_line_usage():
    # A NON-FIRST short sentence-final line earns the pass; first-line short is
    # banned (see test_layout_qa_fluidity_budget). line0 is full (11 tiles).
    e = _e('A B C D E F G H I J K', '<$FFFC>', 'done.', '<$FFFC>', 'next sentence carries on')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    codes = _codes(issues)
    assert 'fluidity_headroom' in codes
    assert 'low_line_usage' not in codes


def test_fluidity_headroom_is_info_severity_and_keeps_polished():
    from layout_qa.metrics import bucket_status
    e = _e('A B C D E F G H I J K', '<$FFFC>', 'done.', '<$FFFC>', 'next sentence carries on')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    fh = next(i for i in issues if i.code == 'fluidity_headroom')
    assert fh.severity == 'info'
    serial = [{'code': i.code, 'severity': i.severity, 'detail': i.detail}
              for i in issues]
    assert bucket_status(serial, 'DIALOGUE_12X4') == 'POLISHED'


def test_short_non_sentence_final_line_still_low_line_usage():
    # No terminal punctuation → still a genuine fill defect (warning).
    e = _e('ab', '<$FFFC>', 'cdefghijkl')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    codes = _codes(issues)
    assert 'low_line_usage' in codes
    assert 'fluidity_headroom' not in codes


def test_scrolls_suppresses_balloon_line_overflow():
    """A scrolling region (PLOT.DAT recap box) auto-FFFDs on overflow, so a
    balloon may exceed max_lines without error when `scrolls` is set."""
    # 6 explicit lines in a 5-line-window profile.
    e = _e('aa', '<$FFFC>', 'bb', '<$FFFC>', 'cc', '<$FFFC>',
           'dd', '<$FFFC>', 'ee', '<$FFFC>', 'ff')
    scroll_spec = {'name': 'NARRATION_16X5', 'width': 16, 'max_lines': 5,
                   'scrolls': True}
    issues, _ = simulate_entry(e, scroll_spec)
    assert 'balloon_line_overflow' not in _codes(issues)
    # Without scrolls the same content overflows.
    issues2, _ = simulate_entry(e, PROF_NARRATION)
    assert 'balloon_line_overflow' in _codes(issues2)


def test_objective_bullet_entry_exempt_from_low_line_usage():
    """An objectives block (bullet/asterisk headers + items) is non-prose:
    its short header lines like '*Victory Conditions' are structural, not
    under-filled prose. They must not trip low_line_usage."""
    e = _e(
        '*Victory Conditions', '<$FFFC>',
        '•Total destruction of the enemy', '<$FFFC>',
        '*Defeat Conditions', '<$FFFC>',
        '•Death of the Hero',
    )
    issues, _ = simulate_entry(e, PROF_NARRATION)
    codes = _codes(issues)
    assert 'low_line_usage' not in codes
    assert 'fluidity_headroom' not in codes


def test_scenario_title_card_exempt_from_low_line_usage():
    """A SCENARIO title card has a blank centering line (from <$0000>) and a
    centered title — structural scaffolding, not prose. No low_line_usage."""
    e = _e(
        ('ctrl', '<$0000>'), '<$FFFC>',
        '   ＳＣＥＮＡＲＩＯ‐０１', '<$FFFC>',
        ' Assault on the Floating Castle ',
    )
    issues, _ = simulate_entry(e, PROF_NARRATION)
    codes = _codes(issues)
    assert 'low_line_usage' not in codes


def test_structural_exemption_is_narrow_overflow_still_flagged():
    """The structural exemption only silences low_line_usage/fluidity_headroom.
    Hard errors (e.g. balloon_line_overflow) on a bullet entry still fire."""
    e = _e(
        '*A', '<$FFFC>', '*B', '<$FFFC>', '*C', '<$FFFC>',
        '*D', '<$FFFC>', '*E', '<$FFFC>', '*F',  # 6 lines > 5 max
    )
    issues, _ = simulate_entry(e, PROF_NARRATION)
    assert 'balloon_line_overflow' in _codes(issues)


def test_token_only_line_exempt_from_low_line_usage():
    """A mid-balloon line that is solely the protagonist name token (often
    placed there to match the JP voiced-line position) is a name slot, not
    under-filled prose. Its width is the player's chosen name — not
    fillable. It must not trip low_line_usage."""
    e = _e(
        ('text', 'From this day onward,'), '<$FFFC>',
        ('token', '<$F600><$0000>'), '<$FFFC>',
        ('text', 'shall be your name.'),
    )
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'low_line_usage' not in _codes(issues)


def test_token_only_line_with_trailing_punct_exempt():
    """Token line carrying only trailing punctuation (e.g. '<token>,') is
    still a name slot — exempt."""
    e = _e(
        ('text', 'My deepest thanks to you'), '<$FFFC>',
        ('token', '<$F600><$0000>'), ('text', ','), '<$FFFC>',
        ('text', 'for the kindness you showed.'),
    )
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    # L0 (12) and L2 (final) are fine; the bare token line is exempt.
    assert 'low_line_usage' not in _codes(issues)


def test_token_line_with_prose_not_exempt():
    """A short line that mixes prose with the token is NOT a bare name slot —
    the fill check still applies to it."""
    e = _e(
        ('text', 'Yo '), ('token', '<$F600><$0000>'), '<$FFFC>',
        ('text', 'the rest of this carries the thought on'),
    )
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    # 'Yo <token>' has real prose ('Yo') → still subject to the check.
    assert 'low_line_usage' in _codes(issues)


def test_normal_narration_short_line_still_low_line_usage():
    """Regression: a non-structural narration with a short mid-thought line
    is NOT exempt — the prose fill check still applies."""
    e = _e('short', '<$FFFC>', 'this line carries the thought onward')
    issues, _ = simulate_entry(e, PROF_NARRATION)
    assert 'low_line_usage' in _codes(issues)


def test_fluidity_headroom_exempts_all_terminal_punctuation():
    for tail in ('.', '!', '?', '…'):
        # non-first short line (line0 full) ending in each terminal mark.
        e = _e('A B C D E F G H I J K', '<$FFFC>', 'end' + tail,
               '<$FFFC>', 'and the tale goes on')
        issues, _ = simulate_entry(e, PROF_DIALOGUE)
        codes = _codes(issues)
        assert 'fluidity_headroom' in codes, tail
        assert 'low_line_usage' not in codes, tail


def test_fluidity_headroom_detail_reports_free_space():
    e = _e('A B C D E F G H I J K', '<$FFFC>', 'done.', '<$FFFC>', 'next sentence carries on')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    fh = next(i for i in issues if i.code == 'fluidity_headroom')
    assert fh.detail.get('budget') == 12
    assert fh.detail.get('freeTiles', 0) > 0


# ---------------------------------------------------------------------------
# orphan punctuation — punctuation must travel with at least its last word.
# A final balloon line that is punctuation-only means a wrap (usually an
# explicit <$FFFC>) tore the mark off its word → ERROR. This closes the
# blind spot where the final line is otherwise exempt from polish checks.
# ---------------------------------------------------------------------------

def _orphan_errs(issues):
    return [i for i in issues
            if i.code == 'broken_word_wrap'
            and i.detail.get('reason') == 'orphan_punctuation_on_final_line']


def test_punctuation_only_final_line_is_error():
    e = _e('lives', '<$FFFC>', '.')   # '.' alone on the final line
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert _orphan_errs(issues), _codes(issues)


def test_orphan_punctuation_covers_all_marks():
    for tail in ('.', '!', '?', '…', '!?', '...'):
        e = _e('word', '<$FFFC>', tail)
        issues, _ = simulate_entry(e, PROF_DIALOGUE)
        assert _orphan_errs(issues), (tail, _codes(issues))


def test_punctuation_with_word_on_final_line_ok():
    e = _e('human', '<$FFFC>', 'lives.')   # mark travels with its word
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert not _orphan_errs(issues)


def test_standalone_punctuation_single_line_balloon_not_orphan():
    # A one-line balloon that is only '…' is a deliberate beat — there is
    # no preceding word it was torn from, so it is not an orphan error.
    e = _e('…')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert not _orphan_errs(issues)


# ---------------------------------------------------------------------------
# line_padding_space — no leading/trailing space at internal wrap boundaries
# ---------------------------------------------------------------------------

def test_padding_space_trailing_on_non_last_line():
    """A non-last line ending with ' ' triggers line_padding_space (DIALOGUE).

    Red→Green (2026-06-19): line_padding_space is now an ERROR, not a
    warning. A padding space at an internal wrap boundary is a defect
    (the engine leaves a ghost gap / leading indent) — it must block
    readiness, not merely polish."""
    e = _e('hello ', '<$FFFC>', 'world')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    codes = _codes(issues)
    assert 'line_padding_space' in codes
    pad = next(i for i in issues if i.code == 'line_padding_space')
    assert pad.severity == 'error'
    assert pad.detail.get('position') == 'trailing'


def test_padding_space_leading_on_non_first_line():
    """A non-first line starting with ' ' triggers line_padding_space (ERROR)."""
    e = _e('hello', '<$FFFC>', ' world')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    codes = _codes(issues)
    assert 'line_padding_space' in codes
    pad = next(i for i in issues if i.code == 'line_padding_space')
    assert pad.severity == 'error'
    assert pad.detail.get('position') == 'leading'


def test_entry_with_padding_space_buckets_to_error():
    """An entry carrying line_padding_space is ERROR (2026-06-19, user
    spec): the padding space at an internal wrap boundary is a real
    defect, not a polish nicety, so it must drop readiness."""
    from layout_qa.metrics import bucket_status
    e = _e('hello ', '<$FFFC>', 'world')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'line_padding_space' in _codes(issues)
    issues_dicts = [{'code': i.code, 'severity': i.severity, 'detail': i.detail}
                    for i in issues]
    assert bucket_status(issues_dicts, 'DIALOGUE_12X4') == 'ERROR'


def test_padding_space_clean_wrap_no_warning():
    """The canonical wrap pattern 'word<$FFFC>word' is clean — no warning."""
    e = _e('begun to', '<$FFFC>', 'rise through')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'line_padding_space' not in _codes(issues)


def test_padding_space_last_line_trailing_ok():
    """The final line of a balloon may end with anything — no warning."""
    e = _e('hello world ')  # single line ending with space
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'line_padding_space' not in _codes(issues)


def test_padding_space_first_line_leading_ok():
    """The first line of a balloon may start with anything (rare anyway)."""
    e = _e(' hello', '<$FFFC>', 'world')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    # Only one line in this balloon has a "leading position" check — line 1.
    # Line 1 starts with 'world', no leading space. Line 0 is first, exempt.
    pads = [i for i in issues if i.code == 'line_padding_space']
    assert pads == []


def test_padding_space_narration_exempt():
    """NARRATION_16X5 uses bigram tricks for layout — rule does NOT apply."""
    e = _e('hello ', '<$FFFC>', ' world')  # both trailing AND leading
    issues, _ = simulate_entry(e, PROF_NARRATION)
    assert 'line_padding_space' not in _codes(issues)


def test_padding_space_objective_exempt():
    """OBJECTIVE_16X5 uses bigram tricks — exempt."""
    e = _e('mission ', '<$FFFC>', ' target')
    issues, _ = simulate_entry(e, PROF_OBJECTIVE)
    assert 'line_padding_space' not in _codes(issues)


def test_padding_space_label_exempt_or_inapplicable():
    """LABEL_* single-line profiles don't have internal wrap boundaries."""
    e = _e('place name ')  # might still be in a single-line LABEL
    issues, _ = simulate_entry(e, PROF_LABEL_CHAR)
    assert 'line_padding_space' not in _codes(issues)


def test_padding_space_balloon_break_does_not_trigger():
    """A balloon end (FFFD) is not an internal wrap — terminal trailing space ok."""
    e = _e('hello world', '<$FFFD>', 'next balloon')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    # Within either balloon, the only line ends naturally — no internal wrap.
    assert 'line_padding_space' not in _codes(issues)


# ---------------------------------------------------------------------------
# special_token_overflow_risk
# ---------------------------------------------------------------------------

def test_special_token_overflow_risk():
    # 'Hello there, ' is several tiles + 8-tile F600 token + '.'
    # Total > 12; should flag the token-induced overflow.
    e = _e(
        'Hello there, ',
        ('token', PROTAGONIST_TOKEN),
        '.',
    )
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'special_token_overflow_risk' in _codes(issues)


def test_special_token_fits_no_risk():
    """F600 fits when the remaining line has 8+ tiles available."""
    # Just the token alone (8 tiles, fits in 12).
    e = _e(('token', PROTAGONIST_TOKEN))
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'special_token_overflow_risk' not in _codes(issues)


# ---------------------------------------------------------------------------
# encoding_risk
# ---------------------------------------------------------------------------

def test_encoding_risk_for_unmapped_char():
    """A char that's neither in CHAR_TILE_MAP nor any bigram triggers."""
    e = _e('text with ​ zerowidth')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert 'encoding_risk' in _codes(issues)


# ---------------------------------------------------------------------------
# Balloon reset on <$FFFD>
# ---------------------------------------------------------------------------

def test_fffd_resets_line_counter():
    """A balloon break starts a fresh 4-line counter."""
    e = _e(
        'A', '<$FFFC>', 'B', '<$FFFC>', 'C', '<$FFFC>', 'D',
        '<$FFFD>',
        'E', '<$FFFC>', 'F', '<$FFFC>', 'G', '<$FFFC>', 'H',
    )
    issues, usage = simulate_entry(e, PROF_DIALOGUE)
    # Two full balloons of 4 lines each — no overflow.
    assert 'balloon_line_overflow' not in _codes(issues)
    assert usage.balloon_count == 2
    assert len(usage.balloons) == 2


# ---------------------------------------------------------------------------
# LABEL_LOCATION polish warning
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Per-line approvals (DIALOGUE_12X4 only)
# ---------------------------------------------------------------------------

def test_approved_line_suppresses_low_line_usage_for_dialogue():
    """An approved (balloon, line) tuple silences low_line_usage in DIALOGUE."""
    e = _e('ab', '<$FFFC>', 'cdefghijkl mnop qrst uvwx yz!')
    # First line is short → would normally emit low_line_usage.
    issues_no_approval, _ = simulate_entry(e, PROF_DIALOGUE)
    assert any(i.code == 'low_line_usage' for i in issues_no_approval)
    issues_approved, _ = simulate_entry(
        e, PROF_DIALOGUE, approved_lines={(0, 0)}
    )
    assert not any(i.code == 'low_line_usage' for i in issues_approved)


def test_approved_line_does_not_silence_other_issues():
    """Approval cannot hide broken_word_wrap or balloon_line_overflow."""
    # A long word that wraps mid-word — broken_word_wrap is an error.
    e = _e('abcdefghijklmnopqrstuvwxyz')
    approved = {(0, 0), (0, 1), (0, 2)}  # approve everything
    issues, _ = simulate_entry(e, PROF_DIALOGUE, approved_lines=approved)
    codes = _codes(issues)
    assert 'broken_word_wrap' in codes  # not suppressed
    assert 'implicit_wrap_without_fffc' in codes  # not suppressed


def test_approvals_ignored_for_label_profiles():
    """Approvals only apply to DIALOGUE_12X4. LABEL/NARRATION ignore them."""
    e = _e('ab', terminator='FFFF')
    # Approval set provided, but LABEL_CHARACTER_12X1 ignores it.
    # In single-line LABEL profile, low_line_usage isn't emitted as
    # a non-final-line warning anyway, so this just verifies no crash.
    issues, _ = simulate_entry(e, PROF_LABEL_CHAR, approved_lines={(0, 0)})
    assert all(i.code != 'low_line_usage' for i in issues)


def test_approvals_none_default_works():
    """No approvals argument = same behavior as before approvals feature."""
    e = _e('ab', '<$FFFC>', 'cdefghijkl mnop qrst uvwx yz!')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    assert any(i.code == 'low_line_usage' for i in issues)


def test_location_label_under_16_tiles_has_no_low_line_usage():
    """Labels have NO minimum-fill rule (user spec 2026-06-17): a location
    label is valid up to 16 tiles, with NO low_line_usage warning at any
    length below the cap. The only hard limit is label_overflow (>16).

    Red state (pre-fix): LABEL_LOCATION_16X1 carried
    'polish_warning_above': 12, so a 13-16 tile label wrongly emitted a
    low_line_usage 'polish' warning, demoting a perfectly valid label to
    PLAYABLE.
    """
    spec = DEFAULT_PROFILE_SPECS['LABEL_LOCATION_16X1']
    e = _e('Highway Near Ransch Village', terminator='FFFF')  # ~14 tiles
    issues, usage = simulate_entry(e, spec)
    assert 12 < usage.max_line_tiles <= 16  # genuinely in the old warn band
    codes = _codes(issues)
    assert 'low_line_usage' not in codes
    assert 'label_overflow' not in codes


def test_location_label_over_16_tiles_is_overflow_error():
    """A location label exceeding the 16-tile cap is a label_overflow error
    (the only hard limit on labels)."""
    spec = DEFAULT_PROFILE_SPECS['LABEL_LOCATION_16X1']
    e = _e('Velzeria Castle, Deep Underground Vault', terminator='FFFF')
    issues, _ = simulate_entry(e, spec)
    overflow = [i for i in issues if i.code == 'label_overflow']
    assert overflow, 'a >16-tile location label must be a label_overflow error'
    assert overflow[0].detail['tilesUsed'] > 16


# ---------------------------------------------------------------------------
# Bucket semantics (per user spec 2026-05-27; implicit_wrap promoted to
# ERROR 2026-06-01):
#   ERROR    → line/balloon/label overflow OR broken word OR
#              implicit_wrap_without_fffc OR unknown profile
#   PLAYABLE → technically safe; may have low_line_usage warnings
#   POLISHED → no errors, no warnings (info advisories allowed)
# ---------------------------------------------------------------------------

def test_implicit_wrap_severity_is_error():
    """implicit_wrap_without_fffc emits as ERROR (2026-06-01): the
    convention is an explicit <$FFFC> on every visual break, because
    engine auto-wrap drags a leading space onto the next line. No line
    may rely on implicit wrap."""
    e = _e('the quick brown fox jumped over the lazy dog rapidly')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    iw = [i for i in issues if i.code == 'implicit_wrap_without_fffc']
    assert iw, 'expected at least one implicit_wrap_without_fffc'
    for i in iw:
        assert i.severity == 'error', (
            f'implicit_wrap_without_fffc must be error severity; '
            f'got {i.severity}'
        )


def test_entry_with_implicit_wrap_buckets_to_error():
    """An entry that wraps without an explicit <$FFFC> is ERROR — it is
    not shippable, the ghost-indent artifact makes it a real defect."""
    from layout_qa.metrics import bucket_status
    e = _e('hello world a b c')
    issues, _ = simulate_entry(e, PROF_DIALOGUE)
    codes = _codes(issues)
    issues_dicts = [{'code': i.code, 'severity': i.severity, 'detail': i.detail}
                    for i in issues]
    bucket = bucket_status(issues_dicts, 'DIALOGUE_12X4')
    if 'implicit_wrap_without_fffc' in codes:
        assert bucket == 'ERROR', (
            f'expected ERROR, got {bucket} with codes={codes}'
        )


# ---------------------------------------------------------------------------
# TileUsage: per-entry avg line tiles + avg fill ratio
# ---------------------------------------------------------------------------

def test_tile_usage_avg_line_tiles_single_line():
    """Single-line entry: avgLine == maxLine == minLine."""
    e = _e('hello')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    assert usage.lines_used == 1
    assert usage.avg_line_tiles == usage.max_line_tiles
    assert usage.avg_line_tiles == usage.min_line_tiles


def test_tile_usage_avg_line_tiles_explicit_breaks():
    """Three lines with explicit FFFC breaks. Verify avg = mean of the
    three line costs and avgFillRatio = avg / width."""
    # Each "abc" is 3 ASCII chars; with bigrams it may collapse, so test
    # the equation rather than absolute counts.
    e = _e('abc', '<$FFFC>', 'abc', '<$FFFC>', 'abc')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    assert usage.lines_used == 3
    # Inside-out: max >= avg >= min (always for a non-empty list).
    assert usage.max_line_tiles >= usage.avg_line_tiles >= usage.min_line_tiles
    # avgFillRatio must match avg / width (width=12 for PROF_DIALOGUE).
    expected = round(usage.avg_line_tiles / 12, 4)
    assert usage.avg_fill_ratio == expected


def test_tile_usage_avg_zero_when_no_lines():
    """Empty entry → no lines, avgLine=0, avgFillRatio=0."""
    e = _e('')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    assert usage.avg_line_tiles == 0.0
    assert usage.avg_fill_ratio == 0.0


# ===========================================================================
# Per-balloon, per-line records for the Entry Inspector (gap 1, schema 0.3.0)
# ---------------------------------------------------------------------------
# `usage.balloons[*].lines[*]` carries the simulated layout for the
# eventual React/ECharts Inspector. Each line records its index in the
# balloon, the tile count, the fill ratio against the budget, and the
# text content that landed on it.
# ===========================================================================

def test_balloons_record_present_on_single_line_entry():
    """Trivial entry → one balloon with one line."""
    e = _e('hello')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    assert len(usage.balloons) == 1
    b = usage.balloons[0]
    assert b['index'] == 0
    assert len(b['lines']) == 1
    line = b['lines'][0]
    assert line['index'] == 0
    assert line['tiles'] == usage.max_line_tiles
    assert isinstance(line['fillRatio'], float)
    assert 'hello' in line['text']


def test_balloons_record_with_explicit_fffc_breaks():
    """Three explicit-FFFC lines → one balloon with three lines."""
    e = _e('abc', '<$FFFC>', 'defg', '<$FFFC>', 'hi')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    assert len(usage.balloons) == 1
    lines = usage.balloons[0]['lines']
    assert len(lines) == 3
    assert [l['index'] for l in lines] == [0, 1, 2]
    # Each line's text contains its content.
    assert 'abc' in lines[0]['text']
    assert 'defg' in lines[1]['text']
    assert 'hi' in lines[2]['text']


def test_balloons_record_splits_on_fffd():
    """FFFD opens a new balloon record."""
    e = _e('hi', '<$FFFD>', 'bye')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    assert len(usage.balloons) == 2
    assert usage.balloons[0]['index'] == 0
    assert usage.balloons[1]['index'] == 1
    assert 'hi' in usage.balloons[0]['lines'][0]['text']
    assert 'bye' in usage.balloons[1]['lines'][0]['text']


def test_balloons_record_protagonist_token_in_text():
    """The F600/0000 token is rendered as its literal form so the
    inspector can show the placeholder visually."""
    e = _e(('text', 'Hi '), ('token', PROTAGONIST_TOKEN))
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    # 'Hi ' (3 chars + token literal) — single line.
    line = usage.balloons[0]['lines'][0]
    assert 'Hi ' in line['text']
    assert PROTAGONIST_TOKEN in line['text']


def test_balloons_record_skips_other_ctrl_codes():
    """Control codes other than FFFC/FFFD/FFFE/FFFF (e.g. FFFB pause)
    aren't visible text — exclude them from per-line text."""
    e = _e('hi', '<$FFFB>', 'bye')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    # Both 'hi' and 'bye' land on the same line, no FFFB in the text.
    text = usage.balloons[0]['lines'][0]['text']
    assert 'hi' in text and 'bye' in text
    assert 'FFFB' not in text and '<$' not in text


def test_balloons_record_last_balloon_finalized_at_entry_end():
    """The closing line of the last balloon must end up in balloons[]
    (no off-by-one losing the tail)."""
    e = _e('ab', '<$FFFC>', 'cd', '<$FFFD>', 'ef', '<$FFFC>', 'gh')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    assert len(usage.balloons) == 2
    assert len(usage.balloons[0]['lines']) == 2
    assert len(usage.balloons[1]['lines']) == 2
    # Final line of final balloon contains 'gh'.
    assert 'gh' in usage.balloons[1]['lines'][1]['text']


def test_balloons_record_tile_counts_consistent_with_max_line():
    """The max tile-count across balloons[*].lines[*] must equal
    usage.max_line_tiles (no drift between the two views)."""
    e = _e('aaa', '<$FFFC>', 'bbbbbbbb', '<$FFFC>', 'c')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    line_tiles = [l['tiles'] for b in usage.balloons for l in b['lines']]
    assert max(line_tiles) == usage.max_line_tiles
    assert min(line_tiles) == usage.min_line_tiles


def test_balloons_record_fill_ratio():
    """fillRatio = tiles / width, rounded."""
    e = _e('hello')
    _, usage = simulate_entry(e, PROF_DIALOGUE)
    line = usage.balloons[0]['lines'][0]
    assert line['fillRatio'] == round(line['tiles'] / 12, 4)
