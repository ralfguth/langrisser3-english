"""The patch can build the English-subtitled opening from the user's own disc.

Red state (v0.7.0): the FMV encoder lived only in a separate, unpublished
checkout (saturn-cinepak-muxer). build.py could only INJECT a prebuilt
`assets/movie/LANG.CPK`, which is game-derived data and therefore not in this
repo — so anyone building from source got the Japanese opening and had no way
to produce the English one (issue #6). tools/movie_tools.py did not exist here
and build.py had no flag to encode.

Green: `python3 build.py --encode-movie` extracts LANG/LANG.CPK from the user's
own disc, burns the committed subtitle track into it, and injects the result.
The disc is the only video source needed; ffmpeg is the only extra tool.
"""
import importlib
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

SRT = REPO / "assets" / "movie" / "opening_en.srt"


@pytest.fixture
def movie_tools():
    return importlib.import_module("movie_tools")


def test_subtitle_track_ships_in_this_repo():
    """The .srt is our own text (no game data), so it MUST be committed — it is
    the one piece a user cannot regenerate from their disc."""
    assert SRT.exists(), f"missing subtitle track: {SRT}"
    text = SRT.read_text(encoding="utf-8")
    assert "-->" in text, "not an SRT (no cue timings)"
    assert text.strip(), "subtitle track is empty"


def test_encoder_is_vendored_with_its_font(movie_tools):
    """The encoder ships inside the patch (issue #6) instead of living in a
    separate checkout the user does not have."""
    assert hasattr(movie_tools, "build_movie_cpk")
    assert hasattr(movie_tools, "encode_from_disc")
    assert movie_tools.FONTS_DIR == REPO / "data" / "fonts"
    assert (movie_tools.FONTS_DIR / "Mx437_CL_EagleIII_8x16.ttf").exists()


def test_encode_from_disc_uses_the_discs_own_movie(movie_tools, tmp_path, monkeypatch):
    """The whole point: the video SOURCE is the CPK read off the user's disc —
    not an external upscale they do not have. Audio still comes from the same
    JP CPK, so the Japanese voice track is preserved verbatim."""
    jp = tmp_path / "LANG_JP.CPK"
    jp.write_bytes(b"FILM" + b"\x00" * 64)
    out = tmp_path / "LANG.CPK"
    seen = {}

    def fake_build(source, srt, jp_cpk, dest, **kw):
        seen.update(source=Path(source), srt=Path(srt),
                    jp_cpk=Path(jp_cpk), dest=Path(dest), kw=kw)
        Path(dest).write_bytes(b"FILM")
        return Path(dest)

    monkeypatch.setattr(movie_tools, "build_movie_cpk", fake_build)
    monkeypatch.setattr(movie_tools.shutil, "which", lambda name: "/usr/bin/" + name)

    result = movie_tools.encode_from_disc(jp, out)
    assert result == out
    assert seen["source"] == jp, "video source must be the disc's own CPK"
    assert seen["jp_cpk"] == jp, "audio must come from the disc's own CPK"
    assert seen["srt"] == SRT, "subtitles must default to the committed track"


def test_encode_from_disc_reports_missing_ffmpeg_clearly(movie_tools, tmp_path,
                                                         monkeypatch):
    """A user without ffmpeg must get one readable sentence, not a raw
    FileNotFoundError from subprocess halfway through the build."""
    monkeypatch.setattr(movie_tools.shutil, "which", lambda name: None)
    jp = tmp_path / "LANG_JP.CPK"
    jp.write_bytes(b"FILM")
    with pytest.raises(RuntimeError, match="(?i)ffmpeg"):
        movie_tools.encode_from_disc(jp, tmp_path / "out.CPK")


def test_build_exposes_the_encode_movie_flag():
    """`python3 build.py --encode-movie` is the documented entry point."""
    build = importlib.import_module("build")
    parser = build.build_arg_parser()
    args = parser.parse_args([])
    assert args.encode_movie is False, "encoding must stay opt-in (needs ffmpeg)"
    args = parser.parse_args(["--encode-movie"])
    assert args.encode_movie is True
    # A better master (e.g. an upscale) may override the disc as the source.
    args = parser.parse_args(["--encode-movie", "--movie-source", "up.mp4"])
    assert Path(args.movie_source) == Path("up.mp4")


# --- real-artifact gate (slow: a full 84s Cinepak encode) ---------------------

HW_SAFE_MAX = 22_500_000     # 2x CD read budget over 84s, with margin
JP_DIR_ENV = "LANG3_JP_DIR"


def _stab(data):
    i = data.find(b"STAB")
    timebase = struct.unpack(">I", data[i + 8:i + 12])[0]
    nsamp = struct.unpack(">I", data[i + 12:i + 16])[0]
    ent = i + 16
    return timebase, [struct.unpack(">IIII", data[ent + k * 16:ent + k * 16 + 16])
                      for k in range(nsamp)]



def test_encoded_cpk_is_saturn_shaped(movie_tools, tmp_path):
    """End-to-end on the REAL disc: encode from the user's own LANG.CPK and pin
    the hardware-critical shape (FILM 1.08, 2 strips, 4-byte alignment, JP audio,
    under the CD read budget). Opt in with LANG3_SLOW_TESTS=1 — it runs a full
    Cinepak encode (minutes)."""
    import os
    if not os.environ.get("LANG3_SLOW_TESTS"):
        pytest.skip("slow encode — set LANG3_SLOW_TESTS=1 to run")
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    from iso_tools import build_file_index, extract_file_data

    jp_dir = Path(os.environ.get(
        JP_DIR_ENV,
        "/home/ralf/Jogos/emulacao/romsets/sega-saturn/cue-bin/Langrisser III (Japan)"))
    tracks = sorted(jp_dir.glob("*rack*01*.bin"))
    if not tracks:
        pytest.skip(f"JP track01 not found under {jp_dir}")
    img = bytearray(tracks[0].read_bytes())
    idx = build_file_index(img)
    entry = idx["LANG/LANG.CPK"]
    jp_cpk = tmp_path / "LANG_JP.CPK"
    jp_cpk.write_bytes(extract_file_data(img, entry.extent, entry.size))

    out = movie_tools.encode_from_disc(jp_cpk, tmp_path / "LANG.CPK", quiet=True)
    data = out.read_bytes()

    assert data[:4] == b"FILM" and data[8:12] == b"1.08"
    timebase, samples = _stab(data)
    assert timebase == 30
    assert samples[0][2] == 0xFFFFFFFF, "first sample must be audio (JP priming)"
    hdr = struct.unpack(">I", data[4:8])[0]
    strips, misaligned = set(), 0
    for off, sz, info1, _info2 in samples:
        if info1 == 0xFFFFFFFF:
            continue
        frame = data[hdr + off:hdr + off + sz]
        strips.add(struct.unpack(">H", frame[8:10])[0])
        if len(frame) % 4:
            misaligned += 1
    assert strips == {2}, f"strip counts {sorted(strips)}"
    assert misaligned == 0, f"{misaligned} misaligned frames — SH-2 will fault"
    assert len(data) <= HW_SAFE_MAX, f"{len(data)} bytes over the CD read budget"

    def audio_stream(path):
        return subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name,sample_rate,channels",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()

    assert audio_stream(out) == audio_stream(jp_cpk), "JP voice track must survive"
