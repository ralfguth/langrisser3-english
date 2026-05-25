#!/usr/bin/env python3
"""
test_inline_comments.py - Ensure translator comments after <$FFFE>/<$FFFF>
on the same line are stripped by the parser and never reach the encoder.

The comment notation lets translators annotate JP tone / nuance / context
co-located with the entry:

    Forgive me.<$FFFC>I swore never to wield<$FFFC>a blade again...<$FFFE> JP: 諦観, voz cansada

This file locks two invariants:

1. parse_script_file() returns identical entries with or without comments.
2. encode_text_to_entry() over those entries produces byte-identical output.
"""

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from d00_tools import parse_script_file, encode_text_to_entry, _strip_inline_comment
from font_tools import CHAR_TILE_MAP, build_bigram_tile_map

SCRIPTS_DIR = PROJECT_DIR / 'scripts' / 'en'


def _inject_comments(text: str) -> str:
    """Append a free-form comment after every terminator that ends a line."""
    out_lines = []
    note_idx = 0
    notes = [
        " JP: 諦観 — voz cansada",
        " AD spoiler? JP só diz 「悲しそう」",
        " tom seinen, não shounen",
        " duplicata intencional no JP — variante",
        " ChatGPT review: ok, manter",
    ]
    for line in text.split('\n'):
        stripped = line.rstrip()
        if stripped.endswith('<$FFFE>') or stripped.endswith('<$FFFF>'):
            line = stripped + notes[note_idx % len(notes)]
            note_idx += 1
        out_lines.append(line)
    return '\n'.join(out_lines)


class TestInlineCommentStripping(unittest.TestCase):

    def test_strip_helper_no_terminator(self):
        self.assertEqual(_strip_inline_comment('plain line'), 'plain line')

    def test_strip_helper_fffe(self):
        self.assertEqual(
            _strip_inline_comment('hello<$FFFE> a comment'),
            'hello<$FFFE>',
        )

    def test_strip_helper_ffff(self):
        self.assertEqual(
            _strip_inline_comment('Tiaris<$FFFF> name slot note'),
            'Tiaris<$FFFF>',
        )

    def test_strip_helper_latest_terminator_wins(self):
        # Latest terminator wins so structural patterns like
        # ``Right!<$FFFE><$FFFF>`` survive intact (FFFE+FFFF padding).
        self.assertEqual(
            _strip_inline_comment('Right!<$FFFE><$FFFF>'),
            'Right!<$FFFE><$FFFF>',
        )

    def test_strip_helper_comment_after_stacked_terminators(self):
        self.assertEqual(
            _strip_inline_comment('Right!<$FFFE><$FFFF> JP note'),
            'Right!<$FFFE><$FFFF>',
        )

    def test_strip_helper_preserves_inner_codes(self):
        # <$FFFC> / <$FFFD> are intra-entry, never terminators.
        line = 'line one<$FFFC>line two<$FFFD>page two<$FFFE> note'
        self.assertEqual(
            _strip_inline_comment(line),
            'line one<$FFFC>line two<$FFFD>page two<$FFFE>',
        )

    def test_strip_helper_no_op_when_already_clean(self):
        line = 'clean entry<$FFFE>'
        self.assertEqual(_strip_inline_comment(line), line)

    def test_terminator_codes_must_not_appear_inside_comments(self):
        """Contract: a translator note must not contain <$FFFE>/<$FFFF>.

        rfind picks the latest terminator on the line, so a literal
        terminator inside a comment would shift the truncation point and
        leak the rest of the comment into the entry. Document this so
        future contributors don't think it's a bug.
        """
        line = 'entry<$FFFE> note mentions <$FFFE> by mistake'
        self.assertEqual(
            _strip_inline_comment(line),
            'entry<$FFFE> note mentions <$FFFE>',
        )


class TestParserInvariance(unittest.TestCase):
    """End-to-end: scripts with vs. without inline comments parse the same."""

    SAMPLES = ['scen001E.txt', 'scen003E.txt', 'scen042E.txt', 'scen046E.txt']

    def test_entries_identical_with_comments(self):
        for name in self.SAMPLES:
            path = SCRIPTS_DIR / name
            if not path.exists():
                continue
            with self.subTest(script=name):
                original_entries = parse_script_file(path)

                annotated_text = _inject_comments(path.read_text(encoding='utf-8'))
                with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.txt', encoding='utf-8', delete=False
                ) as tmp:
                    tmp.write(annotated_text)
                    tmp_path = Path(tmp.name)
                try:
                    annotated_entries = parse_script_file(tmp_path)
                finally:
                    tmp_path.unlink(missing_ok=True)

                self.assertEqual(
                    original_entries,
                    annotated_entries,
                    f"{name}: inline comments altered parsed entries",
                )


class TestEncoderInvariance(unittest.TestCase):
    """Comments must never change a single byte the encoder produces."""

    SAMPLES = ['scen001E.txt', 'scen003E.txt', 'scen042E.txt', 'scen046E.txt']

    @classmethod
    def setUpClass(cls):
        cls.bigram_map = build_bigram_tile_map()

    def _encode_all(self, entries):
        return [
            encode_text_to_entry(e, CHAR_TILE_MAP, self.bigram_map)
            for e in entries
        ]

    def test_encoded_bytes_identical_with_comments(self):
        for name in self.SAMPLES:
            path = SCRIPTS_DIR / name
            if not path.exists():
                continue
            with self.subTest(script=name):
                clean = parse_script_file(path)

                annotated_text = _inject_comments(path.read_text(encoding='utf-8'))
                with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.txt', encoding='utf-8', delete=False
                ) as tmp:
                    tmp.write(annotated_text)
                    tmp_path = Path(tmp.name)
                try:
                    annotated = parse_script_file(tmp_path)
                finally:
                    tmp_path.unlink(missing_ok=True)

                clean_bytes = self._encode_all(clean)
                annotated_bytes = self._encode_all(annotated)

                self.assertEqual(len(clean_bytes), len(annotated_bytes))
                for i, (a, b) in enumerate(zip(clean_bytes, annotated_bytes)):
                    self.assertEqual(
                        a, b,
                        f"{name} entry {i}: encoded bytes differ",
                    )


if __name__ == '__main__':
    unittest.main()
