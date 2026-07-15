"""test_fntsys_no_jp_residue.py — no untranslated Japanese left in the UI strings.

Phase-A disembark Etapa 6 (fntsys text finalization): every fntsys*E.txt record
is English (or a structural code), with ONE deliberate exception — a small set of
full-width box/line-drawing glyphs (囗 ｜ ― ＼ ／) that are UI frame symbols, kept
byte-identical to the Japanese because they are not words. This guard fails if
any kana or non-symbol kanji creeps back into the EN UI scripts.

The handoff's "1 untranslated JP line in fntsys1" was record 98 = 囗, which is
identical to the JP source (a frame glyph), i.e. NOT a translation gap.
"""

import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

EN_DIR = PROJECT / "scripts" / "en"
KANA_KANJI = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")
# Intentional full-width UI frame/line glyphs, kept identical to JP (not words).
SYMBOL_ALLOWLIST = set("囗｜―＼／")


def test_no_japanese_words_in_fntsys_en():
    offenders = []
    for f in sorted(EN_DIR.glob("fntsys*E.txt")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            bad = [c for c in line if KANA_KANJI.match(c) and c not in SYMBOL_ALLOWLIST]
            if bad:
                offenders.append(f"{f.name}:{i}: {''.join(bad)} | {line.strip()}")
    assert not offenders, "untranslated JP in fntsys EN:\n" + "\n".join(offenders)
