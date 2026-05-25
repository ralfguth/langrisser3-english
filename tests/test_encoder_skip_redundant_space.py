"""Comprehensive tests for the encoder rule:

  Inside a text segment, when the previous emitted tile has built-in
  8px right-half blank ("right-blank tile"), and the next char is an
  ASCII space, and there is STILL TEXT in the segment after the space,
  → SKIP the space (don't emit a space tile).

Tiles with right-blank property (left content + blank right half):
  - lowercase letters as "standalone" (which is actually the (letter,' ')
    bigram tile painted from _LC_STARTS — letter at left, space at right)
  - punctuation `,` `.` `?` `!` `:` `;` (painted as _interleave(glyph, blank))
  - umlauts `ä` `ö` `ü` (painted same way)
  - extended punct like `-` `(` `)` `/` etc. (painted as _interleave(glyph, blank))

UC letters DO NOT have this property — their standalone tiles are full-
width 32-byte tiles.

User-stated invariants (2026-05-23):
  > "espaços DEPOIS de letras minusculas standalone podem ser omitidos
     pelo encoder, pq virgulas, pontos, e letras minusculas estão na
     metade esquerda e deixam um espaço em branco de 8px a direita"
  > "a ideia é que se é um standalone e depois tem um control code,
     nada acontece. isso é só durante o texto mesmo."
  > "faça o maximo de testes unitarios nas diferentes abordagens para
     evidenciar o comportamento esperado e eliminar possiveis
     comportamentos nao desejados."
"""

import sys
import struct
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "tools"))

import pytest
from tools.font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP
from tools.d00_tools import encode_text_to_entry


def _tile_ids(text: str) -> list[int]:
    raw = encode_text_to_entry(text, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
    return list(struct.unpack(f">{len(raw)//2}H", raw))


# Tile IDs we want to detect as "redundant space" candidates
SPACE_STANDALONE = CHAR_TILE_MAP[" "]
PUNCT_STANDALONE = {ch: CHAR_TILE_MAP[ch] for ch in ",.!?:;" if ch in CHAR_TILE_MAP}
UMLAUT_STANDALONE = {ch: CHAR_TILE_MAP[ch] for ch in "äöü" if ch in CHAR_TILE_MAP}
SPACE_LETTER_BIGRAMS = {
    BIGRAM_TILE_MAP[(" ", c)]
    for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if (" ", c) in BIGRAM_TILE_MAP
}


def _has_redundant_space_after_right_blank(tiles: list[int]) -> list[tuple]:
    """Return list of (position, prev_tile, redundant_tile) offenders.

    A "redundant" tile after a right-blank tile is either:
    - SPACE_STANDALONE (16px of blank)
    - A (' ', X) space-letter bigram (8px of leading blank, then X)

    Both add visible blank padding after the right-blank tile, when
    visually we already had 8px from the right-blank tile.
    """
    right_blank_tiles = set(PUNCT_STANDALONE.values()) | set(UMLAUT_STANDALONE.values())
    # LC standalone tiles (CHAR_TILE_MAP['a'..'z']) — these resolve to
    # (letter, ' ') bigram tile = left letter + blank right.
    for c in "abcdefghijklmnopqrstuvwxyz":
        if c in CHAR_TILE_MAP:
            right_blank_tiles.add(CHAR_TILE_MAP[c])
    redundant_tiles = {SPACE_STANDALONE} | SPACE_LETTER_BIGRAMS
    offenders = []
    for i in range(1, len(tiles)):
        if tiles[i] not in redundant_tiles:
            continue
        if tiles[i-1] in right_blank_tiles:
            offenders.append((i, tiles[i-1], tiles[i]))
    return offenders


# ============================================================================
# CASES WHERE THE ENCODER MUST SKIP THE SPACE
# ============================================================================

class TestSkipApplies:
    """When standalone right-blank tile is followed by ASCII space which
    is followed by more text in the same segment, the space MUST be
    skipped."""

    @pytest.mark.parametrize("text", [
        "X, Y",                       # UC + comma + space + UC
        "X. Y",                       # UC + period + space + UC
        "X! Y",                       # UC + exclam + space + UC
        "X? Y",                       # UC + question + space + UC
        "X: Y",                       # UC + colon + space + UC
        "X; Y",                       # UC + semicolon + space + UC
        "Sir, Diehärte",              # mid-text comma + space + UC
        "Hello. World",               # period + space inside sentence
        "Yes! Run",                   # exclam + space + UC
        "Wait? No",                   # question + space + UC
        "End: start",                 # colon + space + lc
        "long; short",                # semicolon + space + lc
    ])
    def test_punct_then_space_then_text_skips_space(self, text):
        tiles = _tile_ids(text)
        offenders = _has_redundant_space_after_right_blank(tiles)
        assert not offenders, (
            f"Text {text!r} still emits redundant space tile after "
            f"right-blank tile.\n  tiles: {tiles}\n  offenders: {offenders}"
        )


# ============================================================================
# CASES WHERE THE ENCODER MUST NOT SKIP (BOUNDARY/CTRL-CODE SAFETY)
# ============================================================================

class TestSkipDoesNotApply:
    """The skip rule applies ONLY mid-segment. Space at end-of-segment
    (before a control code) MUST stay — encoder must not touch it."""

    def test_space_at_segment_end_before_structural_ctrl_KEPT(self):
        """'X. <$FFFC>Y' — period + space + STRUCTURAL ctrl-code (FFFC
        newline). User: structural codes (FFFC newline, FFFD scroll,
        FFFE terminator) end the visible word stream — preserve the
        trailing space."""
        bytes_with_space = encode_text_to_entry("X. <$FFFC>Y", CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        bytes_without_space = encode_text_to_entry("X.<$FFFC>Y", CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        assert len(bytes_with_space) > len(bytes_without_space), (
            f"space before structural FFFC ctrl-code should be PRESERVED; "
            f"got {len(bytes_with_space)} == {len(bytes_without_space)}"
        )

    def test_space_at_segment_end_before_F600_SKIPPED(self):
        """'…So, <$F600><$0000>.' — comma + space + INLINE-TEXT ctrl
        F600 (player-name expansion). User (2026-05-23):
        'o do nome do protagonista é diferente, pq é um texto inline e
         não uma quebra de linha ou scroll'.
        F600 continues the visible word stream — the space MUST be
        skipped so the player name appears tight after the comma."""
        bytes_with_space = encode_text_to_entry("X, <$F600><$0000>.", CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        bytes_without_space = encode_text_to_entry("X,<$F600><$0000>.", CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        assert len(bytes_with_space) == len(bytes_without_space), (
            f"space before F600 inline-text ctrl should be SKIPPED; "
            f"got {len(bytes_with_space)} vs {len(bytes_without_space)}"
        )

    # ---------- Rule scope: positive coverage (every standalone right-blank punct) ----------

    @pytest.mark.parametrize("punct", list(',.?!:;'))
    def test_every_standalone_right_blank_punct_before_F600_skips_space(self, punct):
        """The skip rule must fire for EVERY standalone right-blank punct
        char ahead of F600. Source forces standalone encoding by using a
        single uppercase letter (no UC-letter+punct bigram exists), so
        the punct is guaranteed to come out as its standalone tile.

        Rule (user-stated 2026-05-25): "the rule is that you don't need
        to put space if the tile before the space is a standalone with
        space on the right." Standalone right-blank puncts ARE such tiles."""
        text_with    = f"X{punct} <$F600><$0000>!"
        text_without = f"X{punct}<$F600><$0000>!"
        a = encode_text_to_entry(text_with,    CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        b = encode_text_to_entry(text_without, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        assert a == b, (
            f"standalone '{punct}' before space+F600: skip rule must fire."
            f"\n  with    space: {a.hex()}"
            f"\n  without space: {b.hex()}"
        )

    # ---------- Rule scope: negative coverage (bigrams MUST keep the space) ----------

    @pytest.mark.parametrize("text", [
        "Hello, <$F600><$0000>.",   # 'o,' bigram — NOT standalone
        "Yes, <$F600><$0000>.",     # 's,' bigram
        "Sir? <$F600><$0000>!",     # 'r?' bigram
    ])
    def test_bigram_with_right_blank_punct_BEFORE_F600_keeps_space(self, text):
        """Negative coverage: when the punct is part of a bigram (e.g.
        'o,' tile, not standalone ','), the skip rule MUST NOT fire.
        Per user (2026-05-25): "it's not any punctuation, it has to be
        standalone punctuation." Bigram tiles don't carry the right-blank
        property even if their right half is a small punct glyph — the
        space tile after them must be preserved so the rendered glyphs
        don't collide visually with the F600 substitution."""
        without_space = text.replace(" <$F600>", "<$F600>")
        a = encode_text_to_entry(text, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        b = encode_text_to_entry(without_space, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        assert a != b and len(a) > len(b), (
            f"bigram-ending-in-punct before F600: space must be KEPT."
            f"\n  with    space: {a.hex()}"
            f"\n  without space: {b.hex()}"
        )

    # ---------- Rule scope: negative coverage (non-right-blank chars MUST keep the space) ----------

    @pytest.mark.parametrize("text", [
        "Z <$F600><$0000>!",        # bare UC letter — not right-blank
        "X- <$F600><$0000>!",       # hyphen — explicitly excluded from right-blank set
        "•<$F600><$0000>!",         # bullet — explicitly excluded
    ])
    def test_non_right_blank_tile_before_F600_keeps_space(self, text):
        """Negative coverage: only the chars in the documented right-blank
        standalone set may trigger the skip. UC letters and the explicitly
        full-width '-' and '•' chars must NOT trigger it."""
        without_space = text.replace(" <$F600>", "<$F600>")
        a = encode_text_to_entry(text, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        b = encode_text_to_entry(without_space, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        # Either lengths differ (skip didn't fire) OR there was no space to skip
        if ' <$F600>' in text:
            assert len(a) > len(b), (
                f"non-right-blank tile before F600: space must be KEPT."
                f"\n  with    space: {a.hex()}"
                f"\n  without space: {b.hex()}"
            )


    def test_no_space_means_no_skip(self):
        """'X.<$FFFC>Y' — no space at all; encoder behavior unchanged."""
        tiles_a = _tile_ids("X.<$FFFC>Y")
        # Should encode to: X, ., FFFC, Y — 4 tiles
        # Just verify no crash and FFFC is present in the right place
        assert 0xFFFC in tiles_a

    def test_lc_space_lc_uses_bigram_no_standalone(self):
        """'hello world' — encoder picks (h,e)(l,l)(o, )(w,o)(r,l)(d, ).
        No standalone space tile (space absorbed). Skip-rule wouldn't fire
        because no standalone space exists."""
        tiles = _tile_ids("hello world")
        assert SPACE_STANDALONE not in tiles, (
            f"'hello world' should pack via (o, ' ') bigram; got {tiles}"
        )

    def test_space_between_two_uc_words_kept_as_bigram(self):
        """'Hello World' — H/W are UC standalones. Space between them
        becomes (' ', 'W') bigram (blank+W). NOT a standalone space —
        skip-rule shouldn't fire."""
        tiles = _tile_ids("Hello World")
        assert SPACE_STANDALONE not in tiles


# ============================================================================
# CONTROL-CODE BOUNDARY CASES
# ============================================================================

class TestControlCodeBoundaries:
    """Behavior at the boundary between a text segment and a control code."""

    def test_punct_then_ctrl_unchanged(self):
        """'X.<$FFFC>Y' — period directly followed by control code (no
        space). Standalone . is fine; nothing to skip."""
        tiles = _tile_ids("X.<$FFFC>Y")
        period_tile = CHAR_TILE_MAP.get(".")
        ffcc_index = tiles.index(0xFFFC)
        # The period should appear right before FFFC
        assert tiles[ffcc_index - 1] == period_tile

    def test_lc_then_ctrl_unchanged(self):
        """'word<$FFFC>next' — lc 'd' as right side of (r,d) bigram or
        (d,' ') if there's a hidden space... actually no. Just (d, X)
        if next char is X. End of segment after 'd' = standalone (d, ' ')
        bigram (the LC standalone slot). Encoder emits this tile; then
        ctrl-code. No space to skip."""
        tiles = _tile_ids("word<$FFFC>next")
        ffcc_index = tiles.index(0xFFFC)
        # The 'd' tile (or whatever bigram ending) should be just before FFFC
        # No assertion needed beyond it doesn't crash; ensure FFFC present
        assert ffcc_index > 0

    def test_ctrl_then_space_then_text_kept(self):
        """'<$F600>X' (no space) and '<$F600> X' (with space leading
        new segment) — leading space in new segment should be kept
        because it's not after a right-blank tile (it's after a ctrl
        code that has no right-blank semantics)."""
        tiles = _tile_ids("<$F600> X")
        # The leading space in the new segment should produce a (' ', 'X')
        # bigram (1 tile) — that's the optimal encoding, not a skip.
        space_X_bigram = BIGRAM_TILE_MAP.get((" ", "X"))
        if space_X_bigram is not None:
            assert space_X_bigram in tiles


# ============================================================================
# DOUBLE-SPACE AND EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Adjacent spaces, leading/trailing spaces, mixed contexts."""

    def test_punct_double_space_skips_first_only_or_both(self):
        """'X.  Y' (double space). After period (right-blank), the FIRST
        space is redundant. Whether the second is too depends on what
        comes next. Acceptable: skip first space at minimum."""
        tiles_single = _tile_ids("X. Y")
        tiles_double = _tile_ids("X.  Y")
        # Double-space version should NOT have MORE space tiles than the
        # single (the skip might collapse some). At worst, same count.
        space_count_single = sum(1 for t in tiles_single if t == SPACE_STANDALONE)
        space_count_double = sum(1 for t in tiles_double if t == SPACE_STANDALONE)
        assert space_count_double <= space_count_single + 1, (
            f"double-space should not blow up; single={space_count_single}, "
            f"double={space_count_double}"
        )

    def test_single_segment_punct_at_end_no_skip(self):
        """'Hello.' (period at end of text, no space after) — period
        standalone is fine; nothing to skip."""
        tiles = _tile_ids("Hello.")
        # Just verify no exception and SPACE_STANDALONE not present
        assert SPACE_STANDALONE not in tiles

    def test_multiple_punct_in_row(self):
        """'X... Y' (ellipsis encoded as '…' tile, then space then Y).
        The encoder maps '...' → '…' (single ellipsis char). After …
        standalone there's space + Y."""
        tiles = _tile_ids("X... Y")
        # Whatever the exact composition, ensure it doesn't crash
        assert len(tiles) > 0

    def test_punct_space_punct_pattern(self):
        """'Hi, , bye' — comma + space + comma is contrived but should
        not crash or produce weirdness."""
        tiles = _tile_ids("Hi, , bye")
        assert len(tiles) > 0


# ============================================================================
# REAL-WORLD-LIKE LINES FROM THE GAME
# ============================================================================

class TestRealWorldLines:
    """Lines that match common dialogue patterns in our EN scripts."""

    @pytest.mark.parametrize("line", [
        "Gerold, then. You may prove a worthy foe.",
        "I am Varna, General of the Rigüler Empire!",
        "It can't be helped. Don't worry about it.",
        "Yes, Father.",
        "Of course! Let's go.",
    ])
    def test_dialogue_line_no_redundant_space(self, line):
        tiles = _tile_ids(line)
        offenders = _has_redundant_space_after_right_blank(tiles)
        assert not offenders, (
            f"Dialogue {line!r} has redundant space-after-right-blank.\n"
            f"  tiles: {tiles}\n  offenders: {offenders}"
        )
