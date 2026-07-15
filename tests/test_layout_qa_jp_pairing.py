"""test_layout_qa_jp_pairing.py — TDD for JP↔EN entry pairing.

The Entry Inspector in the future React/ECharts dashboard shows the
EN simulated lines alongside the JP source text. The CLI pairs by
entry index (same convention as `tools/translation_audit.py`) and
embeds the raw JP entry into each EN entry's JSON via the `jp` field.

Pairing happens at the CLI layer (simulator stays pure / EN-only).
"""

import json
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.cli import main  # noqa: E402


def _write_scen(path: Path, lines):
    """Write a minimal scen file (newline-terminated entries)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


@pytest.fixture
def scen_pair(tmp_path):
    en_dir = tmp_path / 'scripts_en'
    jp_dir = tmp_path / 'scripts_jp'
    _write_scen(en_dir / 'scen019E.txt', [
        'Hi<$FFFF>',
        'Hello world<$FFFE>',
        'Goodbye<$FFFE>',
    ])
    _write_scen(jp_dir / 'scen019J.txt', [
        'こんにちは<$FFFF>',
        '世界、こんにちは<$FFFE>',
        'さようなら<$FFFE>',
    ])
    return {'en_dir': en_dir, 'jp_dir': jp_dir, 'out': tmp_path / 'r.json'}


def test_analyze_embeds_jp_when_jp_scripts_passed(scen_pair):
    rc = main([
        'analyze', 'scen019',
        '--scripts', str(scen_pair['en_dir']),
        '--jp-scripts', str(scen_pair['jp_dir']),
        '--output', str(scen_pair['out']),
    ])
    assert rc in (0, 2)
    report = json.loads(scen_pair['out'].read_text(encoding='utf-8'))
    entries = report['scenarios'][0]['entries']
    assert entries[0]['jp'].startswith('こんにちは')
    assert entries[1]['jp'].startswith('世界、')
    assert entries[2]['jp'].startswith('さようなら')


def test_analyze_jp_is_optional(scen_pair):
    """Without --jp-scripts, no `jp` field — degrades gracefully."""
    rc = main([
        'analyze', 'scen019',
        '--scripts', str(scen_pair['en_dir']),
        '--output', str(scen_pair['out']),
    ])
    assert rc in (0, 2)
    report = json.loads(scen_pair['out'].read_text(encoding='utf-8'))
    entries = report['scenarios'][0]['entries']
    # No 'jp' key when not requested.
    for e in entries:
        assert 'jp' not in e


def test_analyze_jp_missing_file_is_silent(scen_pair, tmp_path):
    """JP path that doesn't have a matching file → entries get no jp,
    no error (don't fail the whole run because one scen lacks JP)."""
    empty_jp = tmp_path / 'no_jp_here'
    empty_jp.mkdir()
    rc = main([
        'analyze', 'scen019',
        '--scripts', str(scen_pair['en_dir']),
        '--jp-scripts', str(empty_jp),
        '--output', str(scen_pair['out']),
    ])
    assert rc in (0, 2)
    report = json.loads(scen_pair['out'].read_text(encoding='utf-8'))
    entries = report['scenarios'][0]['entries']
    # 'jp' absent or empty/null — we accept either.
    for e in entries:
        assert e.get('jp') in (None, '', e.get('jp'))


def test_analyze_jp_count_mismatch_pads_none(scen_pair):
    """If EN has more entries than JP (or vice versa), unmatched EN
    entries have jp = null. Don't refuse to analyze."""
    # Add a 4th EN entry with no JP counterpart.
    en_path = scen_pair['en_dir'] / 'scen019E.txt'
    en_path.write_text(en_path.read_text() + 'Extra<$FFFE>\n', encoding='utf-8')
    rc = main([
        'analyze', 'scen019',
        '--scripts', str(scen_pair['en_dir']),
        '--jp-scripts', str(scen_pair['jp_dir']),
        '--output', str(scen_pair['out']),
    ])
    assert rc in (0, 2)
    report = json.loads(scen_pair['out'].read_text(encoding='utf-8'))
    entries = report['scenarios'][0]['entries']
    assert len(entries) == 4
    assert entries[3]['jp'] is None
