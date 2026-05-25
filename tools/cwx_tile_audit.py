#!/usr/bin/env python3
"""cwx_tile_audit.py — Task 3: audit tile range 1488-1620.

Outputs:
  build/cwx_tile_audit.png — 16x16 grid render of every tile in the
                              CWX hand-drawn range.
  build/cwx_tile_audit.txt — per-tile ASCII + Eagle II nearest-match
                              with confidence score + call-site list.

The CWX-range tiles (`_CWX_MENU_TILES`, `_CWX_BETWEEN_TILES` in
`tools/font_tools.py`, plus `_CWX_SPECIAL_BIGRAMS` at slot 1500) are
hand-drawn glyphs that compiled binaries (PROG_*.BIN, A0LANG.BIN,
SYSWIN.BIN) reference by tile index. To swap them to Eagle II we
need to know:

1. *What char or char-pair does each tile render?*  → visual + matching
2. *Which binaries reference it?*  → byte-grep BE16 codes

Then `_CWX_TILE_OVERRIDES = {idx: (left, right)}` in `font_tools.py`
drives Eagle II re-rasterization at the same slots, leaving the
patches/*.bin call sites byte-identical (they reference tile *codes*,
not tile *bytes*).

Usage:
  python3 tools/cwx_tile_audit.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from font_tools import (  # noqa: E402
    _CWX_MENU_TILES, _CWX_BETWEEN_TILES, _CWX_SPECIAL_BIGRAMS,
    _LETTER_GLYPHS, _UC_STANDALONE_TILES, _PUNCT_GLYPHS,
    _BLANK_GLYPH, _APOSTROPHE_GLYPH, _DIGIT_TILES,
    _interleave,
)

PROJECT = SCRIPT_DIR.parent
PATCHES_DIR = PROJECT / "patches"
BUILD_DIR = PROJECT / "build"


# ---------------------------------------------------------------------------
# Tile data accessors
# ---------------------------------------------------------------------------

def collect_cwx_tiles() -> dict[int, bytes]:
    """All hand-drawn tiles in the 1488..1620 range that font_tools.py
    treats as preexisting (i.e. NOT regenerated from glyph data).
    """
    tiles: dict[int, bytes] = {}
    tiles.update(_CWX_BETWEEN_TILES)
    tiles.update(_CWX_MENU_TILES)
    # Tile 1500 is built from _CWX_SPECIAL_BIGRAMS at runtime; we
    # synthesize it here so the audit covers it too.
    for (left, right), idx in _CWX_SPECIAL_BIGRAMS.items():
        l_glyph = _APOSTROPHE_GLYPH if left == "'" else _LETTER_GLYPHS.get(left, _BLANK_GLYPH)
        r_glyph = _APOSTROPHE_GLYPH if right == "'" else _LETTER_GLYPHS.get(right, _BLANK_GLYPH)
        tiles[idx] = _interleave(l_glyph, r_glyph)
    return tiles


# ---------------------------------------------------------------------------
# ASCII rendering
# ---------------------------------------------------------------------------

def tile_to_ascii(tile: bytes) -> list[str]:
    """Render a 32-byte 16x16 1bpp tile as 16 lines of 16 chars each."""
    rows = []
    for r in range(16):
        b0 = tile[r * 2]
        b1 = tile[r * 2 + 1]
        line = []
        for c in range(8):
            line.append("█" if b0 & (0x80 >> c) else "·")
        for c in range(8):
            line.append("█" if b1 & (0x80 >> c) else "·")
        rows.append("".join(line))
    return rows


def half_to_ascii(half: bytes) -> list[str]:
    """Render an 8x16 1bpp half-tile as 16 lines of 8 chars each."""
    rows = []
    for r in range(16):
        b = half[r]
        line = []
        for c in range(8):
            line.append("█" if b & (0x80 >> c) else "·")
        rows.append("".join(line))
    return rows


# ---------------------------------------------------------------------------
# PNG rendering (via PIL)
# ---------------------------------------------------------------------------

def render_png(tiles: dict[int, bytes], out_path: Path,
               cols: int = 8, scale: int = 4) -> None:
    """Render all tiles to a PNG grid: each cell shows the 16x16 glyph
    upscaled, with the tile index as a label below.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PIL not available; skipping PNG render", file=sys.stderr)
        return

    sorted_idx = sorted(tiles.keys())
    n = len(sorted_idx)
    rows_grid = (n + cols - 1) // cols
    cell_w = 16 * scale + 8
    cell_h = 16 * scale + 16  # +16 for index label
    pad = 4

    width = cols * cell_w + pad * 2
    height = rows_grid * cell_h + pad * 2
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 10)
    except OSError:
        font = ImageFont.load_default()

    for i, idx in enumerate(sorted_idx):
        tile = tiles[idx]
        row = i // cols
        col = i % cols
        x = pad + col * cell_w + 4
        y = pad + row * cell_h + 14

        # Draw glyph
        for r in range(16):
            b0 = tile[r * 2]
            b1 = tile[r * 2 + 1]
            for c in range(16):
                byte = b0 if c < 8 else b1
                bit = c % 8
                if byte & (0x80 >> bit):
                    px = x + c * scale
                    py = y + r * scale
                    draw.rectangle(
                        [px, py, px + scale - 1, py + scale - 1],
                        fill=(0, 0, 0))
        # Index label
        draw.text((x, y - 12), str(idx), fill=(80, 80, 80), font=font)
        # Frame
        draw.rectangle(
            [x - 1, y - 1, x + 16 * scale, y + 16 * scale],
            outline=(200, 200, 200))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


# ---------------------------------------------------------------------------
# Eagle II nearest-neighbour matching
# ---------------------------------------------------------------------------

def _all_eagle_halfs() -> dict[str, bytes]:
    """Half-glyphs (8x16 = 16 bytes) for every Eagle II char we have."""
    halfs: dict[str, bytes] = {}
    halfs[" "] = _BLANK_GLYPH
    for ch, g in _LETTER_GLYPHS.items():
        halfs[ch] = g
    for ch, g in _PUNCT_GLYPHS.items():
        halfs[ch] = g
    halfs["'"] = _APOSTROPHE_GLYPH
    return halfs


def _all_eagle_full_tiles() -> dict[str, bytes]:
    """Full-tile (32-byte) Eagle II UC standalones + digits — these are
    rendered at full 16x16 (not bigrams), so for matching CWX big-glyph
    tiles we treat them as candidates too.
    """
    tiles: dict[str, bytes] = {}
    for ch, t in _UC_STANDALONE_TILES.items():
        tiles[f"UC:{ch}"] = t
    for d, t in _DIGIT_TILES.items():
        tiles[f"DIG:{d}"] = t
    return tiles


def _hamming_distance(a: bytes, b: bytes) -> int:
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))


def best_bigram_match(tile: bytes, halfs: dict[str, bytes]
                      ) -> tuple[str, str, int]:
    """Find Eagle II (left, right) char pair minimising Hamming distance
    to the CWX tile, treating tile as 8x16 + 8x16 bigram.

    Returns (left, right, distance_bits).
    """
    left_half = bytes(tile[r * 2] for r in range(16))
    right_half = bytes(tile[r * 2 + 1] for r in range(16))
    best_l, best_r = " ", " "
    best_l_d = 256
    best_r_d = 256
    for ch, g in halfs.items():
        d = _hamming_distance(left_half, g)
        if d < best_l_d:
            best_l_d = d
            best_l = ch
        d = _hamming_distance(right_half, g)
        if d < best_r_d:
            best_r_d = d
            best_r = ch
    return best_l, best_r, best_l_d + best_r_d


def best_full_match(tile: bytes, full: dict[str, bytes]) -> tuple[str, int]:
    best_label = "?"
    best_d = 4096
    for label, candidate in full.items():
        d = _hamming_distance(tile, candidate)
        if d < best_d:
            best_d = d
            best_label = label
    return best_label, best_d


# ---------------------------------------------------------------------------
# Byte-grep call sites
# ---------------------------------------------------------------------------

def find_call_sites(tile_idx: int, blobs: dict[str, bytes]
                    ) -> dict[str, list[int]]:
    """For each binary in `blobs`, return BE16 offsets where this
    tile_idx appears (even-aligned only).
    """
    needle = tile_idx.to_bytes(2, "big")
    sites: dict[str, list[int]] = {}
    for name, data in blobs.items():
        offsets = []
        # BE16 codes are typically 2-byte aligned in tile-encoded text
        for i in range(0, len(data) - 1, 2):
            if data[i:i + 2] == needle:
                offsets.append(i)
        if offsets:
            sites[name] = offsets
    return sites


def context_around(data: bytes, offset: int, n_codes: int = 6) -> list[int]:
    """Read 2*n_codes BE16 values centered on offset (n_codes before,
    n_codes after, including offset itself)."""
    out = []
    start = max(0, offset - n_codes * 2)
    end = min(len(data), offset + (n_codes + 1) * 2)
    for i in range(start, end, 2):
        if i + 1 >= len(data):
            break
        out.append((data[i] << 8) | data[i + 1])
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def write_report(tiles: dict[int, bytes], halfs: dict[str, bytes],
                 full: dict[str, bytes], blobs: dict[str, bytes],
                 out_path: Path) -> dict[int, dict]:
    """Emit text report; return per-tile dict for further processing."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows: dict[int, dict] = {}
    lines: list[str] = []
    lines.append(f"# CWX tile audit ({len(tiles)} tiles in 1488-1620 range)\n")
    lines.append(
        "Each tile shown as 16x16 ASCII art + Eagle II bigram nearest-match\n"
        "(Hamming distance over 32 bytes = 256 bits). Lower distance = stronger\n"
        "match. Distance ≤ 32 ≈ very likely correct; 32-80 = plausible;\n"
        "≥ 80 = unrecognised (composite/icon).\n")
    lines.append(f"Bytes-grep targets: {sorted(blobs)}\n\n---\n")

    for idx in sorted(tiles):
        tile = tiles[idx]
        ascii_rows = tile_to_ascii(tile)
        bg_l, bg_r, bg_d = best_bigram_match(tile, halfs)
        full_label, full_d = best_full_match(tile, full)
        sites = find_call_sites(idx, blobs)
        n_sites = sum(len(v) for v in sites.values())

        rows[idx] = {
            "best_bigram": (bg_l, bg_r),
            "bigram_dist": bg_d,
            "best_full": full_label,
            "full_dist": full_d,
            "call_sites": sites,
        }

        lines.append(f"\n## Tile {idx} ({n_sites} call sites)\n")
        lines.append("```")
        lines.extend(ascii_rows)
        lines.append("```")
        lines.append(
            f"  Eagle II bigram match:  ({bg_l!r}, {bg_r!r})  "
            f"dist={bg_d} bits"
        )
        lines.append(
            f"  Eagle II full-tile:     {full_label}  dist={full_d} bits"
        )
        if sites:
            for binary, offs in sorted(sites.items()):
                head = ", ".join(f"{o:#x}" for o in offs[:5])
                if len(offs) > 5:
                    head += f", … (+{len(offs) - 5} more)"
                lines.append(f"  {binary}: {len(offs)} sites @ {head}")
                # Show context for first hit
                first = offs[0]
                ctx = context_around(blobs[binary], first, n_codes=4)
                ctx_repr = " ".join(
                    "*"
                    f"{w:04x}*" if w == idx else f"{w:04x}"
                    for w in ctx
                )
                lines.append(f"    context: {ctx_repr}")
        else:
            lines.append("  (no call sites found in patches/*.bin)")

    out_path.write_text("\n".join(lines))
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_patch_blobs() -> dict[str, bytes]:
    blobs = {}
    for p in sorted(PATCHES_DIR.glob("*.bin")):
        blobs[p.name] = p.read_bytes()
    return blobs


def main() -> int:
    tiles = collect_cwx_tiles()
    halfs = _all_eagle_halfs()
    full = _all_eagle_full_tiles()
    blobs = load_patch_blobs()

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    render_png(tiles, BUILD_DIR / "cwx_tile_audit.png", cols=10, scale=6)
    rows = write_report(
        tiles, halfs, full, blobs, BUILD_DIR / "cwx_tile_audit.txt"
    )

    # Summary
    print(f"audited {len(tiles)} tiles")
    bins_counts = Counter()
    for r in rows.values():
        for binary in r["call_sites"]:
            bins_counts[binary] += 1
    for b, n in bins_counts.most_common():
        print(f"  {b}: {n} tiles referenced")

    high_conf = sum(1 for r in rows.values() if r["bigram_dist"] <= 32)
    plausible = sum(1 for r in rows.values() if 32 < r["bigram_dist"] <= 80)
    weak = sum(1 for r in rows.values() if r["bigram_dist"] > 80)
    print(f"  bigram match distribution: "
          f"≤32 bits={high_conf}, 33-80={plausible}, >80={weak}")
    print(f"  reports: build/cwx_tile_audit.png, build/cwx_tile_audit.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
