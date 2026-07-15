"""TDD gate for fntsys2 (save / data-management messages) — FNT_SYS pair 1.

Two invariants are locked here, both grounded in the JP binary (decoded with
JP's OWN tile_map) rather than in the stale 0.2 patch archive:

1. No inherited 0.2 patch broken-word/ornament tile-position codes remain. We owned
   these by copying 0.2 patch tile indices verbatim; in our font they render as
   pre-composed fragments/ornaments instead of clean text:
     0x05E0 = "Sc"  (was "<$05E0>reen" = Screen, x2)
     0x0608 = "d-"  (was "Mi<$0608>battle" = Mid-battle)
     0x0622/0x0623/0x0624 = "**"/"n*"/"* "  (the "Caution" asterisk banner)
   The fix replaces them with clean ASCII the encoder renders from real bigrams
   (verified: "Mid-battle" -> normal d- tile 0x008B, NOT the 0.2 patch 0x0608).

2. Leading full-width-blank (tile 0 = U+3000, written "<$0000>") is NOT uniform
   "number reservation". The JP-vs-ours alignment (records map 1:1, 40==40)
   shows two distinct classes:
     - save-slot STATE descriptors [31] 面の途中から, [36] 次のシナリオへ,
       [39] 面の作戦準備から carry leading U+3000 (3, 5, 3) reserving the fixed
       pixel slot where the engine prints the scenario number. EN must MIRROR
       the JP count (else the number overprints the text — the [39] bug the user
       reported). [31]/[36] are playtest-pending.
     - message/composition records [0],[1],[2],[21],[22] also carry JP leading
       U+3000, but the EN was restructured (already uses half-width leading
       separators); adding full-tile blanks there would wrongly indent message
       text. EN leading MUST stay 0 for these.
"""

import struct
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from fnt_sys_tools import parse_fnt_sys, encode_fntsys, _build_fntsys_char_map  # noqa: E402

FNTSYS2 = PROJ / "scripts" / "en" / "fntsys2E.txt"
JP_FNTSYS = PROJ / "cache" / "fnt_sys_jp.bin"
PAIR = 1                       # fntsys2 == FNT_SYS pair index 1
EXPECTED_RECORDS = 40

# 0.2 patch-area tile codes that render broken words/ornaments in our font.
BROKEN_CRUFT = (0x05E0, 0x0608, 0x0622, 0x0623, 0x0624)

# JP-grounded leading-<$0000> rule (see module docstring).
SAVE_DESCRIPTOR_LEADING = {31: 3, 36: 5, 39: 3}   # mirror JP, fixed number slot
MESSAGE_NO_LEADING = (0, 1, 2, 21, 22)            # EN restructured -> must be 0


def _en_records():
    return [l.rstrip("\n") for l in FNTSYS2.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def _leading_blanks(line: str) -> int:
    n, s = 0, line
    while s.startswith("<$0000>"):
        n += 1
        s = s[len("<$0000>"):]
    return n


def _jp_leading_tile0(rec: bytes) -> int:
    n = 0
    for i in range(0, len(rec) - 1, 2):
        if struct.unpack_from(">H", rec, i)[0] == 0x0000:
            n += 1
        else:
            break
    return n


# --- invariant 1: no broken-word cruft in the shipped file ----------------

def test_no_broken_word_cruft_in_shipped_file():
    text = FNTSYS2.read_text(encoding="utf-8")
    present = [f"0x{c:04X}" for c in BROKEN_CRUFT if f"<${c:04X}>" in text]
    assert present == [], (
        f"fntsys2E.txt still contains broken-word 0.2 patch codes {present}; "
        f"replace with clean ASCII text"
    )


def test_clean_words_present():
    text = FNTSYS2.read_text(encoding="utf-8")
    assert text.count("Screen") >= 2, "both Management Screen lines must be clean"
    assert "Mid-battle" in text
    assert "Caution" in text


@pytest.mark.skipif(not JP_FNTSYS.exists(), reason="JP FNT_SYS baseline absent")
def test_built_records_have_no_cruft_tiles():
    """The encoded fntsys2 must not emit any broken-word 0.2 patch tile id."""
    out = encode_fntsys(JP_FNTSYS.read_bytes(), PROJ / "scripts" / "en")
    pair = parse_fnt_sys(out).pairs[PAIR]
    bad = []
    for ri, rec in enumerate(pair.records):
        ids = {struct.unpack_from(">H", rec, i)[0]
               for i in range(0, len(rec) - 1, 2)}
        hit = ids & set(BROKEN_CRUFT)
        if hit:
            bad.append((ri, sorted(hex(h) for h in hit)))
    assert bad == [], f"built fntsys2 records still carry cruft tiles: {bad}"


# --- invariant 2: leading-<$0000> matches the JP-grounded rule -------------

def test_save_descriptor_leading_mirrors_jp():
    recs = _en_records()
    for ri, want in SAVE_DESCRIPTOR_LEADING.items():
        got = _leading_blanks(recs[ri])
        assert got == want, (
            f"record [{ri}] (save-slot descriptor) must reserve {want} leading "
            f"<$0000> for the scenario-number slot (JP count); got {got}"
        )


def test_message_records_have_no_leading_blank():
    recs = _en_records()
    for ri in MESSAGE_NO_LEADING:
        got = _leading_blanks(recs[ri])
        assert got == 0, (
            f"record [{ri}] is message text (EN restructured) and must NOT be "
            f"indented; remove its {got} leading <$0000>"
        )


@pytest.mark.skipif(not JP_FNTSYS.exists(), reason="JP FNT_SYS baseline absent")
def test_save_descriptor_leading_equals_jp_ground_truth():
    """Cross-check the hard-coded counts against the live JP binary."""
    jp_pairs = parse_fnt_sys(JP_FNTSYS.read_bytes()).pairs[PAIR].records
    for ri, want in SAVE_DESCRIPTOR_LEADING.items():
        assert _jp_leading_tile0(jp_pairs[ri]) == want, (
            f"JP record [{ri}] leading U+3000 != {want}; update the rule"
        )


# --- structural integrity --------------------------------------------------

@pytest.mark.skipif(not JP_FNTSYS.exists(), reason="JP FNT_SYS baseline absent")
def test_encode_fntsys_accepts_fntsys2():
    out = encode_fntsys(JP_FNTSYS.read_bytes(), PROJ / "scripts" / "en")
    assert parse_fnt_sys(out).pairs[PAIR].record_count == EXPECTED_RECORDS
