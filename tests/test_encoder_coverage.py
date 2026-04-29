#!/usr/bin/env python3
"""
test_encoder_coverage.py - Ensure no script character is silently dropped by the encoder.

The encoder in d00_tools.encode_text_to_entry() silently skips any character
that is not in CHAR_TILE_MAP and cannot form a bigram via BIGRAM_TILE_MAP.
This test catches unmapped characters before they disappear from the game.

Strips control codes (<$XXXX>) and [diehardt's name] the same way the encoder
does, then checks every remaining character.
"""

import re
import sys
from collections import Counter
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

SCRIPTS_DIR = PROJ / 'scripts' / 'en'


def _extract_text_chars(line: str) -> str:
    """Extract text characters from a script line, same as the encoder's segmenter.

    Strips:
    - <$XXXX> control codes (and their contents)
    - [diehardt's name] variable references
    - Leading/trailing whitespace
    Then applies ... -> ellipsis replacement (same as encoder).
    """
    result = []
    i = 0
    while i < len(line):
        # [diehardt's name] — handled as control code by encoder
        if line[i:].lower().startswith("[diehardt's name]"):
            i += 17
            continue
        # <$XXXX> escape sequences
        if line[i:i+2] == '<$':
            end = line.find('>', i + 2)
            if end != -1:
                i = end + 1
                continue
        result.append(line[i])
        i += 1
    text = ''.join(result)
    # Encoder replaces ... with ellipsis
    text = text.replace('...', '\u2026')
    return text


def _word_at(text: str, pos: int) -> str:
    """Extract the word surrounding position pos in text."""
    # Expand left to find word boundary
    left = pos
    while left > 0 and not text[left - 1].isspace():
        left -= 1
    # Expand right
    right = pos
    while right < len(text) and not text[right].isspace():
        right += 1
    return text[left:right]


def _find_dropped_chars():
    """Scan all EN scripts and find chars that the encoder would silently drop.

    Uses parse_script_file() to process only the entries the build pipeline
    actually encodes (skips dump headers and other metadata).

    Returns dict of char -> {'count': int, 'words': set of words containing char}.
    """
    from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP
    from d00_tools import parse_script_file

    dropped = {}  # char -> {'count': int, 'words': set}

    for script_path in sorted(SCRIPTS_DIR.glob('scen*E.txt')):
        entries = parse_script_file(script_path)
        for entry in entries:
            text = _extract_text_chars(entry)

            # Simulate encoder's greedy left-to-right scan
            j = 0
            while j < len(text):
                # Try bigram
                if j + 1 < len(text):
                    pair = (text[j], text[j + 1])
                    if pair in BIGRAM_TILE_MAP:
                        j += 2
                        continue

                # Try single char
                if text[j] in CHAR_TILE_MAP:
                    j += 1
                    continue

                # This char would be dropped
                ch = text[j]
                if ch not in dropped:
                    dropped[ch] = {'count': 0, 'words': set()}
                dropped[ch]['count'] += 1
                dropped[ch]['words'].add(_word_at(text, j))
                j += 1

    return dropped


class TestEncoderCoverage:
    """Every character in EN scripts must be encodable."""

    @pytest.fixture(scope="class")
    def dropped_chars(self):
        return _find_dropped_chars()

    def test_no_silently_dropped_chars(self, dropped_chars):
        if not dropped_chars:
            return
        total = sum(info['count'] for info in dropped_chars.values())
        lines = []
        for ch in sorted(dropped_chars, key=lambda c: dropped_chars[c]['count'], reverse=True):
            info = dropped_chars[ch]
            words = sorted(info['words'])
            word_list = ', '.join(words[:15])
            if len(words) > 15:
                word_list += f', ... (+{len(words) - 15} more)'
            lines.append(
                f"  {ch!r} (U+{ord(ch):04X}): {info['count']} occurrences "
                f"in {len(words)} unique words\n"
                f"    words: {word_list}"
            )
        report = "\n".join(lines)
        pytest.fail(
            f"{len(dropped_chars)} unmapped chars, {total} total drops:\n\n"
            f"{report}\n\n"
            f"Fix: add tiles to font_tools.py or replace chars in scripts."
        )
