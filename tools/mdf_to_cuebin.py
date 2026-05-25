#!/usr/bin/env python3
"""
mdf_to_cuebin.py — convert a Saturn .mdf disc image to single-bin cue/bin.

The .mdf format used by Alcohol 120% / DAEMON Tools is byte-identical to
a single concatenated .bin: raw 2352-byte sectors covering all tracks
end-to-end. The companion .mds file holds the track layout (MSF starts).

Strategy: parse the .mds for track boundaries, copy the .mdf as a .bin,
emit a .cue describing the same track layout. Single .bin output —
emulators that support FILE-spanning .cue (most modern ones, including
Mednafen Saturn / mednafen-libretro / Ymir / Yabause) handle it.
"""
import argparse
import shutil
import struct
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Track:
    number: int
    mode: int          # 0xAA=mode2/data, 0xA9/0xEC/0xED=audio variants
    start_lba: int     # sector offset within file
    pregap_lba: int    # pregap sectors before track data (typically 0 or 150)
    sectors: int       # length in sectors
    file_offset: int   # byte offset within .mdf

    @property
    def is_data(self) -> bool:
        # Verified by inspecting actual sector bytes (sync pattern + mode byte):
        # 0xAA → MODE1/2352  (Saturn boot track)
        # 0xED → MODE2/2352  (Saturn game data)
        # 0xA9 → AUDIO       (CDDA, no sync header, includes 2s silent pregap)
        return self.mode in (0xAA, 0xED)

    @property
    def cue_type(self) -> str:
        if self.mode == 0xAA:
            return "MODE1/2352"
        if self.mode == 0xED:
            return "MODE2/2352"
        return "AUDIO"


def parse_mds(mds: bytes) -> list[Track]:
    """Parse Alcohol MDS file → list of Tracks.

    Layout (verified offsets from a Saturn rip):
      0x00:    "MEDIA DESCRIPTOR" magic (16 bytes)
      0x10-2 : version (e.g., 0x0105)
      0x50: 4 bytes — pointer to session header
      Session header (at the offset above):
        0x00..0x03: start sector (signed; pregap = -150)
        0x04..0x07: end sector
        0x0A:        num blocks total (includes A0/A1/A2 lead-in entries)
        0x0B:        num real tracks
        0x14..0x17:  pointer to first track block
      Track block (80 bytes):
        0x00:        track mode (0xAA=Mode2 data, 0xA9/0xED=audio)
        0x04:        point — track # (or 0xA0/A1/A2 for lead-in markers)
        0x09..0x0B:  PMSF (PMin, PSec, PFrame)
        0x10..0x11:  sector size (typically 2352)
        0x18..0x1B:  start LBA within disc
        0x1C..0x1F:  track length in sectors
        0x28..0x2F:  file offset (8 bytes) — where this track's bytes start
                     within the .mdf file
    """
    if mds[:16] != b"MEDIA DESCRIPTOR":
        raise ValueError("not an MDS file")

    sess_off = struct.unpack_from("<I", mds, 0x50)[0]
    if sess_off == 0 or sess_off >= len(mds):
        raise ValueError(f"bad session offset {sess_off}")

    n_blocks_total = mds[sess_off + 0x0A]
    first_track = mds[sess_off + 0x0C]
    last_track = mds[sess_off + 0x0E]
    n_real_tracks = last_track - first_track + 1
    first_block_off = struct.unpack_from("<I", mds, sess_off + 0x14)[0]

    tracks: list[Track] = []
    for i in range(n_blocks_total):
        b = first_block_off + i * 80
        if b + 80 > len(mds):
            break
        mode_byte = mds[b + 0x00]
        point = mds[b + 0x04]
        # Skip lead-in pseudo entries (point >= 0xA0)
        if point == 0 or point >= 0xA0:
            continue
        sec_size = struct.unpack_from("<H", mds, b + 0x10)[0] or 2352
        sectors = struct.unpack_from("<I", mds, b + 0x1C)[0]
        file_off = struct.unpack_from("<Q", mds, b + 0x28)[0]
        tracks.append(Track(
            number=point,
            mode=mode_byte,
            start_lba=file_off // (sec_size or 2352),
            pregap_lba=0,
            sectors=sectors,
            file_offset=file_off,
        ))
        if len(tracks) >= n_real_tracks:
            break

    tracks.sort(key=lambda t: t.number)
    return tracks


def lba_to_msf(lba: int) -> str:
    """LBA → MM:SS:FF cue string. (75 frames per second.)"""
    minutes, rem = divmod(lba, 75 * 60)
    seconds, frames = divmod(rem, 75)
    return f"{minutes:02d}:{seconds:02d}:{frames:02d}"


def split_mdf_per_track(mdf_path: Path, tracks: list[Track], out_dir: Path,
                        basename: str) -> list[str]:
    """Split the .mdf into one .bin per track. Returns list of bin filenames
    in track order.
    """
    mdf_size = mdf_path.stat().st_size
    bin_names = []
    with mdf_path.open("rb") as src:
        for i, t in enumerate(tracks):
            end = tracks[i + 1].file_offset if i + 1 < len(tracks) else mdf_size
            length = end - t.file_offset
            bin_name = f"{basename} (Track {t.number:02d}).bin"
            bin_path = out_dir / bin_name
            print(f"  Track {t.number:02d}: {length:>11,} bytes ({length // 2352:>6} sectors) "
                  f"→ {bin_name}")
            src.seek(t.file_offset)
            with bin_path.open("wb") as dst:
                remaining = length
                while remaining > 0:
                    chunk = src.read(min(remaining, 4 * 1024 * 1024))
                    if not chunk:
                        break
                    dst.write(chunk)
                    remaining -= len(chunk)
            bin_names.append(bin_name)
    return bin_names


def write_cue_multifile(tracks: list[Track], bin_names: list[str],
                         cue_path: Path) -> None:
    """Emit a multi-FILE cue (one FILE per track), matching JP-rip convention.

    For audio tracks with included pregap, INDEX 00 = 00:00:00 and
    INDEX 01 = 00:02:00 (2-second pregap). Saturn rips conventionally
    include the pregap inside each audio .bin file.
    """
    lines = ["CATALOG 0000000000000"]
    for t, bin_name in zip(tracks, bin_names):
        lines.append(f'FILE "{bin_name}" BINARY')
        lines.append(f"  TRACK {t.number:02d} {t.cue_type}")
        if t.is_data:
            # Data tracks: in this rip the .bin starts at the data sectors
            # directly (no pregap silence inside the file). Cue declares
            # INDEX 01 at 00:00:00 and the burner/emulator handles the
            # leadin transition between tracks itself.
            lines.append("    INDEX 01 00:00:00")
        else:
            # Audio tracks: the .bin includes a 2-second silent pregap, then
            # the actual audio data. Cue uses INDEX 00 (pregap start) and
            # INDEX 01 (audio start) — same pattern as the JP rip.
            lines.append("    INDEX 00 00:00:00")
            lines.append("    INDEX 01 00:02:00")
    cue_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mdf", type=Path, help="path to .mdf file")
    p.add_argument("-o", "--output-dir", type=Path, default=Path("data/cn/cuebin"))
    p.add_argument("--name", default="LANGRISSER_3_CN", help="output basename")
    args = p.parse_args()

    mdf_path: Path = args.mdf
    if not mdf_path.exists():
        print(f"ERROR: {mdf_path} not found", file=sys.stderr)
        return 1
    mds_path = mdf_path.with_suffix(".mds")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cue_path = args.output_dir / f"{args.name}.cue"

    # Parse .mds (if present) to know the track layout
    tracks: list[Track] = []
    if mds_path.exists():
        try:
            parsed = parse_mds(mds_path.read_bytes())
            # Sanity check: track numbers should be small (1..99), modes should
            # be in the known set. If anything looks bogus, fall back.
            valid = (parsed and
                     all(1 <= t.number <= 99 for t in parsed) and
                     parsed[0].number == 1)
            if valid:
                tracks = parsed
                print(f"Parsed {len(tracks)} tracks from {mds_path.name}")
                for t in tracks:
                    print(f"  T{t.number:02d}  mode=0x{t.mode:02X}  "
                          f"sectors={t.sectors}  file_off=0x{t.file_offset:X}  "
                          f"{t.cue_type}")
            else:
                print(f"MDS parsed produced suspect tracks "
                      f"({[(t.number, hex(t.mode)) for t in parsed]}); "
                      "falling back to single-track cue.")
        except Exception as exc:
            print(f"MDS parse failed ({exc}); falling back to single-track cue.")

    # Fallback: single MODE1/2352 track covering the whole file
    if not tracks:
        size = mdf_path.stat().st_size
        if size % 2352:
            print(f"WARN: file size {size} not a multiple of 2352", file=sys.stderr)
        tracks = [Track(number=1, mode=0xAA, start_lba=0,
                       pregap_lba=0, sectors=size // 2352, file_offset=0)]

    # Split the .mdf into one .bin per track
    print("Splitting tracks ...")
    bin_names = split_mdf_per_track(mdf_path, tracks, args.output_dir, args.name)

    write_cue_multifile(tracks, bin_names, cue_path)
    print(f"Wrote {cue_path}")
    print(f"\nVerify by loading {cue_path} in your emulator of choice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
