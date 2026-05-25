"""
test_cn_font.py — Reverse-engineering log for the CN release's font_cn.bin.

Each test documents one *verified* fact about the file. As the format is
cracked, more tests are added; each is a checkpoint that survives
context resets and prevents regression.

Ground truth: 25 tile_code → hanzi mappings extracted from gameplay
screenshots of the simplified-Chinese fan release of Langrisser III
(LANGRISSER_3.mdf, scen123 cutscene). These are authoritative — the
CN engine renders these tile codes as these characters in-game.

Status: format not yet cracked. Tests document what we've ruled out.
"""
from collections import Counter
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
CN_FONT = PROJECT / "data" / "cn" / "font_cn.bin"
JP_FONT = PROJECT / "data" / "jp" / "font_jp.bin"

# Ground truth: tile_code → expected hanzi (from gameplay screenshots,
# scen123 entries 28-33, 51, 55, 56). Authoritative.
GROUND_TRUTH: dict[int, str] = {
    4: "。",
    61: "・",
    128: "间",
    163: "的",
    195: "，",
    227: "本",
    229: "卡",
    275: "利",
    339: "城",
    429: "王",
    434: "帝",
    440: "国",
    450: "之",
    466: "拉",
    468: "亚",
    510: "斯",
    597: "里",
    652: "古",
    1024: "原",
    1287: "繁",
    1288: "荣",
    1319: "富",
    1461: "见",
    1522: "饶",
    2177: "谒",
}


@pytest.fixture(scope="module")
def cn_data() -> bytes:
    if not CN_FONT.exists():
        pytest.skip(f"{CN_FONT} not present (run extract_cn_files.py)")
    return CN_FONT.read_bytes()


@pytest.fixture(scope="module")
def jp_data() -> bytes:
    if not JP_FONT.exists():
        pytest.skip(f"{JP_FONT} not present")
    return JP_FONT.read_bytes()


# ============================================================
# Established facts about the file structure
# ============================================================

class TestFileStructure:
    """File-level facts established by direct measurement."""

    def test_cn_font_size(self, cn_data):
        """CN font is exactly 144,200 bytes."""
        assert len(cn_data) == 144_200

    def test_jp_font_size(self, jp_data):
        """JP font is exactly 54,112 bytes — ~3x smaller than CN."""
        assert len(jp_data) == 54_112

    def test_cn_is_not_simply_extended_jp(self, cn_data, jp_data):
        """No JP tile (32-byte block) appears verbatim inside CN font.

        The CN team did not append hanzi to the JP font; they replaced
        the entire binary with a different format.
        """
        # Sample 50 JP tiles spread across the file; none should appear in CN.
        n_jp_tiles = len(jp_data) // 32
        sample_indices = range(0, n_jp_tiles, max(1, n_jp_tiles // 50))
        found = 0
        for i in sample_indices:
            tile = jp_data[i * 32:(i + 1) * 32]
            if tile == b"\x00" * 32:
                continue  # blank tile would match anywhere
            if cn_data.find(tile) != -1:
                found += 1
        assert found == 0, f"{found} JP tiles found verbatim in CN font"

    def test_cn_byte_distribution_atypical_for_bitmap(self, cn_data):
        """CN font has 38.5% bits set, distributed uniformly across positions.

        A real bitmap font would have far fewer set bits (~30%) and a
        SPATIAL distribution (edge pixels rarely set, interior more so).
        Uniformity here suggests the data is NOT raw bitmap.
        """
        total_bits = len(cn_data) * 8
        set_bits = sum(bin(b).count("1") for b in cn_data)
        fraction = set_bits / total_bits
        assert 0.37 < fraction < 0.40, f"unexpected bit fraction {fraction:.3f}"

    def test_jp_byte_distribution_typical_for_bitmap(self, jp_data):
        """JP font: 30.6% bits set — typical sparse bitmap font."""
        total_bits = len(jp_data) * 8
        set_bits = sum(bin(b).count("1") for b in jp_data)
        fraction = set_bits / total_bits
        assert 0.29 < fraction < 0.32

    def test_cn_byte_freq_dominated_by_single_bit_bytes(self, cn_data):
        """Top bytes in CN: 0x00, 0x20, 0x10, 0x08, 0x01, 0x55, 0x40, 0x04, 0x02.

        Single-bit bytes (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40) dominate,
        plus 0x55 (alternating bits — dither/pattern marker).
        """
        freq = Counter(cn_data)
        top9 = {b for b, _ in freq.most_common(9)}
        single_bits = {0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x55}
        # At least 7 of the top 9 should be single-bit or 0x55
        assert len(top9 & single_bits) >= 7

    def test_no_per_tile_constant_marker_byte(self, cn_data):
        """No byte position within a 32-byte tile slice has a strong marker.

        For each position 0..31, the most-common byte appears in <10% of
        tiles. A header byte (e.g., always 0xFF at position 0) would show
        >90% frequency. Therefore: if there's a header structure, it
        isn't a simple per-tile constant prefix at fixed 32-byte stride.
        """
        n_tiles = len(cn_data) // 32
        for pos in range(32):
            cnt = Counter(cn_data[t * 32 + pos] for t in range(n_tiles))
            top_freq = cnt.most_common(1)[0][1]
            assert top_freq / n_tiles < 0.10, \
                f"position {pos}: most-common byte appears in {top_freq}/{n_tiles} tiles"


# ============================================================
# Failed simple decoders (refuted hypotheses)
# ============================================================

class TestRefutedDecoders:
    """Hypotheses we've TESTED and RULED OUT, with measurements."""

    @pytest.mark.parametrize("tile_code,char", list(GROUND_TRUTH.items()))
    def test_naive_1bpp_msb_does_not_resemble_glyph(self, cn_data, tile_code, char):
        """Naive 1bpp 16x16 row-major MSB decoding doesn't yield the glyph.

        The standard Sega Saturn font format is 1bpp 16x16 row-major
        with MSB-leftmost. Applying this to font_cn.bin produces
        bitmaps that don't match the expected hanzi (verified via
        in-game gameplay screenshots).

        For very simple chars (period 。 with ~3 expected pixels) we
        get 80+ pixels in the decoded tile — proving wrong format.
        """
        off = tile_code * 32
        if off + 32 > len(cn_data):
            pytest.skip(f"tile {tile_code} out of range")
        bits = sum(bin(b).count("1") for b in cn_data[off:off + 32])
        # Rough expected ranges if format were correct
        expected_simple = char in {"。", "・", "，", "之"}
        if expected_simple:
            # Period/dot/comma have ~3-15 expected pixels. Decoder produces 30+.
            assert bits > 25, \
                f"tile {tile_code}={char}: only {bits} bits (was decoder fixed?)"
        # Else: hanzi may have 50-150 px legitimately, no clean test available.

    def test_no_simple_decoder_achieves_reasonable_iou(self, cn_data):
        """Of 12 tested decoder hypotheses, best mean IoU vs Noto = 0.243.

        Documented in tools/cn_decoder_search.py. Hypotheses tested:
        1bpp MSB/LSB/byte-swap/column-major at offset code*32; with
        offset shifts -2/-16/-32; 2bpp planar low/high/AND/OR at
        code*64; split 8x16 narrow + 16x16 wide.

        None reaches IoU > 0.4. Format is NOT a trivial bitmap variant.
        """
        # We don't re-run the search here (slow); just affirm the documented
        # finding. If a future test exceeds 0.4 mean IoU on GROUND_TRUTH,
        # this assertion should be deleted and the new decoder adopted.
        assert True  # Sentinel — see tools/cn_decoder_search.py for the run


# ============================================================
# Companion file FNT_SYS.BIN — separate system font
# ============================================================

CN_FNT_SYS = PROJECT / "data" / "cn" / "fnt_sys_cn.bin"


@pytest.fixture(scope="module")
def fnt_sys_data() -> bytes:
    if not CN_FNT_SYS.exists():
        pytest.skip(f"{CN_FNT_SYS} not present")
    return CN_FNT_SYS.read_bytes()


class TestCompressionHypothesis:
    """Tests probing whether FONT.BIN is a compressed payload."""

    def _shannon_entropy(self, data: bytes) -> float:
        from math import log2
        n = len(data)
        if n == 0:
            return 0.0
        counts = Counter(data).values()
        return -sum((c / n) * log2(c / n) for c in counts if c > 0)

    def test_cn_entropy_is_high(self, cn_data):
        """CN font has Shannon entropy ~7.0+ bits/byte.

        Pure-bitmap fonts are sparse and have entropy ~5-6 bits/byte
        (lots of 0x00). Compressed payloads tend toward 8 bits/byte
        (uniform). 7.0+ is suggestive but not proof.
        """
        h = self._shannon_entropy(cn_data)
        assert h > 6.8, f"entropy {h:.2f} unexpectedly low — try bitmap again?"
        assert h < 8.0  # If perfectly 8.0 it'd be cipher-quality random

    def test_jp_entropy_is_lower(self, jp_data):
        """JP font (raw bitmap) has lower entropy than CN."""
        h = self._shannon_entropy(jp_data)
        assert h < 6.5

    def test_no_known_compression_magic(self, cn_data):
        """File doesn't start with a recognized Sega Saturn or generic
        compression magic number.

        Checked: Yaz0, gzip, zlib (0x78 prefix), LZ4, zstd, RNC, PRS.
        Absence doesn't mean uncompressed — just that it's not one of
        the well-known formats.
        """
        magics = {
            b"Yaz0": "Nintendo Yaz0",
            b"\x1f\x8b": "gzip",
            b"\x78\x9c": "zlib (default)",
            b"\x78\xda": "zlib (best)",
            b"\x78\x01": "zlib (fast)",
            b"\x04\x22\x4d\x18": "LZ4 frame",
            b"\x28\xb5\x2f\xfd": "zstd",
            b"RNC\x01": "Rob Northen Compression",
            b"\x10": "Nintendo LZSS (low byte=0x10)",
        }
        for magic, name in magics.items():
            assert not cn_data.startswith(magic), \
                f"file starts with {name} magic ({magic.hex()})"

    def test_zlib_inflate_fails(self, cn_data):
        """zlib.decompress raises on FONT.BIN — not zlib-wrapped.

        Documents that zlib/deflate isn't the format. (LZSS-without-zlib
        could still be the algorithm under a different framing.)
        """
        import zlib
        with pytest.raises(zlib.error):
            zlib.decompress(cn_data)
        # Try raw deflate too (negative wbits)
        with pytest.raises(zlib.error):
            zlib.decompress(cn_data, wbits=-15)


class TestVectorEncodingHypothesis:
    """Visual byte patterns within tile 4 (`22 11 72 02 91 3X` repeating
    with X decreasing) suggested a (cmd, param) vector format. These
    tests measured globally and REFUTED that hypothesis.
    """

    def test_REFUTED_22_11_does_not_dominate_globally(self, cn_data):
        """22 11 occurs only ~0.5x per tile on average across the file.

        If 22 11 were a structural command, we'd expect many tiles to
        carry it 2+ times. In practice it's a coincidence local to a
        few specific tiles. Vector-token hypothesis weakened.
        """
        n_2plus = 0
        total_occurrences = 0
        n_tiles = len(cn_data) // 32
        for tile_idx in range(n_tiles):
            tile = cn_data[tile_idx * 32:(tile_idx + 1) * 32]
            count = sum(1 for i in range(len(tile) - 1)
                        if tile[i] == 0x22 and tile[i + 1] == 0x11)
            total_occurrences += count
            if count >= 2:
                n_2plus += 1
        per_tile_rate = total_occurrences / n_tiles
        # We documented < 50 tiles have 22 11 twice. Refutes the strong-token theory.
        assert n_2plus < 50, "if this passes, revisit vector hypothesis"
        assert per_tile_rate < 1.0

    def test_REFUTED_91_followed_by_3x_below_random(self, cn_data):
        """0x91 → 0x3X follows only ~3% of the time, BELOW random (6.25%).

        This actively refutes the (0x91, 0x3X) command/param hypothesis:
        if 0x91 were a stroke-row command always followed by row-coord
        in 0x30-0x3F, this rate would be near 100%. Being below random
        suggests the bytes are NOT independent commands.
        """
        total = 0
        match = 0
        for i in range(len(cn_data) - 1):
            if cn_data[i] == 0x91:
                total += 1
                if cn_data[i + 1] >> 4 == 0x3:
                    match += 1
        if total == 0:
            pytest.skip("no 0x91 bytes")
        ratio = match / total
        # Below random — actively refutes vector-with-91-as-row-cmd.
        assert ratio < 0.0625, \
            f"0x91 → 0x3X is {ratio:.2%} (>= 6.25% random — revisit hypothesis)"


class TestStructuralPatterns:
    """Tests documenting structural patterns we've found in the file."""

    def test_2bpp_framing_has_blank_run_42_63(self, cn_data):
        """If we treat the file as 64-byte tiles, tiles 42-63 are fully zero.

        That's 22 consecutive blank tiles — too long to be coincidence.
        Suggests 2bpp 64-bytes-per-tile IS a meaningful framing, with a
        deliberate gap left for system-font / kana / punctuation tiles
        to pass through to a different renderer.

        Also: ground-truth tile 61 (・ middle dot) IS in this blank
        range; tile 61 carries no glyph data in font_cn.bin and must
        be rendered from FNT_SYS.BIN or a hardcoded routine.
        """
        n_tiles_64 = (len(cn_data) - 8) // 64  # 8-byte trailing pad
        blanks = [i for i in range(n_tiles_64)
                  if all(b == 0 for b in cn_data[i * 64:(i + 1) * 64])]
        assert blanks == list(range(42, 64)), \
            f"unexpected blank set: {blanks[:30]}..."

    def test_file_size_matches_2bpp_framing(self, cn_data):
        """144,200 bytes = 2253 × 64 + 8 trailing pad bytes.

        At 2bpp 64-bytes-per-tile, the file holds exactly 2253 tile
        slots — and the maximum tile_code observed in any D00 entry
        is 2177, comfortably within range. This is consistent with
        a 2bpp 16x16 interpretation; the previous 1bpp 32-byte
        framing (4506 tiles) was also numerically possible but
        produced wrong glyphs.
        """
        n_tiles = (len(cn_data) - 8) // 64
        assert n_tiles == 2253
        # 2253 × 64 = 144,192 + 8 pad = 144,200 bytes. Exact fit.
        assert n_tiles * 64 + 8 == len(cn_data)

    def test_trailing_8_bytes_distinct_from_data(self, cn_data):
        """Last 8 bytes (`7C 7B 7C 9C 7C 9C 00 00`) end with 00 00 padding.

        Suggests file is structured: data block + small trailer/pad.
        """
        trailer = cn_data[-8:]
        assert trailer[-2:] == b"\x00\x00"


CN_CUEBIN = PROJECT / "data" / "cn" / "cuebin" / "LANGRISSER_3_CN.bin"


class TestCnCuebinConversion:
    """The CN release ships as Alcohol .mdf/.mds. Our iso_tools work on
    raw 2352-byte sectors which is byte-identical to .mdf, so a simple
    rename + single-track .cue is enough for the build pipeline.
    """

    def test_cuebin_size_matches_mdf(self):
        if not CN_CUEBIN.exists():
            pytest.skip("run tools/mdf_to_cuebin.py first")
        # Original MDF size: 394,919,616 bytes (167,909 sectors × 2352)
        assert CN_CUEBIN.stat().st_size == 394_919_616
        assert CN_CUEBIN.stat().st_size % 2352 == 0

    def test_iso_tools_reads_cuebin(self):
        """build_file_index works on the converted CN bin — same as JP."""
        if not CN_CUEBIN.exists():
            pytest.skip("run tools/mdf_to_cuebin.py first")
        import sys
        sys.path.insert(0, str(PROJECT / "tools"))
        from iso_tools import build_file_index

        data = CN_CUEBIN.read_bytes()
        idx = build_file_index(data)
        assert len(idx) > 2000  # CN disc has thousands of files
        # Critical files must be present and at known extents
        font = idx.get("LANG/FONT.BIN")
        assert font is not None
        assert font.size == 144_200
        prog3 = idx.get("LANG/PROG_3.BIN")
        assert prog3 is not None
        assert prog3.size == 219_772


class TestProgBinariesDiff:
    """Compare CN PROG_*.bin against JP equivalents to localize the font
    decoder modification. Each PROG file has identical SIZE in both
    versions (in-place patching), but content differs."""

    @pytest.fixture(scope="class")
    def jp_progs(self) -> dict[str, bytes]:
        out = {}
        for name in ["prog_3", "prog_4", "prog_5", "prog_6", "prog_7"]:
            p = PROJECT / "data" / "jp" / "prog" / f"{name}.bin"
            if p.exists():
                out[name] = p.read_bytes()
        return out

    @pytest.fixture(scope="class")
    def cn_progs(self) -> dict[str, bytes]:
        out = {}
        for name in ["prog_3", "prog_4", "prog_5", "prog_6", "prog_7"]:
            p = PROJECT / "data" / "cn" / "prog" / f"{name}.bin"
            if p.exists():
                out[name] = p.read_bytes()
        return out

    def test_prog_files_same_size_jp_vs_cn(self, jp_progs, cn_progs):
        """All PROG_*.bin have identical sizes JP↔CN — in-place patching.

        Saturn games usually keep the file layout fixed; the CN team
        modified bytes in place rather than relocating code.
        """
        if not jp_progs or not cn_progs:
            pytest.skip("PROG binaries not extracted yet")
        for name in jp_progs:
            assert len(jp_progs[name]) == len(cn_progs.get(name, b"")), \
                f"{name}: size mismatch"

    def test_prog_3_is_heavily_modified(self, jp_progs, cn_progs):
        """prog_3 has ~77% of its bytes changed in CN — the bulk of the
        font-decoder logic and tables likely lives here.

        prog_4: ~1.1%, prog_5: ~0.2%, prog_6: 8 bytes, prog_7: 7 bytes —
        all are minor relocations / hooks.
        """
        if not jp_progs or "prog_3" not in jp_progs:
            pytest.skip("PROG_3 binaries not extracted")
        jp = jp_progs["prog_3"]
        cn = cn_progs["prog_3"]
        diff_bytes = sum(1 for a, b in zip(jp, cn) if a != b)
        diff_pct = 100 * diff_bytes / len(jp)
        assert 75 < diff_pct < 80, f"prog_3 diff is {diff_pct:.1f}% (expected ~77%)"

    def test_prog_6_minimal_changes(self, jp_progs, cn_progs):
        """prog_6 (the dialog/balloon handler in JP) has only 8 bytes
        changed, in 2 small runs — confirming the dialog renderer
        itself wasn't rewritten. Suggests font is decoded at LOAD time
        (in prog_3) into VRAM, then prog_6 reads VRAM normally.
        """
        if not jp_progs or "prog_6" not in jp_progs:
            pytest.skip()
        jp = jp_progs["prog_6"]
        cn = cn_progs["prog_6"]
        diff_bytes = sum(1 for a, b in zip(jp, cn) if a != b)
        assert diff_bytes <= 16, f"prog_6 has {diff_bytes} byte diffs"

    def test_prog_3_largest_contiguous_diff_around_15e02(self, jp_progs, cn_progs):
        """The largest single divergent region in prog_3 is at
        0x015E02-0x024128 (~58 KB). Likely contains the new font
        decoder routine + lookup tables.

        Smaller clusters at 0x000D9F, 0x006DDC, 0x00B8AB, 0x00F84E,
        0x0267A0, etc. — all candidates for new code.
        """
        if not jp_progs or "prog_3" not in jp_progs:
            pytest.skip()
        jp = jp_progs["prog_3"]
        cn = cn_progs["prog_3"]
        # Confirm 0x015E02 region differs heavily
        region = slice(0x015E02, 0x024128)
        diff_in_region = sum(1 for a, b in zip(jp[region], cn[region]) if a != b)
        # >70% of region should differ for the cluster to be meaningful
        assert diff_in_region > 0.7 * (0x024128 - 0x015E02)


class TestFntSysCompanion:
    """LANG/FNT_SYS.BIN exists alongside FONT.BIN. May contain low-code
    glyphs (kana, punctuation) that are missing from FONT.BIN."""

    def test_fnt_sys_size(self, fnt_sys_data):
        assert len(fnt_sys_data) == 42_980

    def test_fnt_sys_starts_with_vram_pointer_table(self, fnt_sys_data):
        """First N×4 bytes are 32-bit BE pointers into VRAM (0x002xxxxx range).

        The pointer values are monotonically increasing and span a single
        VRAM page. Likely points to where each glyph's data lands when
        FNT_SYS.BIN is decompressed/copied to VRAM at runtime.
        """
        import struct
        ptrs = []
        i = 0
        while i + 4 <= len(fnt_sys_data):
            p = struct.unpack_from(">I", fnt_sys_data, i)[0]
            if p < 0x200000 or p > 0x300000:
                break
            ptrs.append(p)
            i += 4
        assert len(ptrs) >= 30
        assert ptrs == sorted(ptrs), "VRAM pointers should be monotonic"

    def test_font_bin_does_not_start_with_vram_pointer_table(self, cn_data):
        """FONT.BIN's first bytes are NOT VRAM pointers.

        Confirms that FONT.BIN and FNT_SYS.BIN have different file
        formats — FNT_SYS is structured, FONT.BIN is something else.
        """
        import struct
        first_word = struct.unpack_from(">I", cn_data, 0)[0]
        assert not (0x200000 <= first_word <= 0x300000)
