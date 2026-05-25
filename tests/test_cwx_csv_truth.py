#!/usr/bin/env python3
"""test_cwx_csv_truth.py — locks build/cwx_tile_audit.csv as the source
of truth for CWX 1500-1620 tile identifications.

The user-curated CSV (`build/cwx_tile_audit.csv`, regenerable from the
PNG audit) is canonical: every entry MUST be reflected in
`_CWX_TILE_OVERRIDES` (or `_CWX_SPECIAL_BIGRAMS` for tile 1500's
encoder mapping). Untouched specials are 1488/1489/1490 (name input
function keys ADV/BAK/END) and 1630 (unused JP residue).

The CSV uses pipe ('|') as separator. Bigram entries are wrapped in
brackets like `[Sc]`; centered single-letter entries (1585-1610) have
the third column 'centralizado'.
"""
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "tools"))

CSV_PATH = Path(__file__).resolve().parent / "cwx_tile_audit_truth.csv"


def parse_csv():
    """Returns {tile_idx: (bigram_str, note)} from the audit CSV."""
    out = {}
    seen = set()
    if not CSV_PATH.exists():
        return out
    with open(CSV_PATH) as f:
        f.readline()  # header
        for line in f:
            line = line.rstrip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 2:
                continue
            try:
                tile = int(parts[0])
            except ValueError:
                continue
            bigram = parts[1].strip()
            note = parts[2].strip() if len(parts) > 2 else ""
            if bigram.startswith("[") and bigram.endswith("]"):
                bigram = bigram[1:-1]
            # Known typo in CSV: row 66 reuses "1563" but should be 1564.
            if tile == 1563 and tile in seen:
                tile = 1564
            seen.add(tile)
            out[tile] = (bigram, note)
    return out


def matches(actual, csv_bigram, note):
    """Equivalence check between CSV entry and override tuple.

    'left' mode and 'bigram' with trailing space are equivalent forms.
    """
    if "centralizado" in note:
        return actual == ("center", csv_bigram)
    if len(csv_bigram) != 2:
        return False
    l, r = csv_bigram[0], csv_bigram[1]
    if r == " " and actual == ("left", l):
        return True
    return actual == ("bigram", l, r)


class TestCwxCsvTruth(unittest.TestCase):
    def setUp(self):
        if not CSV_PATH.exists():
            self.skipTest(f"CSV not present at {CSV_PATH}")
        from font_tools import _CWX_TILE_OVERRIDES
        self.overrides = _CWX_TILE_OVERRIDES
        self.csv = parse_csv()

    def test_csv_loaded(self):
        self.assertGreater(len(self.csv), 100, "CSV should have 100+ entries")

    def test_every_csv_tile_matches_override(self):
        mismatches = []
        for tile in sorted(self.csv):
            csv_bigram, note = self.csv[tile]
            actual = self.overrides.get(tile)
            if not matches(actual, csv_bigram, note):
                mismatches.append((tile, csv_bigram, note, actual))
        if mismatches:
            self.fail(
                f"{len(mismatches)} CSV-vs-override mismatches:\n"
                + "\n".join(f"  tile {t}: csv={b!r} note={n!r} got={a}"
                            for t, b, n, a in mismatches[:20])
            )

    def test_no_extra_overrides_outside_csv(self):
        """Overrides should not include tiles that aren't in the CSV."""
        extras = sorted(set(self.overrides) - set(self.csv))
        self.assertEqual(
            extras, [],
            f"overrides include tiles not in CSV: {extras}",
        )

    def test_special_tiles_untouched(self):
        """1488/1489/1490 (name keys ADV/BAK/END) must NOT be overridden."""
        for tile in (1488, 1489, 1490):
            self.assertNotIn(
                tile, self.overrides,
                f"tile {tile} (name input function key) must stay CWX hand-drawn",
            )


if __name__ == "__main__":
    unittest.main()
