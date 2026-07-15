"""test_jp_tile_map_ascii_mislabel.py — guard the 'r'→ざ unique-value mis-decode.

Red state (pre-fix): tile 67 was mapped to the half-width ASCII letter 'r' in
``data/jp/tile_map.json`` but its glyph is ざ (さ + dakuten). This is a
*unique-value* mis-decode: the tile is neither a duplicate-value collision nor
an unmapped hole, so neither earlier audit caught it. It surfaced (168×) only
when the whole decoded corpus was aligned character-by-character against
CyberWarriorX's JP dump: ours showed bare 'r' where the dump had ざ —
でござる→"でごrる", ございます→"ごrいます", 招かれざる→"招かれrる".

A bare half-width ASCII letter wedged between kana is the signature of this bug
class (real JP D00 text uses full-width Latin like ＡＴ, never half-width a-z
inside a word). These tests pin tile 67 = ざ and assert the signature is absent
from the decoded corpus.
"""
import json
import re
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from d00_tools import parse_d00

REPO_MAP = PROJECT / "data" / "jp" / "tile_map.json"
JP_D00 = PROJECT / "cache" / "d00_jp.dat"

KANA = r"぀-ヿ"  # hiragana + katakana block


def load_map():
    return {int(k): v for k, v in json.loads(REPO_MAP.read_text()).items()}


def test_tile_67_is_za():
    """Red: map[67] == 'r'. Green: map[67] == 'ざ' (glyph = さ + dakuten)."""
    assert load_map().get(67) == "ざ"


def test_no_halfwidth_ascii_letter_adjacent_to_kana():
    """No decode maps a tile to a bare a-z/A-Z sitting next to kana.

    That adjacency is the mis-decode signature (e.g. 'r' for ざ). Full-width
    Latin (ＡＴ, ＨＰ) is fine; this only flags half-width ASCII letters whose
    map value would render glued to hiragana/katakana.
    """
    m = load_map()
    ascii_letter_tiles = {
        t: v for t, v in m.items()
        if len(v) == 1 and v.isascii() and v.isalpha()
    }
    # Half-width ASCII letters have no legitimate place in the JP glyph map;
    # the JP UI/stat text uses full-width forms (Ａ-Ｚ) instead.
    assert not ascii_letter_tiles, (
        f"tiles mapped to half-width ASCII letters (likely mis-decodes): "
        f"{ {hex(t): v for t, v in ascii_letter_tiles.items()} }"
    )


@pytest.mark.skipif(not JP_D00.exists(), reason="cache/d00_jp.dat not present")
def test_corpus_has_no_ascii_between_kana():
    """Decoded D00 must not contain a half-width a-z wedged between kana."""
    m = load_map()
    chunks = []
    for section in parse_d00(JP_D00.read_bytes()):
        for entry in section.entries:
            i = 0
            buf = []
            while i < len(entry) - 1:
                word = struct.unpack_from(">H", entry, i)[0]
                i += 2
                if word >= 0xF000:
                    if word == 0xF600 and i < len(entry) - 1:
                        i += 2
                    buf.append("\n")  # break run at control codes
                    continue
                buf.append(m.get(word, "�"))
            chunks.append("".join(buf))
    corpus = "".join(chunks)
    bad = re.findall(rf"[{KANA}][A-Za-z][{KANA}]", corpus)
    assert not bad, f"half-width ASCII wedged between kana (mis-decode): {set(bad)}"
