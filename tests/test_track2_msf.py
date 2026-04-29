"""Regression tests for the Track 2 MSF rewrite that keeps Beetle Saturn
playing XA voice clips after Track 1 has grown.

The bug this guards against:
  - When Track 1 of the patched ISO is larger than the JP original, Track
    2 (MODE 2 ADPCM voice streams) shifts forward on disc.
  - Each Track 2 sector contains a BCD MSF header at bytes 12-14 that
    states the sector's own LBA. JP track02.bin ships with MSF values
    starting at LBA 32780 (the JP Track 2 start).
  - Beetle Saturn's CD block (mednafen/ss/cdb.cpp::TestFilterCond) reads
    that in-sector MSF and rejects sectors that fall outside the
    requested file's FAD range. With a stale MSF every voice sector is
    rejected and character voices go silent.
  - Ymir, mednafen and Saroo (real hardware) resolve XA via the dir
    record + cue TOC and don't notice the MSF mismatch.

These tests pin down the behaviour of `_shift_track2_msf` and verify the
end-to-end build output keeps Track 2 MSF aligned with its physical
position.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'tools'))

from iso_tools import (  # noqa: E402
    SECTOR_SIZE,
    JP_TRACK01_SECTORS,
    _shift_track2_msf,
)


SS = SECTOR_SIZE  # 2352


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bcd(n: int) -> int:
    """Pack 0..99 into BCD (e.g. 32 -> 0x32)."""
    return (n // 10) * 16 + (n % 10)


def _from_bcd(b: int) -> int:
    return (b >> 4) * 10 + (b & 0xF)


def _make_mode2_sector(lba: int) -> bytes:
    """Build a synthetic MODE 2 sector whose internal MSF claims `lba`.

    Layout matches a real CD-ROM MODE 2 raw sector:
      0..11  sync (00 FF*10 00)
      12..14 MSF in BCD (lba + 150 lead-in)
      15     mode byte = 0x02
      16..2351 user data + subheader/EDC/ECC (zeros for our purposes)
    """
    s = bytearray(2352)
    s[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
    abs_lba = lba + 150
    minutes = abs_lba // (75 * 60)
    seconds = (abs_lba // 75) % 60
    frames = abs_lba % 75
    s[12] = _bcd(minutes)
    s[13] = _bcd(seconds)
    s[14] = _bcd(frames)
    s[15] = 0x02
    # Put a recognizable signature in user data so we can tell sectors apart
    s[16:24] = struct.pack('<Q', lba)
    return bytes(s)


def _read_msf_lba(sector: bytes) -> int:
    """Decode bytes 12-14 BCD MSF back into an absolute LBA (sans +150)."""
    m = _from_bcd(sector[12])
    s = _from_bcd(sector[13])
    f = _from_bcd(sector[14])
    return m * 60 * 75 + s * 75 + f - 150


def _build_track2(start_lba: int, num_sectors: int) -> bytes:
    return b''.join(
        _make_mode2_sector(start_lba + i) for i in range(num_sectors)
    )


# ---------------------------------------------------------------------------
# Unit tests for _shift_track2_msf
# ---------------------------------------------------------------------------

class TestShiftTrack2MSF:

    def test_zero_delta_returns_input_unchanged(self):
        """If the new Track 2 start equals the JP original, no work is needed."""
        track2 = _build_track2(JP_TRACK01_SECTORS, 50)
        out = _shift_track2_msf(track2, JP_TRACK01_SECTORS)
        assert out == track2

    def test_positive_delta_shifts_every_sector(self):
        """All sector MSFs advance by the delta; LBAs become contiguous from new_start."""
        new_start = JP_TRACK01_SECTORS + 64
        track2 = _build_track2(JP_TRACK01_SECTORS, 200)
        out = _shift_track2_msf(track2, new_start)

        for i in range(200):
            sector = out[i * SS:(i + 1) * SS]
            assert _read_msf_lba(sector) == new_start + i, (
                f'sector {i}: expected MSF {new_start + i}, '
                f'got {_read_msf_lba(sector)}'
            )

    def test_realistic_voice_track_size(self):
        """Match the real JP Track 2 size (56,317 sectors) and shift by +64."""
        new_start = JP_TRACK01_SECTORS + 64
        track2 = _build_track2(JP_TRACK01_SECTORS, 56_317)
        out = _shift_track2_msf(track2, new_start)

        # Spot check first, middle, and last
        for idx in (0, 28_000, 56_316):
            sector = out[idx * SS:(idx + 1) * SS]
            assert _read_msf_lba(sector) == new_start + idx

    def test_only_msf_bytes_change(self):
        """Bytes outside 12..14 of every sector must be left alone."""
        new_start = JP_TRACK01_SECTORS + 16
        track2 = _build_track2(JP_TRACK01_SECTORS, 10)
        out = _shift_track2_msf(track2, new_start)

        for i in range(10):
            base = i * SS
            assert out[base:base + 12]    == track2[base:base + 12], 'sync changed'
            assert out[base + 15:base + SS] == track2[base + 15:base + SS], (
                'mode byte or user data changed'
            )

    def test_output_size_unchanged(self):
        """The shift must never resize the track."""
        track2 = _build_track2(JP_TRACK01_SECTORS, 1234)
        out = _shift_track2_msf(track2, JP_TRACK01_SECTORS + 999)
        assert len(out) == len(track2)

    def test_jp_track01_sectors_constant(self):
        """If the JP Track 1 size constant ever drifts the rest of the math
        breaks silently. Pin it down."""
        assert JP_TRACK01_SECTORS == 32780


# ---------------------------------------------------------------------------
# Integration test against the actual build output
# ---------------------------------------------------------------------------

BUILD_TRACK01 = PROJECT_ROOT / 'build' / 'track01.bin'
BUILD_TRACK02 = PROJECT_ROOT / 'build' / 'track02.bin'

@pytest.mark.skipif(
    not (BUILD_TRACK01.exists() and BUILD_TRACK02.exists()),
    reason='build/track01.bin or build/track02.bin not present (run build.py first)',
)
class TestBuildTrack2MSFAligned:
    """End-to-end: after build.py runs, build/track02.bin must have MSF
    aligned with its physical position (= end of Track 1)."""

    @pytest.fixture(scope='class')
    def track01_sectors(self):
        return BUILD_TRACK01.stat().st_size // SS

    @pytest.fixture(scope='class')
    def track02_data(self):
        return BUILD_TRACK02.read_bytes()

    def test_track02_first_sector_matches_track1_end(
        self, track01_sectors, track02_data,
    ):
        """First Track 2 sector's MSF must equal the sector index where
        Track 2 begins on the assembled disc."""
        first = track02_data[:SS]
        msf_lba = _read_msf_lba(first)
        assert msf_lba == track01_sectors, (
            f'Track 2 first sector MSF says LBA {msf_lba} but Track 2 '
            f'starts at sector {track01_sectors}. This breaks Beetle '
            f'Saturn voice playback.'
        )

    def test_track02_last_sector_msf_consistent(
        self, track01_sectors, track02_data,
    ):
        """Last Track 2 sector's MSF must equal Track 1 end + (track2 length - 1)."""
        num = len(track02_data) // SS
        last = track02_data[(num - 1) * SS:num * SS]
        expected = track01_sectors + num - 1
        assert _read_msf_lba(last) == expected

    def test_track02_msf_strictly_monotonic(
        self, track01_sectors, track02_data,
    ):
        """Every consecutive pair of sectors must have MSF increase by 1.
        Sample 100 evenly-spaced positions to keep the test fast."""
        num = len(track02_data) // SS
        step = max(1, num // 100)
        prev_lba = None
        for i in range(0, num, step):
            sector = track02_data[i * SS:(i + 1) * SS]
            lba = _read_msf_lba(sector)
            assert lba == track01_sectors + i, (
                f'sector {i}: MSF says {lba}, expected {track01_sectors + i}'
            )
            if prev_lba is not None:
                assert lba > prev_lba
            prev_lba = lba

    def test_track02_size_matches_jp_original(self, track02_data):
        """Track 2 length must not change — only the MSF inside each sector
        is rewritten. JP Track 2 is exactly 56,317 sectors."""
        assert len(track02_data) == 56_317 * SS
