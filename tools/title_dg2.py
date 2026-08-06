"""Codec for LANG/TITLE.DG2 — the Saturn title-screen CG container.

Self-contained, RE-derived (2026-06-24, see archive/docs/
20260624_cn_credit_fun299c_decompile.md). Lets us add a patch-author credit to
the title screen's empty footer by editing the logo pattern-name map in place.

## Container
Header = u32 count(=4), then `count` (offset:u32, size:u32) pairs (BE). Each
resource is raw/uncompressed:
  - res0 @0x24            8bpp 8x8 char tiles (sky clouds + logo glyphs); the game
                          loads this verbatim into VDP2 VRAM char base 0x0.
  - res1 (LOGO_RES_INDEX) the logo+sky pattern-name maps (16-bit-per-cell grids).
  - res2                  the "GAME OVER" CG tiles.
  - res3                  res2's map.

## Logo map cell format (cracked from PROG_3 FUN_06059dd0, the map expander)
res1 holds the logo plane as a row-major 16-bit grid, width GRID_W, starting at
byte GRID_BASE within res1. Per cell (BE16):
  bits 0-11  tile index into res0 (the expander emits VRAM charno = index*2)
  bit  12    H-flip      bit 13  V-flip      bits 14-15  attr
  0x0000     empty cell (transparent)
The expander writes VRAM pattern name = high(0x40 + (cell>>8 & 0x30) + (cell &
0xC000)), low((cell & 0x0FFF) * 2). Rows 6..22 carry "LANGRISSER III / TEAM
PRESENTS / ©NCS 1996"; rows 23..27 (footer, px 184..224) are empty.

Palette is NOT in the DG2 — it is VDP2 CRAM (dump `vdp2-cram.bin`), used only for
rendering a preview, not for the byte-level codec.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List

try:                                  # imported both as `title_dg2` and `tools.title_dg2`
    from . import png_indexed
except ImportError:
    import png_indexed

# --- container layout ---
HEADER_COUNT_OFF = 0
RES0_OFFSET = 0x24

# --- logo map within res1 ---
LOGO_RES_INDEX = 1
GRID_BASE = 0x508   # byte offset of grid row 0 within res1
GRID_W = 40         # cells per row
GRID_H = 28         # rows (covers the visible 320x224 = 40x28 cells)

CELL_TILE_MASK = 0x0FFF
CELL_HFLIP = 0x1000
CELL_VFLIP = 0x2000

FOOTER_ROW_START = 23  # first empty footer row (px 184)

# --- title palette (256 BGR555 colors, embedded in res1's header) ---
# The CRAM the title loads is res1[PALETTE_RES1_OFFSET .. +512]. The stock palette
# uses ~8 colors; slots 16..31 are unused (black). We inject a 16-level grayscale
# ramp there so anti-aliased credit text (white over a dark outline) renders
# smoothly without disturbing any existing title color.
PALETTE_RES1_OFFSET = 0x108   # byte offset of color index 0 within res1
CREDIT_RAMP_BASE = 16
CREDIT_RAMP_LEVELS = 16


def _bgr555(r, g, b, msb=1):
    return (msb << 15) | ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


def credit_ramp_rgb():
    """The 16 grayscale RGB levels (index k -> palette slot CREDIT_RAMP_BASE+k)."""
    return [(round(k * 255 / (CREDIT_RAMP_LEVELS - 1)),) * 3
            for k in range(CREDIT_RAMP_LEVELS)]


def credit_ramp_slot(rgb):
    """Map an RGB color to its credit-ramp palette slot (by luminance)."""
    lum = (rgb[0] + rgb[1] + rgb[2]) // 3
    k = min(CREDIT_RAMP_LEVELS - 1, round(lum / 255 * (CREDIT_RAMP_LEVELS - 1)))
    return CREDIT_RAMP_BASE + k


def _write_credit_ramp(res1: bytearray) -> None:
    """Write the grayscale credit ramp into res1's embedded palette (free slots)."""
    for k, c in enumerate(credit_ramp_rgb()):
        struct.pack_into(">H", res1,
                         PALETTE_RES1_OFFSET + (CREDIT_RAMP_BASE + k) * 2,
                         _bgr555(*c))


@dataclass
class Resource:
    offset: int
    size: int


@dataclass
class Container:
    raw: bytes
    resources: List[Resource]


def parse_container(data: bytes) -> Container:
    (count,) = struct.unpack_from(">I", data, HEADER_COUNT_OFF)
    res = []
    for i in range(count):
        off, size = struct.unpack_from(">II", data, 4 + i * 8)
        res.append(Resource(off, size))
    return Container(bytes(data), res)


def pack_container(cont: Container) -> bytes:
    """Reproduce the container bytes. Byte-identical when resources are unchanged
    and keep their offsets/sizes."""
    end = max(r.offset + r.size for r in cont.resources)
    out = bytearray(cont.raw[:end])
    struct.pack_into(">I", out, HEADER_COUNT_OFF, len(cont.resources))
    for i, r in enumerate(cont.resources):
        struct.pack_into(">II", out, 4 + i * 8, r.offset, r.size)
    return bytes(out)


class LogoGrid:
    """A GRID_W x GRID_H grid of raw 16-bit cells from res1. Stores raw values so
    decode->encode is exact (attr bits we don't model are preserved)."""

    def __init__(self, cells: List[int]):
        assert len(cells) == GRID_W * GRID_H
        self.cells = cells
        self.width = GRID_W
        self.height = GRID_H

    def _idx(self, row: int, col: int) -> int:
        return row * GRID_W + col

    def raw(self, row: int, col: int) -> int:
        return self.cells[self._idx(row, col)]

    def tile(self, row: int, col: int) -> int:
        return self.cells[self._idx(row, col)] & CELL_TILE_MASK

    def flips(self, row: int, col: int):
        c = self.cells[self._idx(row, col)]
        return bool(c & CELL_HFLIP), bool(c & CELL_VFLIP)

    def set_tile(self, row: int, col: int, tile: int,
                 hflip: bool = False, vflip: bool = False, attr: int = 0) -> None:
        cell = (tile & CELL_TILE_MASK)
        if hflip:
            cell |= CELL_HFLIP
        if vflip:
            cell |= CELL_VFLIP
        cell |= (attr & 0x3) << 14
        self.cells[self._idx(row, col)] = cell

    def clear(self, row: int, col: int) -> None:
        self.cells[self._idx(row, col)] = 0


def decode_logo_grid(dg2: bytes) -> LogoGrid:
    cont = parse_container(dg2)
    res1_off = cont.resources[LOGO_RES_INDEX].offset
    base = res1_off + GRID_BASE
    cells = [
        struct.unpack_from(">H", dg2, base + i * 2)[0]
        for i in range(GRID_W * GRID_H)
    ]
    return LogoGrid(cells)


def encode_logo_grid(dg2: bytes, grid: LogoGrid) -> bytes:
    """Write the grid cells back into res1 in place (size-preserving) and repack.
    With an unmodified grid this returns `dg2` byte-for-byte."""
    out = bytearray(dg2)
    cont = parse_container(dg2)
    res1_off = cont.resources[LOGO_RES_INDEX].offset
    base = res1_off + GRID_BASE
    for i, cell in enumerate(grid.cells):
        struct.pack_into(">H", out, base + i * 2, cell)
    return pack_container(parse_container(bytes(out)))


def footer_cell_count(dg2: bytes, footer_rows=None) -> int:
    """Number of non-empty (drawn) cells in the footer rows of the logo map.
    Used as a build-time assertion that the mandatory credit is actually present."""
    if footer_rows is None:
        footer_rows = range(FOOTER_ROW_START, GRID_H)
    grid = decode_logo_grid(dg2)
    return sum(1 for r in footer_rows for c in range(GRID_W) if grid.tile(r, c))


def repack(blobs: List[bytes]) -> bytes:
    """Build a container from resource blobs (recomputing offsets). With the
    original blobs at their natural contiguous offsets this equals the input."""
    hdr = 4 + len(blobs) * 8
    out = bytearray(struct.pack(">I", len(blobs)))
    off = hdr
    offs = []
    for b in blobs:
        offs.append(off)
        off += len(b)
    for o, b in zip(offs, blobs):
        out += struct.pack(">II", o, len(b))
    for b in blobs:
        out += b
    return bytes(out)


def _read_indexed_png(path: str):
    """(width, height, pixels) — pixels[x, y] is a palette index.

    Decoded with the stdlib (tools/png_indexed.py), NOT Pillow: the build must
    run on a bare Python 3 (issue #7 — v0.7.0 crashed here at step 6 on any
    machine without Pillow, after five successful steps)."""
    return png_indexed.read_indexed_png(path)


def apply_footer_indexed(dg2: bytes, indexed_png_path: str,
                         footer_rows=None) -> bytes:
    """Overlay an indexed (mode 'P') PNG's ADDED content onto the title logo map.
    Cells that are EMPTY in the original art (the top margin + the footer) take
    the PNG's content (tiled into res0, dedup + append); existing logo cells are
    left byte-exactly untouched. This lets the credit add a footer line AND extra
    marks (e.g. a version tag in the top corner) without disturbing the logo.
    `footer_rows` is accepted for back-compat but ignored (the empty-cell rule
    covers the footer)."""
    _, _, px = _read_indexed_png(indexed_png_path)
    cont = parse_container(dg2)
    res0 = bytearray(dg2[RES0_OFFSET:RES0_OFFSET + cont.resources[0].size])
    tiles = [bytes(res0[i * 64:i * 64 + 64]) for i in range(len(res0) // 64)]
    tindex = {t: i for i, t in enumerate(tiles)}
    grid = decode_logo_grid(dg2)

    for row in range(GRID_H):
        for col in range(GRID_W):
            if grid.tile(row, col) != 0:
                continue  # original logo cell — preserve exactly
            blk = bytearray(64)
            nz = False
            for y in range(8):
                for x in range(8):
                    v = px[col * 8 + x, row * 8 + y]
                    blk[y * 8 + x] = v
                    if v:
                        nz = True
            if not nz:
                continue  # empty here too
            tb = bytes(blk)
            ti = tindex.get(tb)
            if ti is None:
                ti = len(tiles)
                tiles.append(tb)
                tindex[tb] = ti
            grid.set_tile(row, col, ti)

    res0n = b"".join(tiles)
    res1 = bytearray(dg2[cont.resources[1].offset:
                         cont.resources[1].offset + cont.resources[1].size])
    for i, cell in enumerate(grid.cells):
        struct.pack_into(">H", res1, GRID_BASE + i * 2, cell)
    _write_credit_ramp(res1)   # inject the credit's grayscale ramp into the palette
    res2 = dg2[cont.resources[2].offset:cont.resources[2].offset + cont.resources[2].size]
    res3 = dg2[cont.resources[3].offset:cont.resources[3].offset + cont.resources[3].size]
    return repack([res0n, bytes(res1), res2, res3])


# --- full-logo rebuild (move logo elements + freeform colors, Derek-style) ----
# Stock title colors occupy palette slots 0..8; KEEP them and the whole scrolling
# sky (a SEPARATE map that references the cloud tiles in res0 by index). The
# artist's edit lives in slots 9..255.
PRESERVED_PALETTE_SLOTS = 9


def _indexed_png_palette(path: str):
    """The (R,G,B) palette (256 entries, zero-padded) of an indexed PNG.
    Stdlib decode — see _read_indexed_png."""
    return png_indexed.read_indexed_palette(path)


def apply_full_logo(dg2: bytes, indexed_png_path: str) -> bytes:
    """Rebuild the ENTIRE logo plane from an indexed (mode 'P') 320x224 PNG.

    Unlike apply_footer_indexed (which only FILLS empty cells, preserving the
    original logo), this rewrites EVERY cell, so the artist can MOVE logo elements:
    a cell that is transparent (index 0) in the PNG is CLEARED (index 0 = the
    scrolling sky shows through — this also erases an element's OLD position when
    it was moved); a painted cell takes the new content.

    Byte-safe like apply_footer_indexed: res0 is APPEND-ONLY (the original cloud +
    logo tiles keep their indices, so the separate sky map never breaks), and the
    stock palette slots 0..8 are LEFT INTACT — only slots 9..255 (the artist's
    colors, carried in the PNG's own palette) are injected into res1's CRAM.
    """
    _, _, px = _read_indexed_png(indexed_png_path)
    palette = _indexed_png_palette(indexed_png_path)
    cont = parse_container(dg2)
    res0 = bytearray(dg2[RES0_OFFSET:RES0_OFFSET + cont.resources[0].size])
    tiles = [bytes(res0[i * 64:i * 64 + 64]) for i in range(len(res0) // 64)]
    tindex = {t: i for i, t in enumerate(tiles)}
    grid = decode_logo_grid(dg2)

    for row in range(GRID_H):
        for col in range(GRID_W):
            blk = bytearray(64)
            nz = False
            for y in range(8):
                for x in range(8):
                    v = px[col * 8 + x, row * 8 + y]
                    blk[y * 8 + x] = v
                    if v:
                        nz = True
            if not nz:
                grid.clear(row, col)   # transparent -> empty (sky shows; clears moves)
                continue
            tb = bytes(blk)
            ti = tindex.get(tb)
            if ti is None:
                ti = len(tiles)
                tiles.append(tb)
                tindex[tb] = ti
            grid.set_tile(row, col, ti)

    res1 = bytearray(dg2[cont.resources[1].offset:
                         cont.resources[1].offset + cont.resources[1].size])
    for i in range(PRESERVED_PALETTE_SLOTS, 256):   # inject the artist's colors only
        r, g, b = palette[i]
        struct.pack_into(">H", res1, PALETTE_RES1_OFFSET + i * 2, _bgr555(r, g, b))
    for i, cell in enumerate(grid.cells):
        struct.pack_into(">H", res1, GRID_BASE + i * 2, cell)
    res2 = dg2[cont.resources[2].offset:cont.resources[2].offset + cont.resources[2].size]
    res3 = dg2[cont.resources[3].offset:cont.resources[3].offset + cont.resources[3].size]
    return repack([b"".join(tiles), bytes(res1), res2, res3])


# --- preview rendering (optional; needs a CRAM palette + Pillow) ---
def render_logo_png(dg2: bytes, cram: bytes, out_path: str, scale: int = 1) -> None:
    """Render the logo layer to a transparent PNG using a VDP2 CRAM dump."""
    from PIL import Image

    cont = parse_container(dg2)
    res0 = dg2[RES0_OFFSET:RES0_OFFSET + cont.resources[0].size]
    pal = []
    for i in range(0, len(cram), 2):
        v = struct.unpack_from(">H", cram, i)[0]
        pal.append(((v & 0x1F) * 255 // 31,
                    ((v >> 5) & 0x1F) * 255 // 31,
                    ((v >> 10) & 0x1F) * 255 // 31))
    grid = decode_logo_grid(dg2)
    nt = len(res0) // 64
    im = Image.new("RGBA", (GRID_W * 8, GRID_H * 8), (0, 0, 0, 0))
    px = im.load()
    for row in range(GRID_H):
        for col in range(GRID_W):
            tile = grid.tile(row, col)
            if tile <= 0 or tile >= nt:
                continue
            hf, vf = grid.flips(row, col)
            b = tile * 64
            for y in range(8):
                for x in range(8):
                    idx = res0[b + (7 - y if vf else y) * 8 + (7 - x if hf else x)]
                    if idx == 0:
                        continue
                    px[col * 8 + x, row * 8 + y] = (*pal[idx], 255)
    if scale != 1:
        im = im.resize((GRID_W * 8 * scale, GRID_H * 8 * scale), Image.NEAREST)
    im.save(out_path)
