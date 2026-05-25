"""plot_tools.py — parse / build LANG/PLOT.DAT for the EN patch.

Format (verified against CN release LANG/PLOT.DAT):

  bytes 0..3   : BE32 total file size
  bytes 4..73  : 35 × BE16 block offsets (start of each block body)
  bytes 74..   : block bodies (concatenated)

Each block body:

  bytes 0..1   : 0xFFF8                    (block-start marker)
  bytes 2..3   : BE16 block_id (0x0001..0x0023 for blocks 0..34)
  bytes 4..    : BE16 tile codes — text + control codes
                 0xFFFE                    block terminator (mandatory at end)
                 0xFFFD / 0xFFFC          paragraph / line break
                 < 0xFF00                 visible tile codes

The plotE.txt source format mirrors this 1:1: each block opens with
`<$FFF8000N>` and ends with `<$FFFE>`, paragraphs separated by
`<$FFFD>` / `<$FFFC>`. Same engine encoder used for D00.DAT
(`d00_tools.encode_text_to_entry`).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

N_BLOCKS = 35
HEADER_SIZE = 4 + N_BLOCKS * 2  # 74 bytes


@dataclass
class PlotBlock:
    block_id: int            # 1..35 (per-file ordinal)
    raw_bytes: bytes         # FULL bytes including FFF8XXXX header + FFFE terminator


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def parse_plot(data: bytes) -> list[PlotBlock]:
    """Parse a PLOT.DAT into 35 PlotBlock entries (raw bytes per block)."""
    if len(data) < HEADER_SIZE:
        raise ValueError(f"PLOT.DAT too short: {len(data)} < {HEADER_SIZE}")
    file_size = struct.unpack(">I", data[0:4])[0]
    if file_size != len(data):
        # Tolerate but warn — saturn images sometimes pad
        pass
    offsets = list(struct.unpack(f">{N_BLOCKS}H", data[4:HEADER_SIZE]))
    offsets.append(file_size)  # sentinel for last block end

    blocks = []
    for i in range(N_BLOCKS):
        start, end = offsets[i], offsets[i + 1]
        if start < HEADER_SIZE or end > len(data) or start > end:
            raise ValueError(f"block {i} bad range: {start}..{end}")
        chunk = data[start:end]
        # The block_id follows the 0xFFF8 marker
        if len(chunk) < 4:
            raise ValueError(f"block {i} too short")
        marker = struct.unpack(">H", chunk[0:2])[0]
        block_id = struct.unpack(">H", chunk[2:4])[0]
        if marker != 0xFFF8:
            raise ValueError(f"block {i}: missing FFF8 marker (got {marker:04x})")
        blocks.append(PlotBlock(block_id=block_id, raw_bytes=chunk))
    return blocks


# ---------------------------------------------------------------------------
# Build / re-emit
# ---------------------------------------------------------------------------

def build_plot(blocks: list[PlotBlock]) -> bytes:
    """Concatenate block bodies + recompute offset table + file size header."""
    if len(blocks) != N_BLOCKS:
        raise ValueError(f"need exactly {N_BLOCKS} blocks (got {len(blocks)})")
    body_parts = []
    offsets = []
    cursor = HEADER_SIZE
    for b in blocks:
        offsets.append(cursor)
        body_parts.append(b.raw_bytes)
        cursor += len(b.raw_bytes)
    file_size = cursor

    out = bytearray()
    out.extend(struct.pack(">I", file_size))
    out.extend(struct.pack(f">{N_BLOCKS}H", *offsets))
    for p in body_parts:
        out.extend(p)
    assert len(out) == file_size
    return bytes(out)


# ---------------------------------------------------------------------------
# Script-file encoder
# ---------------------------------------------------------------------------

def parse_plot_script(path: Path) -> list[str]:
    """Read plotE.txt, return 35 strings — one full block per entry.

    Each block opens with `<$FFF8000N>` and ends with `<$FFFE>`. The
    parser collects text between these markers (inclusive of the
    `<$FFFD>` / `<$FFFC>` separators inside) and joins lines with
    nothing (the separators already encode line breaks)."""
    text = path.read_text(encoding="utf-8")
    # Drop CWX dumper preamble lines, if any
    lines = []
    for ln in text.splitlines():
        if ln.startswith("Langrisser") or ln.startswith("Cyber"):
            continue
        lines.append(ln)
    flat = "\n".join(lines)

    # Split on '<$FFF8' opener — keep the marker
    blocks: list[str] = []
    parts = flat.split("<$FFF8")
    for idx, part in enumerate(parts[1:]):  # parts[0] is preamble
        block_text = "<$FFF8" + part
        end = block_text.find("<$FFFE>")
        if end < 0:
            raise ValueError(f"block missing <$FFFE> terminator: "
                             f"{block_text[:80]!r}")
        block_text = block_text[: end + len("<$FFFE>")]
        # Last block: JP and CN ship a trailing 0xFFFF as the file-end
        # sentinel right after FFFE. Engine needs it; preserve it.
        if idx == N_BLOCKS - 1:
            block_text += "<$FFFF>"
        blocks.append(block_text)

    if len(blocks) != N_BLOCKS:
        raise ValueError(
            f"expected {N_BLOCKS} blocks, parsed {len(blocks)} from {path}")
    return blocks


def encode_plot_script(script_path: Path,
                        char_tile_map: dict[str, int],
                        bigram_tile_map: dict[tuple[str, str], int] | None = None
                        ) -> bytes:
    """Compile plotE.txt → PLOT.DAT bytes ready for the engine.

    Uses `d00_tools.encode_text_to_entry` for each block (same encoder
    as D00 dialogue — handles `<$XXXX>` escapes, bigrams, and
    `[diehardt's name]`)."""
    from d00_tools import encode_text_to_entry  # late import: tools-internal

    block_texts = parse_plot_script(script_path)
    blocks: list[PlotBlock] = []
    for i, txt in enumerate(block_texts):
        raw = encode_text_to_entry(txt, char_tile_map, bigram_tile_map)
        # Sanity: block 1..34 end with FFFE; block 35 ends with FFFE FFFF
        # (file-end sentinel preserved from JP/CN format)
        if i == N_BLOCKS - 1:
            if raw[-4:] != b"\xff\xfe\xff\xff":
                raise ValueError(
                    f"block 35: encoded body must end with FFFE FFFF "
                    f"(got {raw[-4:].hex()})")
        elif raw[-2:] != b"\xff\xfe":
            raise ValueError(
                f"block {i+1}: encoded body must end with FFFE "
                f"(got {raw[-4:].hex()})")
        # Sanity: block must start with FFF8
        if raw[:2] != b"\xff\xf8":
            raise ValueError(
                f"block {i+1}: encoded body must start with FFF8 "
                f"(got {raw[:4].hex()})")
        blocks.append(PlotBlock(block_id=i + 1, raw_bytes=raw))
    return build_plot(blocks)


# ---------------------------------------------------------------------------
# Self-test: round-trip against a known PLOT.DAT
# ---------------------------------------------------------------------------

def round_trip_test(data: bytes) -> None:
    """Parse + re-emit must produce byte-identical output."""
    blocks = parse_plot(data)
    assert len(blocks) == N_BLOCKS
    rebuilt = build_plot(blocks)
    if rebuilt != data:
        # Find first diff for diagnostics
        for i, (a, b) in enumerate(zip(rebuilt, data)):
            if a != b:
                raise AssertionError(
                    f"round-trip mismatch at byte {i}: "
                    f"got {a:02x} expected {b:02x}")
        if len(rebuilt) != len(data):
            raise AssertionError(
                f"round-trip length mismatch: {len(rebuilt)} vs {len(data)}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "round-trip":
        path = Path(sys.argv[2])
        round_trip_test(path.read_bytes())
        print(f"  round-trip OK: {path.name}")
