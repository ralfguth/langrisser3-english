#!/usr/bin/env python3
"""fnt_sys_tools.py — decoder + encoder for LANG/FNT_SYS.BIN.

LANG/FNT_SYS.BIN is NOT a font file. It is 31 sections of menu/UI strings
encoded as BE16 tile codes against LANG/FONT.BIN — same family as D00.DAT
and PLOT.DAT. See archive/docs/20260503_fnt_sys_format.md.

Layout (JP, 56,804 bytes):

    +----------+-----------------------------------------------+
    | 0x000    | 31 × BE32 work-RAM pointers, monotonic        |
    | 0x07C    | section 0  (offset table, BE16 word offsets)  |
    |          | section 1  (data records, FFFF-terminated)    |
    |          | section 2  (offset table)                     |
    |          | section 3  (data records)                     |
    |          | ... 13 more (offset, data) pairs ...          |
    |          | section 28 (336B LOOKUP table — preserve)     |
    |          | section 29 (offset table)                     |
    |          | section 30 (data records — final pair)        |
    +----------+-----------------------------------------------+

Section pointers are work-RAM addresses starting at 0x246000 + 0x7C. The
delta between consecutive pointers gives each section's length in bytes.
Engine copies each section into RAM at its declared address; PROG_*.BIN
code reads them as plain BE16 streams.

Each of the 15 paired (offset_table, data_table) groups encodes a
variable-length string array:
  - offset_table: N × BE16, word-offsets into the paired data_table
  - data_table:   N FFFF-terminated records; sometimes a trailing 0x0000
                  pad after the last terminator. The encoder preserves
                  whatever trailer JP had.

Section 28 is opaque 336B (168 BE16 entries) — a class/category lookup,
non-textual. Always preserved byte-for-byte.

This module supplies:
  - parse_fnt_sys(data)  → FntSys
  - build_fnt_sys(fs)    → bytes (round-trip identical for unedited input)
  - load_fnt_sys_from_iso(iso_image_path)  helper
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POINTER_COUNT = 31
HEADER_BYTES = POINTER_COUNT * 4  # 124
SECTION_BASE_OFFSET = HEADER_BYTES  # 0x7C
WRAM_BASE = 0x246000

# Indices of the 15 (offset_section, data_section) pairs. Section 28 is the
# opaque lookup table and is skipped; the final pair jumps over it.
PAIR_INDICES: list[tuple[int, int]] = [
    (0, 1), (2, 3), (4, 5), (6, 7), (8, 9),
    (10, 11), (12, 13), (14, 15), (16, 17), (18, 19),
    (20, 21), (22, 23), (24, 25), (26, 27), (29, 30),
]
LOOKUP_SECTION_INDEX = 28
LOOKUP_SECTION_BYTES = 336

# ALL fntsys text is encoded with the half-width BIGRAM tile map. Half-width is
# the default; full-width is NOT a separate code path — it falls out of the maps
# by character case. Standalone full-width-Latin labels (START / LOAD / SAVE /
# SCENARIO / TURN / HP / MP) are all-caps, and all-caps letters have no bigram,
# so they fall back to the zenkaku standalone tiles 17-42 → they stay full-width
# automatically, byte-identical to single-char encoding (verified). Mixed-case
# prose and names bigram to half-width. So the only thing rendered full-width is
# exactly "what is full-width Latin in the JP" (per feedback_ui_zenkaku_latin_rule),
# with no per-section flag needed. Prose is always bigram.
#
# Kept as the full set for clarity / future opt-out; encode_fntsys bigrams every
# pair regardless. NOTE: that the description boxes render bigram tiles correctly
# is unverified — playtest is authority.
BIGRAM_PAIRS: set[int] = set(range(15))

# JP record count per pair index (0..14), per archive/docs format doc.
EXPECTED_JP_RECORD_COUNTS = [
    242, 40, 31, 237, 169, 22, 31, 57, 19, 177, 381, 349, 701, 21, 41,
]

JP_FILE_SIZE = 56_804


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Pair:
    """One (offset_table, data_table) string array.

    ``records`` and ``data_trailer`` are derived by ``parse_fnt_sys``.
    ``offset_table_raw`` and ``data_section_raw`` preserve the original
    section bytes so unedited Pairs round-trip byte-identical even when the
    underlying binary has count corruption (e.g. 0.2 patch-EN's pair 3 / 4 / 6 /
    10 declare more records than FFFF terminators present).

    When the caller mutates ``records`` (e.g. translation editing), set
    ``edited=True`` so ``build_fnt_sys`` regenerates the offset table and
    data section from scratch instead of reusing the raw bytes.
    """
    pair_index: int                     # 0..14
    records: list[bytes]                # each ends with b'\xff\xff'
    data_trailer: bytes = b""           # bytes after the last decoded FFFF
    offset_table_raw: bytes = b""       # original offset table section bytes
    data_section_raw: bytes = b""       # original data section bytes
    edited: bool = False                # True ⇒ regenerate from records on build

    @property
    def record_count(self) -> int:
        return len(self.records)


@dataclass
class FntSys:
    """Structured FNT_SYS.BIN."""
    pointers: list[int]                 # 31 BE32 work-RAM pointers (from JP/baseline; recomputed by build)
    pairs: list[Pair]                   # 15 string-table pairs
    lookup: bytes                       # section 28 raw bytes
    raw_sections: list[bytes] = field(default_factory=list)  # all 31, for reference / debug

    @property
    def size(self) -> int:
        return SECTION_BASE_OFFSET + sum(len(s) for s in self.raw_sections)


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def _section_bounds(data: bytes) -> list[tuple[int, int]]:
    """Return [(file_offset, length)] for each of the 31 sections."""
    pointers = list(struct.unpack(">31I", data[:HEADER_BYTES]))
    bounds = []
    base = SECTION_BASE_OFFSET
    for i, ptr in enumerate(pointers):
        next_ptr = pointers[i + 1] if i + 1 < POINTER_COUNT else None
        if next_ptr is None:
            length = len(data) - base
        else:
            length = next_ptr - ptr
        if length < 0:
            raise ValueError(f"section {i}: negative length {length} "
                             f"(non-monotonic pointer table)")
        bounds.append((base, length))
        base += length
    return bounds


def _split_records(section_bytes: bytes, count: int) -> tuple[list[bytes], bytes]:
    """Take up to ``count`` FFFF-terminated records; return (records, trailer).

    Cannot key off 0x0000 to detect end-of-table because that word is a valid
    in-record tile (full-width space). Record count comes from the paired
    offset table size — for healthy data (JP) it's exact; for corrupted data
    (0.2 patch-EN per archive/docs/20260503_fnt_sys_format.md "Why 0.2 patch's was wrong")
    fewer FFFF terminators may exist than the offset table claims. We capture
    whatever records exist and bundle any leftover bytes into ``trailer`` so
    the original bytes round-trip exactly. ``validate(fs)`` flags the mismatch.
    """
    records: list[bytes] = []
    cur = bytearray()
    i = 0
    n = len(section_bytes)
    while i < n - 1 and len(records) < count:
        word = struct.unpack_from(">H", section_bytes, i)[0]
        i += 2
        cur.extend(struct.pack(">H", word))
        if word == 0xFFFF:
            records.append(bytes(cur))
            cur = bytearray()
    # Whatever is left (partial last record + post-last-FFFF padding) becomes trailer.
    trailer = bytes(cur) + section_bytes[i:]
    return records, trailer


def parse_fnt_sys(data: bytes) -> FntSys:
    """Parse FNT_SYS.BIN bytes into a structured FntSys."""
    if len(data) < HEADER_BYTES:
        raise ValueError(f"file too small ({len(data)} bytes) for header")

    pointers = list(struct.unpack(">31I", data[:HEADER_BYTES]))
    bounds = _section_bounds(data)
    raw_sections = [data[off:off + length] for off, length in bounds]

    # Sanity: section 28 is the lookup table.
    lookup = raw_sections[LOOKUP_SECTION_INDEX]
    if len(lookup) != LOOKUP_SECTION_BYTES:
        raise ValueError(f"section 28 (lookup) is {len(lookup)} bytes, "
                         f"expected {LOOKUP_SECTION_BYTES}")

    pairs: list[Pair] = []
    for pair_idx, (off_sec_idx, data_sec_idx) in enumerate(PAIR_INDICES):
        offset_table = raw_sections[off_sec_idx]
        data_section = raw_sections[data_sec_idx]
        record_count = len(offset_table) // 2
        records, trailer = _split_records(data_section, record_count)
        pairs.append(Pair(
            pair_index=pair_idx,
            records=records,
            data_trailer=trailer,
            offset_table_raw=offset_table,
            data_section_raw=data_section,
        ))

    return FntSys(pointers=pointers, pairs=pairs, lookup=lookup,
                  raw_sections=raw_sections)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _pair_to_sections(pair: Pair) -> tuple[bytes, bytes]:
    """Return (offset_table_bytes, data_section_bytes) for a Pair.

    Offsets are in BE16 word units relative to the start of the data section.
    """
    offsets: list[int] = []
    word_pos = 0  # word position in data section
    data = bytearray()
    for rec in pair.records:
        if len(rec) % 2 != 0:
            raise ValueError(f"pair {pair.pair_index}: record length "
                             f"{len(rec)} is not word-aligned")
        if not rec.endswith(b"\xff\xff"):
            raise ValueError(f"pair {pair.pair_index}: record missing "
                             f"FFFF terminator")
        offsets.append(word_pos)
        data.extend(rec)
        word_pos += len(rec) // 2
    data.extend(pair.data_trailer)
    offset_table = b"".join(struct.pack(">H", o) for o in offsets)
    return offset_table, bytes(data)


def build_fnt_sys(fs: FntSys) -> bytes:
    """Reconstruct FNT_SYS.BIN bytes from a FntSys structure.

    Round-trip: ``build_fnt_sys(parse_fnt_sys(jp)) == jp`` for the
    untouched JP binary. The pointer table is recomputed from section
    lengths; section 28 is copied byte-for-byte from ``fs.lookup``.
    """
    # Compose each of the 31 sections.
    sections: list[bytes] = [b""] * POINTER_COUNT

    for pair in fs.pairs:
        off_idx, data_idx = PAIR_INDICES[pair.pair_index]
        if pair.edited or not pair.data_section_raw:
            off_bytes, data_bytes = _pair_to_sections(pair)
        else:
            # Unedited: reuse raw bytes for true byte-identical round-trip
            # (handles 0.2 patch-EN's count corruption losslessly).
            off_bytes = pair.offset_table_raw
            data_bytes = pair.data_section_raw
        sections[off_idx] = off_bytes
        sections[data_idx] = data_bytes

    sections[LOOKUP_SECTION_INDEX] = fs.lookup

    # Sanity: every section must be set (no holes).
    for i, s in enumerate(sections):
        if s is None:
            raise ValueError(f"section {i} not populated by any pair")

    # Recompute the BE32 pointer table from section lengths.
    # First pointer = WRAM_BASE + SECTION_BASE_OFFSET; each subsequent =
    # previous + previous_section_length.
    pointers = []
    addr = WRAM_BASE + SECTION_BASE_OFFSET
    for s in sections:
        pointers.append(addr)
        addr += len(s)

    header = b"".join(struct.pack(">I", p) for p in pointers)
    return header + b"".join(sections)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def load_fnt_sys_from_iso(iso_track_path: Path) -> bytes:
    """Extract LANG/FNT_SYS.BIN from a Saturn Track 01 image."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from iso_tools import build_file_index, extract_file_data
    image = Path(iso_track_path).read_bytes()
    idx = build_file_index(image)
    entry = idx.get("LANG/FNT_SYS.BIN")
    if not entry:
        raise RuntimeError("LANG/FNT_SYS.BIN not found in ISO")
    return extract_file_data(image, entry.extent, entry.size)


# ---------------------------------------------------------------------------
# Script → binary encoder (Phase 2+)
# ---------------------------------------------------------------------------

def _build_fntsys_char_map() -> dict[str, int]:
    """Char→tile map for fntsys encoding == the project's EN font map.

    FNT_SYS strings render through the SAME custom font (FONT.BIN) as the
    scenario (D00) and chapter-recap (PLOT) text — the glyphs are shared
    across the whole project. So fntsys must encode with the SAME map the
    scen/plot pipelines use: font_tools.CHAR_TILE_MAP (paired with
    BIGRAM_TILE_MAP). There is no JP font in the build, so layering the JP
    decoder's tile_map.json here is wrong: it points chars at JP slots that
    generate_english_font has repainted with different glyphs.

    Concrete failure that caused (now guarded by tests/test_fntsys_char_map.py):
    JP put 'r' at tile 67, but the EN font paints tile 67 as the ('a','u')
    bigram, so a word-final standalone 'r' ("Commander", "Soldier") rendered
    as "au" ("Commandeau", "Soldieau"). CHAR_TILE_MAP maps each standalone
    lowercase letter to its own (letter, ' ') half-width tile, which the font
    draws correctly — identical to how scen encodes.

    Kept as a thin wrapper (rather than importing the map directly at
    every call site) so the build_fntsys* helpers share one accessor.

    2026-06-11: FNT_SYS uses the per-surface FNTSYS maps — same glyphs,
    plus the digit pairs / fragment reuse and the half-width digit
    fallback that dialogue must NOT get (numbers in prose keep the
    centered zenkaku-style digits). See font_tools.build_fntsys_maps.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from font_tools import FNTSYS_CHAR_TILE_MAP
    return dict(FNTSYS_CHAR_TILE_MAP)


def _parse_script_records(script_path: Path) -> list[str]:
    """Read fntsys{N}E.txt and return one entry per line (newline-stripped).

    Each line is expected to end with `<$FFFF>`. Blank lines are skipped.
    """
    out: list[str] = []
    for line in script_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.append(line)
    return out


def encode_fntsys(jp_baseline: bytes, scripts_dir: Path,
                  script_pattern: str = "fntsys{n}E.txt",
                  bigram_override: dict = None) -> bytes:
    """Build a complete FNT_SYS.BIN from scripts/en/fntsys{1..15}E.txt.

    Steps:
      1. parse_fnt_sys(jp_baseline) → 15 pairs + lookup section
      2. For each script file present, encode each line into a record
         (FFFF terminator embedded via the `<$FFFF>` escape) and swap
         into the corresponding pair, marking it as edited so build_fnt_sys
         regenerates the offset table.
      3. Pairs without a script file keep their JP raw bytes — useful
         during incremental disembark when only some scripts are wired.
      4. build_fnt_sys → bytes.

    Args:
        jp_baseline: bytes of the JP LANG/FNT_SYS.BIN (round-trip safe).
        scripts_dir: directory containing fntsys{N}E.txt files.
        script_pattern: filename pattern with `{n}` placeholder (1-indexed).

    Returns:
        Complete FNT_SYS.BIN bytes ready to patch into the ISO.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from d00_tools import encode_text_to_entry
    from font_tools import FNTSYS_BIGRAM_TILE_MAP

    # bigram_override lets the new-font build pass the RELOCATED fntsys bigram map
    # (same glyphs, new positions); default keeps the production map.
    _fntsys_bigram = bigram_override if bigram_override is not None else FNTSYS_BIGRAM_TILE_MAP

    fs = parse_fnt_sys(jp_baseline)
    char_map = _build_fntsys_char_map()

    for pair_idx in range(15):
        script_path = scripts_dir / script_pattern.format(n=pair_idx + 1)
        if not script_path.exists():
            continue
        # Prose-only sections (BIGRAM_PAIRS) use the half-width bigram map so
        # English fits the box; all other sections stay single-char full-width.
        bigram_map = _fntsys_bigram if pair_idx in BIGRAM_PAIRS else None
        lines = _parse_script_records(script_path)
        records: list[bytes] = []
        for line in lines:
            rec = encode_text_to_entry(line, char_map, bigram_tile_map=bigram_map)
            if not rec.endswith(b"\xff\xff"):
                rec = rec + b"\xff\xff"
            records.append(rec)
        fs.pairs[pair_idx].records = records
        # Trailer preserved from JP baseline so byte-equivalence is possible
        # when the scripts are still the JP-text dump.
        fs.pairs[pair_idx].edited = True

    return build_fnt_sys(fs)


def main():
    """CLI helper: parse + report stats."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("path", type=Path, help="path to a FNT_SYS.BIN file")
    args = parser.parse_args()

    data = args.path.read_bytes()
    fs = parse_fnt_sys(data)
    print(f"file: {args.path} ({len(data):,} bytes)")
    print(f"pointers[0]: 0x{fs.pointers[0]:08X} (expected 0x{WRAM_BASE + SECTION_BASE_OFFSET:08X})")
    print(f"section 28 lookup: {len(fs.lookup)} bytes")
    print(f"pairs:")
    for p in fs.pairs:
        sec_total = sum(len(r) for r in p.records) + len(p.data_trailer)
        print(f"  pair {p.pair_index:2d}: {p.record_count:4d} records, "
              f"{sec_total:5d} bytes data, "
              f"trailer={len(p.data_trailer)}")

    roundtrip = build_fnt_sys(fs)
    if roundtrip == data:
        print("round-trip: OK (byte-identical)")
    else:
        diff = sum(1 for a, b in zip(roundtrip, data) if a != b)
        print(f"round-trip: FAIL ({diff} bytes differ; "
              f"len {len(roundtrip)} vs {len(data)})")


if __name__ == "__main__":
    main()
