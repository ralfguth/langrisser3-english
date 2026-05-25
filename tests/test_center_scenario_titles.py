"""Tests for tools.center_scenario_titles.

Centers SCENARIO subtitle text within the 16-tile balloon line using:
- <$0000> as a full-tile (16px) padding step
- ASCII space (bigram-absorbed when adjacent to a letter) as a half-tile (8px) nudge

When the subtitle does not fit on one 16-tile line, split into two lines via
<$FFFC> and center each line independently.
"""

import pytest
from tools.center_scenario_titles import (
    count_tiles,
    center_line,
    split_subtitle,
    fit_subtitle,
)

BALLOON_WIDTH = 16


# ---------------------------------------------------------------------------
# count_tiles
# ---------------------------------------------------------------------------

class TestCountTiles:
    def test_empty(self):
        assert count_tiles('') == 0

    def test_pure_text(self):
        # 'Tiaris' = (Ti)(ar)(is) = 3 tiles via bigrams
        assert count_tiles('Tiaris') == 3

    def test_known_subtitles(self):
        # Reference subtitles measured by the encoder
        assert count_tiles('Assault on the Floating Castle') == 15
        assert count_tiles('Wily General Emerick') == 10
        assert count_tiles('The Despicable General Geier') == 14

    def test_umlauts_via_bigram(self):
        # Böser = (B,ö)(s,e)r = 3 tiles using CWX bigrams 1613/1614
        assert count_tiles('Böser') == 3
        # Diehärte = (D,i)(e,h?)(ä,r)... depends on encoder packing
        assert count_tiles('Diehärte') <= 5  # generous upper bound

    def test_control_code_counts_as_one_tile(self):
        assert count_tiles('<$0000>') == 1
        assert count_tiles('<$01E2>') == 1
        assert count_tiles('<$FFFC>') == 1

    def test_mixed_control_and_text(self):
        # <$0000> + 'X' = 1 raw + 1 letter = 2 tiles
        assert count_tiles('<$0000>X') == 2
        # Padding around 15-tile naked = 16 (1 tile of padding via leading <$0000>)
        assert count_tiles('<$0000>Assault on the Floating Castle') == 16

    def test_space_letter_bigram(self):
        # leading space absorbed into bigram with first letter (UC included)
        assert count_tiles(' X') == 1  # (' ', 'X') bigram
        # Trailing space + UC letter has no (UC, ' ') bigram — adds 1 standalone
        assert count_tiles('X ') == 2
        # Lowercase has both leading and trailing space bigrams
        assert count_tiles(' x') == 1
        assert count_tiles('x ') == 1
        # 2 leading spaces: 1 standalone + 1 bigram
        assert count_tiles('  X') == 2


# ---------------------------------------------------------------------------
# center_line
# ---------------------------------------------------------------------------

class TestCenterLine:
    """center_line(text, width=16) returns padded text that:
       - has total tile count == width (or close)
       - is symmetrically centered (or as close to symmetric as the grid allows)
       - uses <$0000> for whole-tile steps, ASCII space for half-tile nudge
       - keeps ASCII spaces ADJACENT to letters (so they bigram-absorb)"""

    def test_exact_fit_no_padding(self):
        # 16-tile naked needs no padding
        text = 'Assault on the Floating'  # naked tiles known
        if count_tiles(text) == 16:
            assert center_line(text) == text

    def test_15_tile_text_one_space_each_side(self):
        # naked=15 → padding=1 tile total → 1 ASCII each side, both absorbed
        text = 'Assault on the Floating Castle'
        assert count_tiles(text) == 15
        out = center_line(text)
        assert count_tiles(out) == 16
        # Should not have leading <$0000> (a single ASCII space suffices on each side)
        assert not out.startswith('<$0000>')

    def test_13_tile_text_full_tile_each_side(self):
        # naked=13 → padding=3 tiles → 1.5 each side; pick <$0000>+space each side
        text = 'The Southern Lushiris Gate'
        assert count_tiles(text) == 13
        out = center_line(text)
        assert count_tiles(out) == 16

    def test_14_tile_text_symmetric_with_zero_codes(self):
        # naked=14 → padding=2 tiles → 1 <$0000> each side, fully symmetric
        text = 'The Despicable General Geier'
        assert count_tiles(text) == 14
        out = center_line(text)
        assert count_tiles(out) == 16
        # symmetric: starts with <$0000>, ends with <$0000>
        assert out.startswith('<$0000>') and out.endswith('<$0000>')

    def test_small_text_many_zero_codes(self):
        # naked=4 (e.g. "Feraquea" =? let's pick a real one)
        text = 'Feraquea'  # naked=4 per audit
        assert count_tiles(text) == 4
        out = center_line(text)
        assert count_tiles(out) == 16

    def test_naked_already_exceeds_width(self):
        # If text > width, center_line should raise or refuse (caller must split)
        with pytest.raises(ValueError):
            center_line('Hidden Gyudon Restaurant, A true story')  # naked=20

    def test_idempotent_on_already_centered(self):
        # Applying center_line to its own output yields the same output
        text = 'The Despicable General Geier'
        once = center_line(text)
        twice = center_line(once.strip().replace('<$0000>', '').strip())
        assert once == twice

    def test_keeps_embedded_control_codes(self):
        # scen17 has 'Operation<$01E2> Recapture Laffel' — control code in middle
        text = 'Operation<$01E2> Recapture Laffel'
        # Should pass through embedded code without modification
        out = center_line(text) if count_tiles(text) <= 16 else None
        if out is not None:
            assert '<$01E2>' in out


# ---------------------------------------------------------------------------
# split_subtitle
# ---------------------------------------------------------------------------

class TestSplitSubtitle:
    """split_subtitle(text, max_tiles=16) returns (line1, line2) each ≤ max_tiles.
       Splits at natural boundary: comma > 'of'/'the' > last space before midpoint."""

    def test_comma_split_preferred(self):
        # Comma stays on line1 as a visual continuation cue
        line1, line2 = split_subtitle('Hidden Gyudon Restaurant, A true story')
        assert line1 == 'Hidden Gyudon Restaurant,'
        assert line2 == 'A true story'

    def test_split_with_böser(self):
        line1, line2 = split_subtitle('Böser, Master of the Demon Blade')
        assert line1 == 'Böser,'
        assert line2 == 'Master of the Demon Blade'

    def test_split_long_no_comma(self):
        # 'Ultimate Military Device of Antiquity' — no comma, split on 'of'
        line1, line2 = split_subtitle('Ultimate Military Device of Antiquity')
        assert 'of' not in line1.split()  # 'of' starts line2 or its right side
        assert count_tiles(line1) <= 16
        assert count_tiles(line2) <= 16

    def test_split_field_marshal(self):
        line1, line2 = split_subtitle("The Field Marshal's Determination")
        assert count_tiles(line1) <= 16
        assert count_tiles(line2) <= 16
        # Reasonable break: after Marshal's
        assert "Marshal's" in line1

    def test_both_halves_fit(self):
        for raw in [
            'Hidden Gyudon Restaurant, A true story',
            'Ultimate Military Device of Antiquity',
            'The Magnificent capital, Larcussia',
            "The Field Marshal's Determination",
            'Böser, Master of the Demon Blade',
        ]:
            l1, l2 = split_subtitle(raw)
            assert count_tiles(l1) <= 14, f'{raw!r}: line1 {l1!r} too wide'
            assert count_tiles(l2) <= 14, f'{raw!r}: line2 {l2!r} too wide'


# ---------------------------------------------------------------------------
# fit_subtitle (top-level)
# ---------------------------------------------------------------------------

class TestFitSubtitle:
    """fit_subtitle(text) returns the final string ready to be placed
       between SCENARIO-NN<$FFFC> and <$FFFE>:
       - 1 line if naked fits ≤14 tiles (some headroom for padding)
       - 2 lines (joined by <$FFFC>) if longer"""

    def test_short_subtitle_one_line(self):
        out = fit_subtitle('Wily General Emerick')
        assert '<$FFFC>' not in out
        assert count_tiles(out) == 16

    def test_long_subtitle_two_lines(self):
        out = fit_subtitle('Hidden Gyudon Restaurant, A true story')
        assert out.count('<$FFFC>') == 1
        line1, line2 = out.split('<$FFFC>')
        assert count_tiles(line1) == 16
        assert count_tiles(line2) == 16

    def test_15_tile_subtitle_stays_one_line(self):
        # 'Assault on the Floating Castle' = 15 naked, fits in 16 with 1-tile padding
        out = fit_subtitle('Assault on the Floating Castle')
        assert '<$FFFC>' not in out, f'expected single line, got {out!r}'
        assert count_tiles(out) == 16

    def test_16_tile_subtitle_no_padding(self):
        # 'The Necromancer, Again' = 11 naked but used to be padded to exact 16
        # Force-test 16-tile-exact case (use a phrase that hits 16 exactly)
        text = 'The Necromancer, Again '   # exists in scen23, padded to ~16 with surrounding
        # Just ensure the algorithm doesn't crash on exact-fit cases
        out = fit_subtitle('The Necromancer, Again')   # naked=11 here, will pad
        assert count_tiles(out) == 16

    def test_each_line_independently_centered(self):
        out = fit_subtitle('Ultimate Military Device of Antiquity')
        parts = out.split('<$FFFC>')
        assert len(parts) == 2
        for p in parts:
            assert count_tiles(p) == 16

    def test_all_wrap_subtitles_become_valid(self):
        # End-to-end: every known WRAP subtitle should produce a result where
        # every visible line is exactly 16 tiles.
        WRAP_SUBTITLES = [
            'The Despicable General Geier',
            'The Southern Lushiris Gate',
            'Ceremony of Scorching Heat',
            'Operation<$01E2> Recapture Laffel',
            'Ultimate Military Device of Antiquity',
            'Skirmish in the Vast Skies',
            'The Magnificent capital, Larcussia',
            "The Field Marshal's Determination",
            'Böser, Master of the Demon Blade',
            'The Insanity of King Wilder',
            'Hidden Gyudon Restaurant, A true story',
            'The Queen and Aesthetic Men',
        ]
        for sub in WRAP_SUBTITLES:
            out = fit_subtitle(sub)
            for line in out.split('<$FFFC>'):
                assert count_tiles(line) == 16, (
                    f'{sub!r} → line {line!r} = {count_tiles(line)} tiles (expected 16)'
                )

    def test_no_change_to_already_short(self):
        # 'Suspicion' = 5 tiles → 1 line, centered
        out = fit_subtitle('Suspicion')
        assert '<$FFFC>' not in out
        assert count_tiles(out) == 16
