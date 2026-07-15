"""test_jp_tile_map_unmapped_filled.py — guard the recovered unmapped JP tiles.

Red state (pre-fix): 147 distinct tile-words (643 occurrences) appeared inside
real JP text entries with NO entry in ``data/jp/tile_map.json``, so they
decoded as ``<$0xxx>`` holes — mostly in item/monster/skill flavour text the
strategy guide does not contain.

They were recovered by aligning each hole's surrounding (already-decoded)
context against CyberWarriorX's full Saturn JP dump shipped with the Akari
Dawn PC project (``~/romhack/langrisser3pc/script/jp/*.sjs``, Shift-JIS): the
same game text, so an ``L(.)R`` lookup in the matching scenario file yields the
exact character. 141/147 resolved with zero conflicts.

Three results were corrected against the CWX dump itself (it carries a few of
its own font mis-decodes; the true reading comes from the word + the tile
glyph):
  - 0x0639 = 籠 (籠絡), NOT CWX's 滝 — glyph has the 竹 radical, not 氵.
  - 0x029A = 憑 (憑依能力), NOT CWX's 懣 — shares the 心 footer with tile 0x0627=憑.
The remaining 6 not in the dump came from the AD terrain list (吊橋/溶岩/砂浜),
the skill list (駿足), and glyph+word (外宇宙 = 宇).

These tests pin the recovered map and assert the decoded corpus no longer has
any unmapped tile holes.
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
SCRIPTS = PROJECT / "scripts" / "jp"
TOK = re.compile(r"<\$([0-9A-F]{4})>")

# Recovered tile index -> true character (the end-state). Single source of truth.
RECOVERED = {
    0x001A: 'Ｊ', 0x0024: 'Ｔ', 0x002C: 'ｍ', 0x009F: 'ヂ', 0x00A9: 'ヌ', 0x0135: '睡',
    0x013E: '斡', 0x013F: '旋', 0x0145: '蔵', 0x0156: '版', 0x0159: '量', 0x0172: '＋',
    0x0173: '％', 0x0188: '雷', 0x0191: '兜', 0x019F: '林', 0x01AB: '吊', 0x01AD: '窟',
    0x01AE: '溶', 0x01B8: '浜', 0x01D3: '録', 0x01E2: '：', 0x01ED: '削', 0x0225: '干',
    0x0227: '宇', 0x0228: '宙', 0x023F: '積', 0x0248: '械', 0x024A: '距', 0x024D: '搬',
    0x0254: '弾', 0x025B: '尾', 0x026E: '棲', 0x0271: '型', 0x0272: '虎', 0x0278: '犬',
    0x027E: '蔽', 0x0281: '泥', 0x0282: '竹', 0x0283: '訓', 0x028A: '乞', 0x028C: '漢',
    0x0290: '侶', 0x0296: '純', 0x029A: '憑', 0x029B: '依', 0x02AD: '肌', 0x02B3: '養',
    0x02B6: '吸', 0x02B9: '透', 0x02BB: '穏', 0x02D7: '氷', 0x02E4: '鱗', 0x02E5: '覆',
    0x02E7: '洋', 0x02EC: '匠', 0x02F2: '斧', 0x0305: '彫', 0x030B: '製', 0x0312: '穂',
    0x031E: '球', 0x031F: '複', 0x0336: '樫', 0x033D: '烈', 0x0340: '絞', 0x0343: '六',
    0x0344: '菊', 0x0349: '宗', 0x0367: '芸', 0x036A: '冶', 0x0376: '丸', 0x037E: '帽',
    0x0380: '黄', 0x0382: '埋', 0x0383: '巾', 0x0391: '＆', 0x03A0: '植', 0x03B0: '採',
    0x03B5: '紋', 0x03C7: '雑', 0x03CE: '七', 0x03D4: '震', 0x03D5: '隕', 0x03D8: '瞬',
    0x03D9: '累', 0x03DA: '侍', 0x03DB: '徒', 0x03E7: '駿', 0x044D: '嬢', 0x0487: '妨',
    0x048B: '紙', 0x0495: '駒', 0x04C3: '昼', 0x0502: '勲', 0x052B: '排', 0x0554: '恨',
    0x057D: '潰', 0x057E: '錫', 0x0580: '往', 0x0581: '牢', 0x058C: '殴', 0x059B: '控',
    0x05AC: '稽', 0x05AD: '順', 0x05B6: '譲', 0x05C4: '鉢', 0x05D0: '鬼', 0x05D1: '頻',
    0x05D4: '勉', 0x05D5: '姑', 0x05D6: '磨', 0x05EC: '偽', 0x05ED: '簒', 0x05EF: '染',
    0x05F0: '踊', 0x05F1: '羅', 0x061C: '飽', 0x0623: '挽', 0x0626: '否', 0x0627: '憑',
    0x0638: '暑', 0x0639: '籠', 0x063A: '鍵', 0x063B: '荷', 0x063C: '担', 0x063D: '裁',
    0x063E: '浄', 0x0648: '週', 0x064F: '曲', 0x0652: '衡', 0x0655: '崇', 0x0656: '拝',
    0x066E: '筆', 0x0672: '健', 0x0673: '康', 0x067A: '惹', 0x067B: '吟', 0x067C: '詩',
    0x067D: '歌', 0x067F: '齢', 0x0682: '廻', 0x0684: '胆', 0x0689: '邦', 0x068A: '唯',
    0x068B: '瞼', 0x0699: '虚', 0x069A: '懇',
}


def load_map():
    return {int(k): v for k, v in json.loads(REPO_MAP.read_text()).items()}


def test_recovered_tiles_mapped():
    """Red: these tiles are absent from the map. Green: each maps to its char."""
    m = load_map()
    wrong = {f"0x{t:04X}": m.get(t) for t, ch in RECOVERED.items() if m.get(t) != ch}
    assert not wrong, f"tiles not recovered: {wrong}"


@pytest.mark.skipif(not JP_D00.exists(), reason="cache/d00_jp.dat not present")
def test_no_unmapped_holes_in_decoded_d00():
    """Effective behavior: decoding D00 leaves no <$0xxx> tile holes.

    Red: 147 distinct tile-words decode as holes. Green: every word < 0xF000 in
    a text entry resolves to a glyph (control codes >= 0xF000 are not holes).
    """
    m = load_map()
    holes = set()
    for section in parse_d00(JP_D00.read_bytes()):
        for entry in section.entries:
            i = 0
            while i < len(entry) - 1:
                word = struct.unpack_from(">H", entry, i)[0]
                i += 2
                if word >= 0xF000:
                    if word == 0xF600 and i < len(entry) - 1:
                        i += 2
                    continue
                if word not in m:
                    holes.add(word)
    assert not holes, f"unmapped tile holes remain: {sorted(hex(h) for h in holes)}"


def test_corrected_cwx_dump_errors():
    """籠 (not 滝) and 憑 (not 懣): readings corrected against the CWX dump."""
    m = load_map()
    assert m[0x0639] == '籠'   # 籠絡 — CWX dump had 滝
    assert m[0x029A] == '憑'   # 憑依能力 — CWX dump had 懣
    assert m[0x0188] == '雷'   # 雷神剣 — earlier context-guess was 魔
