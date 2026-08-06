#!/usr/bin/env python3
"""png_indexed.py — stdlib reader for indexed (palette) PNG images.

The build embeds the mandatory title credit from an indexed PNG. That used to
go through Pillow, which made `python3 build.py` die at step 6 on any machine
without it (issue #7 — the user had already waited through five steps). The
patch has no other third-party dependency, so decoding the handful of PNGs the
build reads is done here with `zlib` + `struct` only.

Scope: colour type 3 (palette) at bit depths 1/2/4/8, non-interlaced — what
every "save as indexed PNG" export produces. Anything else raises a clear
error naming what to re-export, instead of a cryptic crash mid-build.

Pixel access mimics Pillow's `Image.load()`: `px[x, y]` -> palette index, so
call sites read the same either way.
"""
import struct
import zlib

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
COLOR_TYPE_PALETTE = 3


class _Pixels:
    """Row-major palette indices with Pillow's `px[x, y]` access."""

    __slots__ = ("_rows", "width", "height")

    def __init__(self, rows, width, height):
        self._rows = rows
        self.width = width
        self.height = height

    def __getitem__(self, xy):
        x, y = xy
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"pixel ({x}, {y}) outside {self.width}x{self.height}")
        return self._rows[y][x]


def _iter_chunks(data: bytes):
    if data[:8] != PNG_MAGIC:
        raise ValueError("not a PNG file (bad signature)")
    pos = 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack_from(">I", data, pos)
        ctype = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        yield ctype, payload
        pos += 12 + length          # length + type + payload + CRC


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(raw: bytes, width: int, height: int, bit_depth: int) -> list[bytearray]:
    """Undo the per-scanline PNG filters. Indexed images are 1 channel, so the
    filter unit is 1 byte for depth 8 and (per spec) also 1 byte below it."""
    stride = (width * bit_depth + 7) // 8
    bpp = 1
    out = []
    prev = bytearray(stride)
    pos = 0
    for row in range(height):
        if pos >= len(raw):
            raise ValueError(f"PNG data ends early at scanline {row}")
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        if len(line) != stride:
            raise ValueError(f"PNG scanline {row} truncated")
        pos += stride
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                upleft = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], upleft)) & 0xFF
        else:
            raise ValueError(f"unknown PNG filter type {ftype} on scanline {row}")
        out.append(line)
        prev = line
    return out


def _expand(rows, width: int, bit_depth: int) -> list[bytearray]:
    """Unpack sub-byte palette indices to one index per pixel."""
    if bit_depth == 8:
        return rows
    per_byte = 8 // bit_depth
    mask = (1 << bit_depth) - 1
    expanded = []
    for line in rows:
        px = bytearray(width)
        for x in range(width):
            byte = line[x // per_byte]
            shift = 8 - bit_depth * (x % per_byte + 1)
            px[x] = (byte >> shift) & mask
        expanded.append(px)
    return expanded


def _parse(path: str):
    data = open(path, "rb").read()
    ihdr = None
    palette = b""
    idat = bytearray()
    for ctype, payload in _iter_chunks(data):
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", payload[:13])
        elif ctype == b"PLTE":
            palette = payload
        elif ctype == b"IDAT":
            idat += payload
        elif ctype == b"IEND":
            break
    if ihdr is None:
        raise ValueError(f"{path}: no IHDR chunk")
    width, height, bit_depth, color_type, _comp, _filt, interlace = ihdr
    if color_type != COLOR_TYPE_PALETTE:
        raise ValueError(
            f"{path}: expected an indexed (palette) PNG, got PNG colour type "
            f"{color_type} — re-export as indexed/paletted")
    if bit_depth not in (1, 2, 4, 8):
        raise ValueError(f"{path}: unsupported indexed bit depth {bit_depth}")
    if interlace:
        raise ValueError(f"{path}: interlaced PNGs are not supported — "
                         "re-export without Adam7 interlacing")
    return width, height, bit_depth, palette, bytes(idat)


def read_indexed_png(path: str):
    """(width, height, pixels) for an indexed PNG. `pixels[x, y]` = palette index."""
    width, height, bit_depth, _palette, idat = _parse(path)
    rows = _expand(_unfilter(zlib.decompress(idat), width, height, bit_depth),
                   width, bit_depth)
    return width, height, _Pixels(rows, width, height)


def read_indexed_palette(path: str) -> list[tuple[int, int, int]]:
    """The PNG's 256-entry (R, G, B) palette, zero-padded like Pillow's."""
    *_, palette, _idat = _parse(path)
    pal = list(palette) + [0] * (768 - len(palette))
    return [(pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]) for i in range(256)]
