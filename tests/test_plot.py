"""test_plot.py — round-trip and structure tests for LANG/PLOT.DAT.

Locks in the format facts established in 2026-05-01 (Langrisser III
patch v0.5+):
- 35 blocks, BE32 file_size header + 35 × BE16 offsets, then bodies.
- Each block opens with `0xFFF8 BLOCK_ID`, ends with `0xFFFE`.
- Same tile encoding as D00.DAT (bigram + char fallback).

If `cache/plot_jp.dat` is present (produced by `build.py`), this also
verifies that the EN compilation of `scripts/en/plotE.txt` is byte-
parseable and contains 35 blocks.
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from plot_tools import (
    N_BLOCKS, HEADER_SIZE, parse_plot, build_plot,
    parse_plot_script, encode_plot_script, round_trip_test,
)

CN_PLOT = PROJECT / "data" / "cn" / "plot_cn.dat"
JP_PLOT = PROJECT / "cache" / "plot_jp.dat"
PLOT_SCRIPT = PROJECT / "scripts" / "en" / "plotE.txt"


@pytest.mark.skipif(not CN_PLOT.exists(),
                    reason="CN PLOT.DAT not extracted")
def test_cn_round_trip():
    """parse(data) → build(parsed) === data, byte-identical."""
    round_trip_test(CN_PLOT.read_bytes())


@pytest.mark.skipif(not JP_PLOT.exists(),
                    reason="JP PLOT.DAT not in build/ — run build.py first")
def test_jp_round_trip():
    round_trip_test(JP_PLOT.read_bytes())


@pytest.mark.skipif(not CN_PLOT.exists(), reason="CN PLOT.DAT missing")
def test_cn_block_count():
    blocks = parse_plot(CN_PLOT.read_bytes())
    assert len(blocks) == N_BLOCKS == 35


@pytest.mark.skipif(not CN_PLOT.exists(), reason="CN PLOT.DAT missing")
def test_cn_block_ids_sequential():
    """Block IDs run 1..35 in order (engine reads them by index)."""
    blocks = parse_plot(CN_PLOT.read_bytes())
    assert [b.block_id for b in blocks] == list(range(1, 36))


@pytest.mark.skipif(not CN_PLOT.exists(), reason="CN PLOT.DAT missing")
def test_cn_blocks_terminate_correctly():
    """Blocks 1..34 end with FFFE; block 35 ends with FFFE FFFF (file-end)."""
    blocks = parse_plot(CN_PLOT.read_bytes())
    for i, b in enumerate(blocks[:-1]):
        assert b.raw_bytes[-2:] == b"\xff\xfe", \
            f"block {i+1} doesn't end with FFFE (got {b.raw_bytes[-4:].hex()})"
    # Last block: FFFE FFFF
    assert blocks[-1].raw_bytes[-4:] == b"\xff\xfe\xff\xff", \
        f"block 35 must end with FFFE FFFF (got {blocks[-1].raw_bytes[-4:].hex()})"


@pytest.mark.skipif(not CN_PLOT.exists(), reason="CN PLOT.DAT missing")
def test_cn_file_header_size_matches():
    data = CN_PLOT.read_bytes()
    declared = struct.unpack(">I", data[:4])[0]
    assert declared == len(data)


@pytest.mark.skipif(not PLOT_SCRIPT.exists(), reason="plotE.txt missing")
def test_plot_script_has_35_blocks():
    blocks = parse_plot_script(PLOT_SCRIPT)
    assert len(blocks) == N_BLOCKS


@pytest.mark.skipif(not PLOT_SCRIPT.exists(), reason="plotE.txt missing")
def test_plot_script_blocks_in_order():
    """plotE.txt block N opens with `<$FFF8000N>` (1-indexed)."""
    blocks = parse_plot_script(PLOT_SCRIPT)
    for i, blk in enumerate(blocks, start=1):
        marker = f"<$FFF8{i:04X}>"
        assert blk.startswith(marker), \
            f"block {i}: expected to start with {marker}, got {blk[:20]!r}"


@pytest.mark.skipif(not PLOT_SCRIPT.exists(), reason="plotE.txt missing")
def test_en_compile_parses_back():
    """Compiled EN PLOT.DAT must be parseable into 35 blocks ending with FFFE."""
    from font_tools import build_char_tile_map, build_bigram_tile_map
    char_map = build_char_tile_map()
    bigram_map = build_bigram_tile_map()
    out = encode_plot_script(PLOT_SCRIPT, char_map, bigram_map)
    blocks = parse_plot(out)
    assert len(blocks) == N_BLOCKS
    for i, b in enumerate(blocks):
        assert b.raw_bytes[:2] == b"\xff\xf8"
        if i == N_BLOCKS - 1:
            assert b.raw_bytes[-4:] == b"\xff\xfe\xff\xff"
        else:
            assert b.raw_bytes[-2:] == b"\xff\xfe"
    # Round-trip: parsed → rebuilt should match
    round_trip_test(out)
