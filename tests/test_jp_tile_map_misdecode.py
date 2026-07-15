"""test_jp_tile_map_misdecode.py — guard against the JP decode-table mis-decode.

Red state (pre-fix): ``data/jp/tile_map.json`` was built with ~21 tile
indices carrying the WRONG character value. Each mislabeled tile shared a
value with another tile (a duplicate-value collision), so its true reading
was lost and every occurrence decoded as the wrong kanji/kana. The most
visible symptom: 見 (one of the most common kanji) had ZERO occurrences in
the decoded JP corpus while 暴 had 334 — because tile 461 (glyph 目+儿 = 見)
was labeled 暴, shadowing the real 暴 tile (612).

Evidence (glyph render + raw-byte context, all triangulated):
  461 暴→見  1090 。→逃  469 先→失  1174 か→楽  942 の→南  1329 ！→酋
  1133 す→談 683 ハ→青  1132 で→冗 1152 な→恩 924 は→祈 1184 ん→虜
  1198 を→訪 1474 エ→湖 1249 編→騙 1411 撃→郊 1390 鹿→麗 1616 式→盤
  1617 ン→滞 22 ゲ→Ｆ  42 Ｇ→Ｚ
(ー[48,219] is genuine font redundancy — both tiles ARE ー — not a bug.)

These tests pin the end-state: the repo decode map maps each tile to its
true character, the previously-shadowed characters are decodable again, and
the real decoded artifact (cache/d00_jp.dat → text) contains 見 (and the
other restored chars) instead of the wrong ones.
"""
import json
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from d00_tools import parse_d00

REPO_MAP = PROJECT / "data" / "jp" / "tile_map.json"
JP_D00 = PROJECT / "cache" / "d00_jp.dat"

# Single source of truth: tile index -> TRUE character (the corrected value).
# Left column is what the buggy table claimed; we assert the corrected value.
CORRECTIONS = {
    461: "見", 1090: "逃", 469: "失", 1174: "楽", 942: "南", 1329: "酋",
    1133: "談", 683: "青", 1132: "冗", 1152: "恩", 924: "祈", 1184: "虜",
    1198: "訪", 1474: "湖", 1249: "騙", 1411: "郊", 1390: "麗", 1616: "盤",
    1617: "滞", 22: "Ｆ", 42: "Ｚ",
}

# The wrong value each tile used to carry (shadowing the real tile listed).
# After the fix, each of these characters must map to exactly ONE tile.
SHADOWED = {
    "見": 461, "逃": 1090, "失": 469, "楽": 1174, "南": 942, "酋": 1329,
    "談": 1133, "青": 683, "冗": 1132, "恩": 1152, "祈": 924, "虜": 1184,
    "訪": 1198, "湖": 1474, "騙": 1249, "郊": 1411, "麗": 1390, "盤": 1616,
    "滞": 1617, "Ｆ": 22, "Ｚ": 42,
}


def load_map():
    return {int(k): v for k, v in json.loads(REPO_MAP.read_text()).items()}


def decode_corpus():
    """Decode every D00 text entry to a single string using the repo map.

    Mirrors dump_jp_scripts.decode_entry: 2-byte BE words, >=0xF000 are
    control codes (F600 carries a param word), else a tile lookup.
    """
    tile_map = load_map()
    sections = parse_d00(JP_D00.read_bytes())
    out = []
    for section in sections:
        for entry in section.entries:
            i = 0
            while i < len(entry) - 1:
                word = struct.unpack_from(">H", entry, i)[0]
                i += 2
                if word >= 0xF000:
                    if word == 0xF600 and i < len(entry) - 1:
                        i += 2
                    continue
                out.append(tile_map.get(word, ""))
    return "".join(out)


def test_each_tile_maps_to_true_character():
    """Red: e.g. map[461] == '暴' (wrong). Green: map[461] == '見'."""
    m = load_map()
    wrong = {t: m.get(t) for t, ch in CORRECTIONS.items() if m.get(t) != ch}
    assert not wrong, f"tiles still mislabeled: {wrong}"


def test_restored_characters_map_to_exactly_one_tile():
    """No residual duplicate-value collision for any restored character.

    Red: 見 maps to nothing and 暴 maps to {461, 612}. Green: 見 -> {461}
    only, and each restored char resolves to its single tile.
    """
    m = load_map()
    for ch, tile in SHADOWED.items():
        tiles = [t for t, v in m.items() if v == ch]
        assert tiles == [tile], f"{ch!r} should map only to tile {tile}, got {tiles}"


@pytest.mark.skipif(not JP_D00.exists(), reason="cache/d00_jp.dat not present")
def test_ken_present_in_decoded_corpus():
    """Effective behavior: the real decoded artifact contains 見.

    Red: 見 appears 0 times (every 見 came out as 暴). Green: 見 appears
    hundreds of times across the JP dialogue.
    """
    corpus = decode_corpus()
    assert corpus.count("見") > 100, "見 still missing from decoded JP corpus"


@pytest.mark.skipif(not JP_D00.exists(), reason="cache/d00_jp.dat not present")
def test_high_frequency_restored_chars_decodable():
    """逃 / 失 / 楽 / 南 / 酋 must now appear in the decoded corpus (were 0)."""
    corpus = decode_corpus()
    missing = [c for c in ("逃", "失", "楽", "南", "酋", "青", "恩", "虜")
               if corpus.count(c) == 0]
    assert not missing, f"restored chars still absent from corpus: {missing}"
