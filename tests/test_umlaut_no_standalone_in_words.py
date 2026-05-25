"""Assert that encoding our umlaut-bearing names NEVER falls back to
the standalone ü/ä/ö tile (1658+) mid-word — always uses a bigram.

The standalone ü tile is `ü + 8px blank right half`, which inside a
word renders as "ü " (visible word-internal gap). It exists for
contexts like name-input grid where the standalone form is intended.
In dialogue, every umlaut MUST be paired with the adjacent letter via
a (X, ü)/(ü, X)/(X, ä)/(ä, X)/(X, ö)/(ö, X) bigram.

Bug history: encoder for "of the Rigüler Empire" picks (i, g) bigram
at j=8, leaving 'ü' orphan at j=10, falling back to standalone tile
1658 → in-game shows "Rigü ler" with ~10px visible gap.

Fix: ensure BIGRAM_TILE_MAP has (ü, l), (ä, r), (ö, s) etc. for every
post-umlaut letter that occurs in our names.
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

STANDALONE_UMLAUT_TILES = {1658}   # standalone ü slot; add ä/ö if we ever paint them standalone


def _tile_ids(text: str) -> list[int]:
    """Encode text and return the tile-ID sequence."""
    raw = encode_text_to_entry(text, CHAR_TILE_MAP, BIGRAM_TILE_MAP)
    return list(struct.unpack(f">{len(raw)//2}H", raw))


UMLAUT_NAMES = [
    "Rigüler",
    "Altemüller",
    "Diehärte",
    "Böser",
]

# Build (leading_chars + name, name) for every parity (0..7 leading chars).
# Word-boundary preserved with a trailing space before the name.
PARITY_CONTEXTS = []
for name in UMLAUT_NAMES:
    for leading in range(8):
        prefix = "x" * leading + (" " if leading else "")
        PARITY_CONTEXTS.append((prefix + name, name))


class TestUmlautNoStandalone:
    """User-stated invariant (2026-05-23, emphatic):
    "LETRAS STANDALONE NO MEIO DE PALAVRAS NÃO PODEM OCORRER."

    For every umlaut-bearing canonical name, in every parity (0..7
    leading chars before the name), the encoder must NEVER fall back
    to a standalone single-char umlaut tile mid-word."""

    @pytest.mark.parametrize("text,name", PARITY_CONTEXTS)
    def test_no_standalone_umlaut_in_name_words(self, text, name):
        tiles = _tile_ids(text)
        bad = [t for t in tiles if t in STANDALONE_UMLAUT_TILES]
        if bad:
            pytest.fail(
                f"Text {text!r} (name {name!r}) encodes to tile sequence:\n"
                f"  {tiles}\n"
                f"which includes standalone umlaut tile(s) {bad}.\n"
                f"The encoder fell back to standalone because no "
                f"(prev, umlaut) OR (umlaut, next) bigram was available "
                f"at the parity position. Add the missing bigram to "
                f"_CUSTOM_UMLAUT_BIGRAMS."
            )
