#!/usr/bin/env python3
"""
iso_tools.py - ISO9660 Mode 2 Form 1 tools for Sega Saturn disc images.

Handles reading, extracting, and patching files in raw 2352-byte sector images.
Includes EDC/ECC recalculation for modified sectors.
"""

import math
import struct
from pathlib import Path

SECTOR_SIZE = 2352
USER_OFFSET = 16
USER_SIZE = 2048


# ---------------------------------------------------------------------------
# EDC / ECC calculation for Mode 2 Form 1 sectors
# ---------------------------------------------------------------------------

def _build_edc_table():
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xD8018001
            else:
                crc >>= 1
        table.append(crc)
    return table

_EDC_TABLE = _build_edc_table()


def compute_edc(data: bytes) -> int:
    edc = 0
    for b in data:
        edc = (edc >> 8) ^ _EDC_TABLE[(edc ^ b) & 0xFF]
    return edc


def compute_ecc_block(data: bytes, major_count: int, minor_count: int,
                      major_mult: int, minor_inc: int) -> bytes:
    result = bytearray(major_count * 2)
    for j in range(2):
        for i in range(major_count):
            a = 0
            b = 0
            for k in range(minor_count):
                idx = (i * major_mult + k * minor_inc) % (minor_count * major_mult)
                if idx < len(data):
                    val = data[idx]
                else:
                    val = 0
                a ^= val
                b ^= val
                a = ((a << 1) ^ (0x11D if a & 0x80 else 0)) & 0xFF
            result[i * 2 + j] = a ^ b
            # Shift to odd bytes on second pass
        data = bytes([data[k] if k < len(data) else 0 for k in range(1, len(data) + 1)])
    return bytes(result)


def rewrite_sector_edc_ecc(sector: bytearray) -> None:
    """Recalculate EDC and ECC for a Mode 1/2352 sector in-place."""
    # Mode 1 layout:
    #   0-11: sync pattern
    #   12-15: header (min, sec, frac, mode)
    #   16-2063: user data (2048 bytes)
    #   2064-2067: EDC
    #   2068-2075: reserved (zeros)
    #   2076-2247: P parity (172 bytes)
    #   2248-2351: Q parity (104 bytes)

    # EDC over bytes 0..2063
    edc = compute_edc(bytes(sector[:2064]))
    struct.pack_into('<I', sector, 2064, edc)

    # Reserved zeros
    sector[2068:2076] = b'\x00' * 8

    # P parity: 86 vectors of 24 bytes
    p_data = bytes(sector[12:2076])
    p_result = bytearray(172)
    for i in range(86):
        a0, a1 = 0, 0
        for j in range(24):
            idx = i + j * 86
            if idx < len(p_data):
                val = p_data[idx]
            else:
                val = 0
            a0 ^= val
            a1 ^= val
            a0 = ((a0 << 1) ^ (0x11D if a0 & 0x80 else 0)) & 0xFF
        p_result[2 * i] = a0 ^ a1
        p_result[2 * i + 1] = a0
    sector[2076:2248] = p_result

    # Q parity: 52 vectors of 43 bytes
    q_data = bytes(sector[12:2248])
    q_result = bytearray(104)
    for i in range(52):
        a0, a1 = 0, 0
        for j in range(43):
            idx = (i + j * 52) % (43 * 52)
            if idx < len(q_data):
                val = q_data[idx]
            else:
                val = 0
            a0 ^= val
            a1 ^= val
            a0 = ((a0 << 1) ^ (0x11D if a0 & 0x80 else 0)) & 0xFF
        q_result[2 * i] = a0 ^ a1
        q_result[2 * i + 1] = a0
    sector[2248:2352] = q_result


# ---------------------------------------------------------------------------
# Sector I/O
# ---------------------------------------------------------------------------

def read_user_data(image: bytes, sector: int) -> bytes:
    """Read 2048 bytes of user data from a raw sector."""
    start = sector * SECTOR_SIZE + USER_OFFSET
    return image[start:start + USER_SIZE]


def write_user_data(image: bytearray, sector: int, data: bytes) -> None:
    """Write user data to a sector and recalculate EDC/ECC."""
    start = sector * SECTOR_SIZE
    user_start = start + USER_OFFSET
    image[user_start:user_start + len(data)] = data
    if len(data) < USER_SIZE:
        image[user_start + len(data):user_start + USER_SIZE] = b'\x00' * (USER_SIZE - len(data))
    raw_sector = bytearray(image[start:start + SECTOR_SIZE])
    rewrite_sector_edc_ecc(raw_sector)
    image[start:start + SECTOR_SIZE] = raw_sector


def extract_file_data(image: bytes, extent: int, size: int) -> bytes:
    """Extract a file from ISO by reading consecutive user sectors."""
    num_sectors = math.ceil(size / USER_SIZE)
    result = bytearray()
    for s in range(num_sectors):
        result.extend(read_user_data(image, extent + s))
    return bytes(result[:size])


def write_file_data(image: bytearray, extent: int, data: bytes, old_size: int) -> None:
    """Write file data to ISO at given extent, sector by sector."""
    num_sectors = math.ceil(len(data) / USER_SIZE)
    for s in range(num_sectors):
        chunk_start = s * USER_SIZE
        chunk_end = min(chunk_start + USER_SIZE, len(data))
        chunk = data[chunk_start:chunk_end]
        write_user_data(image, extent + s, chunk)


# ---------------------------------------------------------------------------
# ISO9660 directory parsing
# ---------------------------------------------------------------------------

class ISOEntry:
    def __init__(self, path, extent, size, is_dir, record_offset):
        self.path = path
        self.extent = extent
        self.size = size
        self.is_dir = is_dir
        self.record_offset = record_offset  # absolute byte offset of dir record in image


def parse_directory(image: bytes, extent: int, size: int, base: str = '') -> list:
    """Parse an ISO9660 directory and return list of ISOEntry."""
    entries = []
    remaining = size
    sector = extent

    while remaining > 0:
        data = read_user_data(image, sector)
        offset = 0

        while offset < USER_SIZE and offset < remaining:
            length = data[offset]
            if length == 0:
                break

            record = data[offset:offset + length]
            ext = struct.unpack_from('<I', record, 2)[0]
            sz = struct.unpack_from('<I', record, 10)[0]
            flags = record[25]
            name_len = record[32]
            name_bytes = record[33:33 + name_len]
            is_dir = bool(flags & 0x02)

            if name_bytes == b'\x00':
                name = '.'
            elif name_bytes == b'\x01':
                name = '..'
            else:
                name = name_bytes.decode('ascii', errors='replace')
                if ';' in name:
                    name = name.split(';', 1)[0]

            if name not in ('.', '..'):
                full_path = f'{base}/{name}' if base else name
                rec_offset = sector * SECTOR_SIZE + USER_OFFSET + offset
                entry = ISOEntry(full_path, ext, sz, is_dir, rec_offset)
                entries.append(entry)

                if is_dir:
                    entries.extend(parse_directory(image, ext, sz, full_path))

            offset += length

        sector += 1
        remaining -= USER_SIZE

    return entries


def build_file_index(image: bytes) -> dict:
    """Build a path → ISOEntry dict of all files in the ISO."""
    pvd = read_user_data(image, 16)
    root_len = pvd[156]
    root = pvd[156:156 + root_len]
    root_extent = struct.unpack_from('<I', root, 2)[0]
    root_size = struct.unpack_from('<I', root, 10)[0]

    entries = parse_directory(image, root_extent, root_size)
    return {e.path: e for e in entries}


def update_dir_record_size(image: bytearray, record_offset: int, new_size: int) -> None:
    """Update the size fields in an ISO9660 directory record."""
    image[record_offset + 10:record_offset + 14] = struct.pack('<I', new_size)
    image[record_offset + 14:record_offset + 18] = struct.pack('>I', new_size)
    # Recalculate EDC/ECC for the sector containing this record
    sector_start = (record_offset // SECTOR_SIZE) * SECTOR_SIZE
    raw_sector = bytearray(image[sector_start:sector_start + SECTOR_SIZE])
    rewrite_sector_edc_ecc(raw_sector)
    image[sector_start:sector_start + SECTOR_SIZE] = raw_sector


def update_dir_record_extent(image: bytearray, record_offset: int,
                              new_extent: int, new_size: int) -> None:
    """Update both extent and size in an ISO9660 directory record."""
    image[record_offset + 2:record_offset + 6] = struct.pack('<I', new_extent)
    image[record_offset + 6:record_offset + 10] = struct.pack('>I', new_extent)
    image[record_offset + 10:record_offset + 14] = struct.pack('<I', new_size)
    image[record_offset + 14:record_offset + 18] = struct.pack('>I', new_size)
    sector_start = (record_offset // SECTOR_SIZE) * SECTOR_SIZE
    raw_sector = bytearray(image[sector_start:sector_start + SECTOR_SIZE])
    rewrite_sector_edc_ecc(raw_sector)
    image[sector_start:sector_start + SECTOR_SIZE] = raw_sector


def patch_file_in_iso(image: bytearray, entry: ISOEntry, new_data: bytes) -> int:
    """Patch a file in the ISO image.

    If new data fits in existing space, writes in-place.
    If larger, appends at end of image and repoints.

    Returns number of sectors added (0 if in-place).
    """
    old_sectors = math.ceil(entry.size / USER_SIZE)
    new_sectors = math.ceil(len(new_data) / USER_SIZE)

    if new_sectors <= old_sectors:
        # Fits in place
        write_file_data(image, entry.extent, new_data, entry.size)
        update_dir_record_size(image, entry.record_offset, len(new_data))
        return 0
    else:
        # Need more space - append at end
        current_sectors = len(image) // SECTOR_SIZE
        new_extent = current_sectors

        # Extend image with proper sector structure
        for s in range(new_sectors):
            # Create a new sector with sync pattern and header
            new_sector = bytearray(SECTOR_SIZE)
            # Sync pattern
            new_sector[0:12] = b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00'
            # Header: MSF address with standard 150-frame (2-second) lead-in offset
            total_sector = new_extent + s + 150
            minutes = total_sector // (75 * 60)
            seconds = (total_sector // 75) % 60
            frames = total_sector % 75
            new_sector[12] = (minutes // 10) * 16 + (minutes % 10)  # BCD
            new_sector[13] = (seconds // 10) * 16 + (seconds % 10)
            new_sector[14] = (frames // 10) * 16 + (frames % 10)
            new_sector[15] = 1  # Mode 1

            # User data
            chunk_start = s * USER_SIZE
            chunk_end = min(chunk_start + USER_SIZE, len(new_data))
            chunk = new_data[chunk_start:chunk_end]
            new_sector[USER_OFFSET:USER_OFFSET + len(chunk)] = chunk

            rewrite_sector_edc_ecc(new_sector)
            image.extend(new_sector)

        update_dir_record_extent(image, entry.record_offset, new_extent, len(new_data))
        return new_sectors


def _make_sector(sector_num: int, user_data: bytes) -> bytearray:
    """Create a Mode 1/2352 sector with sync, MSF header, user data, EDC/ECC."""
    sector = bytearray(SECTOR_SIZE)
    sector[0:12] = b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00'
    abs_sector = sector_num + 150  # 2-second lead-in offset
    m = abs_sector // (75 * 60)
    s = (abs_sector // 75) % 60
    f = abs_sector % 75
    sector[12] = (m // 10) * 16 + (m % 10)  # BCD
    sector[13] = (s // 10) * 16 + (s % 10)
    sector[14] = (f // 10) * 16 + (f % 10)
    sector[15] = 1  # Mode 1
    sector[USER_OFFSET:USER_OFFSET + len(user_data)] = user_data
    rewrite_sector_edc_ecc(sector)
    return sector


def rebuild_iso_inorder(image: bytearray, file_index: dict,
                        target_path: str, new_data: bytes) -> bytearray:
    """Rebuild ISO with a larger file in its original position.

    Single-file convenience wrapper around rebuild_iso_batch.
    """
    return rebuild_iso_batch(image, file_index, [(target_path, new_data)])


def rebuild_iso_batch(image: bytearray, file_index: dict,
                      patches: list) -> bytearray:
    """Rebuild ISO applying multiple patches, shifting subsequent files as
    needed per grown file.

    patches: list of (path, new_data) tuples. Processed in ascending extent
    order; after each grown file, downstream extents are recomputed and the
    in-memory file_index is updated.

    For each target:
      - if new_data <= old sectors: patched in place, no shift
      - if new_data > old sectors: inserted at original extent, all sectors
        beyond it shifted +delta, MSF headers rewritten, dir records updated

    This works because (per audit): no SH-2 binary in Langrisser 3 has
    hardcoded file LBAs. All file access is via ISO9660 directory lookup,
    so updating dir records is sufficient.

    Returns a new image bytearray.
    """
    result = bytearray(image)
    # Working copy of file_index we mutate as shifts accumulate
    work_index = {p: ISOEntry(e.path, e.extent, e.size, e.is_dir, e.record_offset)
                  for p, e in file_index.items()}

    # Sort targets by current (possibly-shifted) extent ascending
    def current_extent(path):
        return work_index[path].extent

    pending = sorted(patches, key=lambda p: current_extent(p[0]))
    total_delta = 0
    shifted_total = 0

    for target_path, new_data in pending:
        target = work_index[target_path]
        old_sectors = math.ceil(target.size / USER_SIZE)
        new_sectors = math.ceil(len(new_data) / USER_SIZE)
        delta = new_sectors - old_sectors

        if delta <= 0:
            # Fits in place
            write_file_data(result, target.extent, new_data, target.size)
            update_dir_record_size(result, target.record_offset, len(new_data))
            target.size = len(new_data)
            continue

        shift_start = target.extent + old_sectors
        total_old_sectors = len(result) // SECTOR_SIZE

        # Rebuild: keep sectors [0..target.extent-1], write new data at
        # target.extent, then shift sectors [shift_start..end] by +delta
        prefix = bytes(result[:target.extent * SECTOR_SIZE])
        new_result = bytearray(prefix)

        for s in range(new_sectors):
            chunk_start = s * USER_SIZE
            chunk_end = min(chunk_start + USER_SIZE, len(new_data))
            new_result.extend(_make_sector(
                target.extent + s, new_data[chunk_start:chunk_end]))

        for old_idx in range(shift_start, total_old_sectors):
            old_start = old_idx * SECTOR_SIZE
            sector = bytearray(result[old_start:old_start + SECTOR_SIZE])
            new_idx = old_idx + delta
            abs_sector = new_idx + 150
            m = abs_sector // (75 * 60)
            s = (abs_sector // 75) % 60
            f = abs_sector % 75
            sector[12] = (m // 10) * 16 + (m % 10)
            sector[13] = (s // 10) * 16 + (s % 10)
            sector[14] = (f // 10) * 16 + (f % 10)
            rewrite_sector_edc_ecc(sector)
            new_result.extend(sector)

        # Update target dir record: size only (extent unchanged)
        update_dir_record_size(new_result, target.record_offset, len(new_data))
        target.size = len(new_data)

        # All entries with extent >= shift_start: shift +delta.
        # Includes Track 2 ADPCM dir records (Track 1/2 LBA coupling).
        shifted = 0
        for path, entry in work_index.items():
            if entry.extent >= shift_start:
                entry.extent += delta
                update_dir_record_extent(
                    new_result, entry.record_offset, entry.extent, entry.size)
                shifted += 1

        result = new_result
        total_delta += delta
        shifted_total += shifted
        print(f'  +{delta}s shift for {target_path}: '
              f'{shifted} entries repointed')

    if total_delta:
        print(f'  ISO rebuild batch: +{total_delta} total sectors, '
              f'{shifted_total} cumulative entry updates')
    return result


def assemble_cd_image(track01_path: Path, jp_dir: Path, output_cue: Path) -> None:
    """Assemble final CD image: patched track01 + audio tracks from JP source."""
    output_dir = output_cue.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Flat layout (cue + all track*.bin in same directory). Beetle Saturn
    # (libretro) does not follow subdirectories in cue FILE entries, so
    # keeping everything sibling-level is what works across Ymir, Mednafen,
    # SSF, Yabause and Beetle Saturn alike.
    import shutil
    dst_track01 = output_dir / 'track01.bin'
    if track01_path.resolve() != dst_track01.resolve():
        shutil.copy2(track01_path, dst_track01)

    # Copy audio tracks from Japanese source
    for i in range(2, 23):
        jp_track = jp_dir / f'Langrisser III (Japan) (3M) (Track {i:02d}).bin'
        if jp_track.exists():
            shutil.copy2(jp_track, output_dir / f'track{i:02d}.bin')

    # Generate CUE sheet matching original JP disc layout, with FILE
    # entries pointing to siblings of the .cue (no subdirectory).
    cue_lines = ['CATALOG 0000000000000']
    cue_lines.append('FILE "track01.bin" BINARY')
    cue_lines.append('  TRACK 01 MODE1/2352')
    cue_lines.append('    INDEX 01 00:00:00')

    if (output_dir / 'track02.bin').exists():
        cue_lines.append('FILE "track02.bin" BINARY')
        cue_lines.append('  TRACK 02 MODE2/2352')
        cue_lines.append('    INDEX 00 00:00:00')
        cue_lines.append('    INDEX 01 00:03:00')

    for i in range(3, 23):
        if (output_dir / f'track{i:02d}.bin').exists():
            cue_lines.append(f'FILE "track{i:02d}.bin" BINARY')
            cue_lines.append(f'  TRACK {i:02d} AUDIO')
            cue_lines.append('    INDEX 00 00:00:00')
            cue_lines.append('    INDEX 01 00:02:00')

    output_cue.write_text('\n'.join(cue_lines) + '\n')
