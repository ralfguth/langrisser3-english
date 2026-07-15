"""Truth-lock: encoder maps vs the font-tile CSV.

The CSV (`tests/font_tile_map_complete.csv`) was REGENERATED from the maps after
the Part 6 data-driven swap (2026-06-27), which moved every bigram to a new
packed position and composes the FRESH region (tiles 46-1499) by machine — so the
original by-eye 1691-tile map (docs repo commit 4df7739) no longer matched the
moved glyphs. The regenerated CSV mirrors CHAR_TILE_MAP / BIGRAM_TILE_MAP, so for
the FRESH region this lock is currently TAUTOLOGICAL; the independent by-eye
check is to be RESTORED by re-mapping the new font from screenshots (TODO). It
still guards that the maps stay internally consistent (no two roles per tile, the
NFKC/alias folding holds) and that no encoder row goes unmapped.

CSV facts (see archive/docs/20260608/09 handoffs):
- columns: tile_dec, tile_hex, label, source, coments
- source CHAR_TILE_MAP rows wrap the label in literal single quotes
  ("': '" = standalone colon + blank half); BIGRAM rows are raw 2-char
  labels ("a ", "'s"); encoding is mixed utf-8/latin-1 per line.
- 22 real-text bigrams the user re-identified still carry source
  0.2 patch_OVERRIDE / UI_TILES (error) — they are Phase-4 input (draw+map),
  NOT current-encoder truth, so they are out of scope here.

KNOWN_EXCEPTIONS document every legitimate encoder<->CSV divergence; a
new mismatch means either a font_tools regression or a CSV correction —
resolve it explicitly, never widen the list without a reason string.
"""

import csv
import io
import sys
import unicodedata
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

from font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP  # noqa: E402

CSV_PATH = Path(__file__).resolve().parent / "font_tile_map_complete.csv"

# tile -> reason. Divergences that are CORRECT by design.
KNOWN_EXCEPTIONS = {
    44:   "engine 8-bit-loadable 's duplicate (SH-2 mov #imm) — encoder "
          "maps (',s)->1498; tile 44 is reached only by PROG_3 immediates",
    906:  "CSV label is the '?' placeholder; coments column says elipsis — "
          "the glyph is the full-width ellipsis the encoder maps as '…'",
    1656: "CSV recorded the 0.2 patch reference 'NP' glyph; our generated font "
          "draws (' ','•') here and NP lives at our own slot 1666",
    1666: "(N,P) bigram drawn post-CSV at a free kanji slot "
          "(tests/test_np_bigram_eagle.py); CSV still says UNMAPPED kanji",
    1582: "(G,R) bigram drawn post-CSV at the UNMAPPED dead-kanji slot — "
          "dialogue emphasis *GRIN*! (tests/test_dialogue_ascii_emphasis.py); "
          "CSV still says UNMAPPED kanji",
    1583: "(H,P) bigram drawn post-CSV at the UNMAPPED dead-kanji slot — "
          "ASCII HP in dialogue prose (tests/test_dialogue_ascii_emphasis.py); "
          "CSV still says UNMAPPED kanji",
}


def _load_rows() -> dict[int, dict]:
    raw = CSV_PATH.read_bytes()
    lines = []
    for ln in raw.split(b"\n"):
        try:
            lines.append(ln.decode("utf-8"))
        except UnicodeDecodeError:
            lines.append(ln.decode("latin-1"))
    rows = {}
    for r in csv.DictReader(io.StringIO("\n".join(lines))):
        if r.get("tile_dec", "").strip().isdigit():
            rows[int(r["tile_dec"])] = r
    return rows


# CSV-author ASCII approximations for glyphs that have no NFKC ASCII form.
CHAR_ALIASES = {
    "囗": "?",   # formation SQUARE — author had no ASCII stand-in
    "―": "-",   # formation LINE (U+2015 horizontal bar)
    "‐": "-",   # U+2010 hyphen glyph, labelled with ASCII '-'
}


def _repair_mojibake(s: str) -> str:
    """Undo utf-8-read-as-latin-1 ('mÃ¼' -> 'mü'); identity if not that."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _csv_label(row: dict) -> str:
    """Label normalized: mojibake repaired, CHAR-row quote wrapping
    (single or double) removed."""
    label = _repair_mojibake(row["label"])
    if (row["source"] == "CHAR_TILE_MAP" and len(label) >= 3
            and label[0] == label[-1] and label[0] in "'\""):
        return label[1:-1]
    return label


def _expected_char(ch: str) -> str:
    """Encoder char normalized to the CSV-label alphabet: NFKC folds the
    zenkaku aliases (Ａ->A, ０->0, U+3000->space) that share a tile with
    their ASCII form; CHAR_ALIASES covers glyphs NFKC cannot fold."""
    if ch in CHAR_ALIASES:
        return CHAR_ALIASES[ch]
    return unicodedata.normalize("NFKC", ch)


@pytest.fixture(scope="module")
def rows():
    if not CSV_PATH.exists():
        pytest.skip(f"visual truth CSV not present at {CSV_PATH}")
    r = _load_rows()
    assert len(r) == 1691, f"expected 1691 tiles in CSV, parsed {len(r)}"
    return r


def test_char_tile_map_matches_csv(rows):
    """Every CHAR_TILE_MAP entry must land on a CSV tile whose visual label
    is that char (standalone glyphs carry a blank half: label may pad with
    a space on either side)."""
    bad = []
    for ch, tile in sorted(CHAR_TILE_MAP.items(), key=lambda kv: kv[1] or 0):
        if tile is None or tile in KNOWN_EXCEPTIONS:
            continue
        row = rows.get(tile)
        if row is None:
            bad.append((ch, tile, "<no CSV row>"))
            continue
        want = _expected_char(ch)
        label = _csv_label(row)
        if tile == 0 and label == "(blank)" and want == " ":
            continue   # full-width blank tile; CSV uses the (blank) marker
        if label.strip() != want:
            bad.append((ch, tile, label))
    assert not bad, (
        "CHAR_TILE_MAP diverges from the visual CSV "
        f"(char, tile, csv_label): {bad}"
    )


def test_bigram_tile_map_matches_csv(rows):
    """Every BIGRAM_TILE_MAP entry must land on a CSV tile whose visual
    label is exactly the two glyph halves."""
    bad = []
    for (a, b), tile in sorted(BIGRAM_TILE_MAP.items(), key=lambda kv: kv[1]):
        if tile in KNOWN_EXCEPTIONS:
            continue
        if tile >= 1691:
            # Bigrams APPENDED past the JP 1691-tile ceiling (the data-driven
            # number/complete-coverage slices; archive/docs/
            # 20260625_font_bin_grow_spike.md). They are OUR composed glyphs,
            # not in the user's 1691-row CSV; validated by their own tests
            # (e.g. tests/test_number_bigrams.py).
            continue
        row = rows.get(tile)
        if row is None:
            bad.append((a + b, tile, "<no CSV row>"))
            continue
        if _csv_label(row) != a + b:
            bad.append((a + b, tile, row["label"]))
    assert not bad, (
        "BIGRAM_TILE_MAP diverges from the visual CSV "
        f"(pair, tile, csv_label): {bad}"
    )


def test_every_csv_encoder_row_is_mapped(rows):
    """Every CSV row the user attributed to the encoder (source CHAR/BIGRAM)
    must actually be reachable through the current maps — a row that is not
    means the encoder lost a mapping the font still draws."""
    mapped_tiles = ({t for t in CHAR_TILE_MAP.values() if t is not None}
                    | set(BIGRAM_TILE_MAP.values()))
    bad = []
    for tile, row in sorted(rows.items()):
        if row["source"] not in ("CHAR_TILE_MAP", "BIGRAM_TILE_MAP"):
            continue
        if tile in KNOWN_EXCEPTIONS:
            continue
        if tile not in mapped_tiles:
            bad.append((tile, row["label"]))
    assert not bad, (
        "CSV rows attributed to the encoder but unreachable through "
        f"CHAR_TILE_MAP/BIGRAM_TILE_MAP (tile, csv_label): {bad}"
    )
