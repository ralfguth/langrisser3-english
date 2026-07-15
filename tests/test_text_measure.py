"""test_text_measure.py — unit + parity for tools/text_measure.py.

The parity test pins `measure_tiles(text)` against the canonical
byte-emitter `d00_tools.encode_text_to_entry` (file `d00_tools.py`,
lines 154-285). If anyone changes the encoder's greedy rules and
doesn't sync `text_measure.py`, the parity test catches it.
"""

import os
import sys
import random
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from text_measure import measure_tiles, iter_tiles, SPECIAL_TOKEN_WIDTHS
from d00_tools import encode_text_to_entry
from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_special_token_widths_f600_locked_at_8():
    """Decision F: protagonist token worst-case = 8 zenkaku tiles."""
    assert SPECIAL_TOKEN_WIDTHS['<$F600><$0000>'] == 8


# ---------------------------------------------------------------------------
# Basic behavior
# ---------------------------------------------------------------------------

def test_empty_string():
    assert measure_tiles('') == 0
    assert list(iter_tiles('')) == []


def test_single_char():
    assert measure_tiles('a') == 1


def test_ellipsis_collapses_to_single_tile():
    """'...' → '…' substitution (d00_tools.py:250) — one tile, not three."""
    assert measure_tiles('...') == 1
    assert measure_tiles('…') == 1
    assert measure_tiles('a...b') == measure_tiles('a…b')


def test_bigram_is_one_tile():
    """A pair in BIGRAM_TILE_MAP collapses to one tile."""
    # ('t', 'h') is in the map; ('h', 'e') is also there.
    # Greedy left-to-right picks ('t','h') first, then 'e' single.
    assert ('t', 'h') in BIGRAM_TILE_MAP, 'fixture invariant: th must be in BIGRAM_TILE_MAP'
    assert ('h', 'e') in BIGRAM_TILE_MAP, 'fixture invariant: he must be in BIGRAM_TILE_MAP'
    assert measure_tiles('the') == 2  # 'th' + 'e'


def test_iter_tiles_yields_per_tile_with_source_substring():
    """iter_tiles yields (substring, 1) per emitted tile."""
    result = list(iter_tiles('the'))
    assert len(result) == 2
    assert result[0] == ('th', 1)
    assert result[1] == ('e', 1)


def test_unmapped_char_is_silently_dropped():
    """Encoder drops chars not in CHAR_TILE_MAP nor any bigram — measured
    cost stays equal to the canonical encoder for the same input (parity
    holds even with unmapped chars in the middle)."""
    unmapped = '\x01'  # control char, not in any map
    assert unmapped not in CHAR_TILE_MAP
    s = f'a{unmapped}b'
    expected = len(encode_text_to_entry(s, CHAR_TILE_MAP, BIGRAM_TILE_MAP)) // 2
    assert measure_tiles(s) == expected


def test_trailing_space_skip_mid_segment():
    """After a tile with right-blank, an ASCII space mid-segment is
    skipped (d00_tools.py:262-267). 'a b' should cost the same as the
    encoder would emit."""
    # We compare to the canonical encoder rather than a hard-coded
    # number, because the cost depends on which bigrams exist.
    expected = len(encode_text_to_entry('a b', CHAR_TILE_MAP, BIGRAM_TILE_MAP)) // 2
    assert measure_tiles('a b') == expected


def test_skipped_space_is_represented_not_disregarded():
    """A space after a right-blank char (e.g. after ',') is PACKED into that
    char's (char,' ') bigram under the data-driven font's complete (c,space)
    coverage. The encoder writes no separate space tile, so it adds no extra
    width, and the space IS occupied in the balloon (the bigram's right half).
    iter_tiles emits the bigram (e.g. ', ') as one substring whose text includes
    the space, so the reconstruction stays faithful (the space is never silently
    dropped). The old separate zero-cost 'skipped space' tile is superseded."""
    s = 'duty, not'
    tiles = list(iter_tiles(s))
    # Reconstruction is faithful — the space lives in the ', ' bigram substring.
    assert ''.join(sub for sub, _ in tiles) == 'duty, not'
    # The space contributes no extra tile (it is the right half of the ', ' bigram).
    assert measure_tiles(s) == \
        len(encode_text_to_entry(s, CHAR_TILE_MAP, BIGRAM_TILE_MAP)) // 2
    # The space is packed into a cost-1 bigram, not a separate zero-cost tile.
    zero_cost = [sub for sub, cost in tiles if cost == 0]
    assert zero_cost == []


def test_skipped_space_reconstruction_matches_source_visible_text():
    """For a line with several punctuation-skip spaces, the reconstructed
    visible text equals the source (no space silently dropped)."""
    s = 'And so, my explanation is over.'
    recon = ''.join(sub for sub, _ in iter_tiles(s))
    assert recon == s


def test_next_is_inline_propagates_skip_across_boundary():
    """When the segment ends with a right-blank-carrying tile AND the
    next segment is inline (e.g. <$F600><$0000>), the trailing space
    is skipped just like mid-segment."""
    # Trailing space scenario where the encoder skip applies only when
    # next_is_inline=True. Take a string ending in a right-blank tile
    # followed by ' ' followed by inline-ctrl boundary.
    text = 'a '  # 'a' is in RIGHT_BLANK_STANDALONE_CHARS
    without_inline = measure_tiles(text, next_is_inline=False)
    with_inline = measure_tiles(text, next_is_inline=True)
    # Inline path skips the trailing space; default path keeps it.
    assert with_inline <= without_inline


# ---------------------------------------------------------------------------
# Parity with canonical encoder
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def real_scen_strings():
    """Pull short visible-text-only snippets from real scen files for the
    parity sweep. Filters out lines with control codes so we test pure
    text behavior without entangling the encoder's segmentation."""
    scen_dir = PROJ / 'scripts' / 'en'
    if not scen_dir.exists():
        pytest.skip('scripts/en/ missing')
    samples = []
    for path in sorted(scen_dir.glob('scen*E.txt'))[:30]:  # sample 30 files
        for line in path.read_text(encoding='utf-8').splitlines():
            if '<$' in line or '[diehardt' in line.lower():
                continue
            line = line.strip()
            if 4 <= len(line) <= 60:
                samples.append(line)
            if len(samples) >= 200:
                break
        if len(samples) >= 200:
            break
    return samples


def test_parity_against_canonical_encoder(real_scen_strings):
    """For every sampled real-corpus line, `measure_tiles(s)` must equal
    `len(encode_text_to_entry(s, ...)) // 2`. This is the contract that
    `text_measure.py` doesn't drift from `d00_tools.py:154-285`."""
    mismatches = []
    for s in real_scen_strings:
        measured = measure_tiles(s)
        encoded_bytes = encode_text_to_entry(s, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
        expected = len(encoded_bytes) // 2
        if measured != expected:
            mismatches.append((s, measured, expected))
    assert not mismatches, (
        f'{len(mismatches)} parity mismatches; first 5: '
        f'{mismatches[:5]}'
    )


def test_parity_on_synthetic_edges():
    """Edge cases that may not appear in the natural-text corpus sample."""
    cases = [
        '',
        'a',
        'A',
        'the',
        'hello world',
        '...',
        '… …',
        "I'm here",
        'a b c d',
        'AB CD EF',
        'abc def ghi jkl',
    ]
    for s in cases:
        measured = measure_tiles(s)
        expected = len(encode_text_to_entry(s, CHAR_TILE_MAP, BIGRAM_TILE_MAP)) // 2
        assert measured == expected, (
            f'parity fail on {s!r}: measure={measured} expected={expected}'
        )
