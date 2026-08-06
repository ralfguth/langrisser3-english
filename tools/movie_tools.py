#!/usr/bin/env python3
"""Build a Sega Saturn FMV (Sega FILM / CPK) from a modern, subtitled source.

The opening movie ships on disc as ``LANG/LANG.CPK``. The Japanese original is a
Sega FILM 1.08 container:

    video : Cinepak, 320x224, 15 fps, 24bpp
    audio : 8-bit signed PCM, 22050 Hz, mono (the Japanese voice track)

We rebuild it from an upscaled source clip plus an English ``.srt`` while keeping
every one of those facts intact, so the existing Saturn Cinepak player accepts it
unchanged. The English subtitles are *burned in* at the final 320x224 resolution
(the Saturn cannot show more); the upscaled source only buys a cleaner downscale.

Hardware constraint
-------------------
The binding limit is NOT disc capacity (the whole disc is ~half a CD) but the
Saturn's **2x CD-ROM read speed (~2.46 Mbit/s)**: the CPK is streamed off the
disc, so its average bitrate must stay under that or playback starves (audio
dropouts, frozen frames) on real hardware. We target ~2.0 Mbit/s total.

This module is language-agnostic: point it at any source + .srt to localise the
opening for another language.
"""
from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# --- engine-fixed facts (do not change without re-checking the Saturn player) --
WIDTH = 320
HEIGHT = 224
FPS = 15
DURATION = 84.0                  # seconds; matches the JP audio exactly
AUDIO_RATE = 22050
AUDIO_CH = 1

# Subtitles use the SAME face as the langrisser3-english in-game text — Eagle III
# (Mx437 CL EagleIII 8x16, bundled here in fonts/) — so the opening reads
# consistently with the rest of that localisation. It is a pixel font built on a
# 16px cell. To render it PIXEL-EXACT we burn it through a generated .ass whose
# PlayResY equals the frame height (224): then FontSize 16 == 16 real px == 8x16
# glyphs with no scaling blur. (Burning a raw .srt lets libass default to
# PlayResY 288, which scales the font to ~12.4px and softens it.)
FONTS_DIR = REPO_ROOT / "data" / "fonts"
SUB_FONT = "Mx437 CL EagleIII 8x16"
SUB_FONT_SIZE = 16               # == cell height -> pixel-exact at PlayResY=HEIGHT
SUB_MARGIN_V = 22                # px from the bottom (raised ~one line from 6)

# Hardware-safe video bitrate. NOTE: the ffmpeg cinepak encoder is fixed-quality
# and effectively ignores -b:v; kept only as a nominal hint. Real quality comes
# from the clean upscaled source; size is governed by MATCH_STRIPS.
DEFAULT_VIDEO_BITRATE = "1800k"

# --- Saturn-exact container ---------------------------------------------------
# The ffmpeg 'film_cpk' muxer writes a version-1.09 header, timebase=fps, a
# video-FIRST sample order, and adaptive 1..3 Cinepak strips. The Saturn opening
# player REJECTS that on real hardware (black screen / popping audio — confirmed
# on Saroo). The JP original is version 1.08, timebase 30 (dur=2 per 15fps
# frame), audio-FIRST priming, and exactly 2 strips on every frame. So we encode
# 2-strip video with ffmpeg, then re-wrap our frames into a byte-structure that
# clones the JP container (audio reused verbatim) via _remux_like_jp().
MATCH_STRIPS = 2
FILM_HEADER_BYTES = 16
FDSC_BYTES = 32
STAB_HEADER_BYTES = 16
SAMPLE_BYTES = 16
JP_TIMEBASE = 30                 # FILM timebase; each 15fps video frame has dur=2
AUDIO_SYNC = 0xFFFFFFFF          # info1 marker for an audio sample
NOT_SYNC_FLAG = 0x80000000       # info1 bit31 set => video delta frame (not keyframe)


def ff_filter_path(path) -> str:
    """Quote a filesystem path for use INSIDE an ffmpeg filtergraph.

    A filtergraph parses ':' as an option separator and '\\' as an escape, so a
    Windows path (C:\\Users\\me\\fonts) has to become C\\:/Users/me/fonts.
    POSIX paths pass through unchanged.
    """
    return str(path).replace("\\", "/").replace(":", r"\:")


def subtitles_filter(ass_name: str, fontsdir) -> str:
    """The `subtitles=` filter. The .ass is referenced by bare filename (ffmpeg
    runs with cwd set to its directory), the fonts dir cannot be."""
    return f"subtitles={ass_name}:fontsdir={ff_filter_path(fontsdir)}"


def _split_samples(data: bytes):
    """Return (data_section_offset, [(off, size, info1, info2), ...]) for a FILM."""
    hdr_size = struct.unpack(">I", data[4:8])[0]
    i = data.find(b"STAB")
    nsamp = struct.unpack(">I", data[i + 12:i + 16])[0]
    ent = i + 16
    samples = [struct.unpack(">IIII", data[ent + k * 16:ent + k * 16 + 16])
               for k in range(nsamp)]
    return hdr_size, samples


def _audio_schedule(jp_samples):
    """For each JP audio chunk: (video_frames_that_preceded_it, jp_off, jp_size).

    This captures the JP's read-ahead: an audio chunk sitting after V video
    frames (at 15fps) is fetched V/15 seconds into playback.
    """
    sched, vbefore = [], 0
    for (off, sz, a, b) in jp_samples:
        if a == AUDIO_SYNC:
            sched.append((vbefore, off, sz))
        else:
            vbefore += 1
    return sched


# Cinepak chunk-type ids (Sega FILM uses the standard QuickTime Cinepak ids).
_CB_FULL = (0x2000, 0x2200)      # full V4 / V1 codebook chunks
_CB_ENTRY = 6                    # bytes per codebook entry (24-bit colour)


def _align_cinepak_frame(frame: bytes) -> bytes:
    """Pad every Cinepak chunk/strip/frame to a 4-byte boundary.

    ffmpeg emits odd-sized chunks; the Saturn's SH-2 Cinepak decoder reads them
    with word/longword accesses and faults on a misaligned address (black screen
    / reset on real hardware — confirmed on Saroo). The JP original is 4-byte
    aligned throughout. We match it WITHOUT changing the decoded image:

      * vector chunks (0x3xxx) are read by macroblock COUNT, so trailing zero
        padding is ignored by the decoder -> pad with zeros to a multiple of 4.
      * full codebook chunks (0x2000/0x2200) are read by entry; a stray partial
        entry would corrupt them, so we append one whole unreferenced 6-byte
        entry (which moves an even size to a multiple of 4).

    The frame's own 3-byte length field is left untouched (ffmpeg/JP both store
    a value 8 below the real size; rewriting it makes ffmpeg reject the frame and
    is unnecessary — strips are walked by their own size fields). Verified to
    decode pixel-identical to the unaligned input.
    """
    nstrips = struct.unpack(">H", frame[8:10])[0]
    out_strips = []
    p = 12                                  # 12-byte frame header (2 reserved)
    for _ in range(nstrips):
        sid = frame[p:p + 2]
        ssz = struct.unpack(">H", frame[p + 2:p + 4])[0]
        box = frame[p + 4:p + 12]
        cp, end, chunks = p + 12, p + ssz, []
        while cp + 4 <= end:
            cid = struct.unpack(">H", frame[cp:cp + 2])[0]
            csz = struct.unpack(">H", frame[cp + 2:cp + 4])[0]
            cdata = frame[cp + 4:cp + csz]
            if len(cdata) % 4:
                if cid in _CB_FULL:
                    cdata += b"\x00" * _CB_ENTRY        # one whole dummy entry
                else:
                    cdata += b"\x00" * (-len(cdata) % 4)  # zero-pad vectors
            chunks.append(struct.pack(">HH", cid, len(cdata) + 4) + cdata)
            if csz < 4:
                break
            cp += csz
        body = b"".join(chunks)
        out_strips.append(sid + struct.pack(">H", 12 + len(body)) + box + body)
        p += ssz
    return frame[0:12] + b"".join(out_strips)   # keep original length field


def _remux_saturn(my_cpk: bytes, jp_cpk: bytes, fps: int = FPS) -> bytes:
    """Re-wrap OUR Cinepak video frames into a Saturn-exact Sega FILM container:
    version 1.08, timebase 30, FDSC + every audio chunk reused verbatim from the
    JP file, audio-first priming. ffmpeg's own film_cpk layout does NOT play on
    real hardware (black screen / popping — confirmed on Saroo).

    Works at any integer multiple of 15fps (15 -> dur 2, 30 -> dur 1). The audio
    interleave reproduces the JP's wall-clock read-ahead: a chunk placed after V
    JP frames is placed after V*fps/15 of OUR frames, so priming holds at 30fps
    too. Requires our frame count to equal jp_video_count * fps/15.
    """
    if JP_TIMEBASE % fps:
        raise ValueError(f"fps {fps} must divide {JP_TIMEBASE} (use 15 or 30)")
    my_hdr, my_s = _split_samples(my_cpk)
    jp_hdr, jp_s = _split_samples(jp_cpk)
    my_video = [(o, s, a) for (o, s, a, b) in my_s if a != AUDIO_SYNC]
    jp_vcount = sum(1 for s in jp_s if s[2] != AUDIO_SYNC)
    scale = fps // FPS                                 # 15->1, 30->2
    expect = jp_vcount * scale
    if len(my_video) != expect:
        raise ValueError(
            f"video frame count {len(my_video)} != expected {expect} for {fps}fps")
    dur = JP_TIMEBASE // fps                            # 15->2, 30->1
    sched = [(vb * scale, off, sz) for (vb, off, sz) in _audio_schedule(jp_s)]

    data, entries, ai = bytearray(), [], 0
    n = len(my_video)
    for i in range(n + 1):                              # +1 flushes trailing audio
        while ai < len(sched) and sched[ai][0] <= i:
            _, ao, asz = sched[ai]; ai += 1
            cur = len(data)
            data += jp_cpk[jp_hdr + ao:jp_hdr + ao + asz]
            entries.append((cur, asz, AUDIO_SYNC, 1))
        if i < n:
            vo, vsz, va = my_video[i]
            frame = _align_cinepak_frame(my_cpk[my_hdr + vo:my_hdr + vo + vsz])
            cur = len(data)
            data += frame
            pts = (i * dur) | (NOT_SYNC_FLAG if (va & NOT_SYNC_FLAG) else 0)
            entries.append((cur, len(frame), pts, dur))
    assert ai == len(sched), (ai, len(sched))

    nsamp = len(entries)
    stab_size = STAB_HEADER_BYTES + nsamp * SAMPLE_BYTES
    hdr_size = FILM_HEADER_BYTES + FDSC_BYTES + stab_size
    out = bytearray()
    out += b"FILM" + struct.pack(">I", hdr_size) + b"1.08" + b"\x00\x00\x00\x00"
    out += jp_cpk[16:48]                               # FDSC verbatim from JP
    out += (b"STAB" + struct.pack(">I", stab_size)
            + struct.pack(">I", JP_TIMEBASE) + struct.pack(">I", nsamp))
    for (o, s, a, b) in entries:
        out += struct.pack(">IIII", o, s, a, b)
    assert len(out) == hdr_size, (len(out), hdr_size)
    out += data
    return bytes(out)


def _parse_film_fdsc(data: bytes) -> dict:
    """Parse the Sega FILM header / FDSC chunk (big-endian) for verification."""
    if data[:4] != b"FILM":
        raise ValueError("not a Sega FILM container")
    if data[16:20] != b"FDSC":
        raise ValueError("FDSC chunk not where expected")
    return dict(
        fourcc=data[24:28],
        height=struct.unpack(">I", data[28:32])[0],
        width=struct.unpack(">I", data[32:36])[0],
        bpp=data[36],
        a_channels=data[37],
        a_bits=data[38],
        a_compression=data[39],
        a_rate=struct.unpack(">H", data[40:42])[0],
    )


def _srt_ts_to_ass(ts: str) -> str:
    """'00:00:02,500' -> '0:00:02.50' (ASS centisecond timestamps)."""
    hh, mm, rest = ts.strip().split(":")
    ss, ms = rest.split(",")
    return f"{int(hh)}:{mm}:{ss}.{int(ms) // 10:02d}"


def _srt_to_pixel_ass(srt: Path) -> str:
    """Render an .srt as an .ass whose PlayRes matches the 320x224 frame, so the
    Eagle III pixel font lands 1:1 (FontSize 16 == 16px). Style: white fill, 1px
    black outline, bottom-centred, raised SUB_MARGIN_V px."""
    import re
    blocks = re.split(r"\n\s*\n", srt.read_text(encoding="utf-8").strip())
    events = []
    for blk in blocks:
        lines = blk.strip().splitlines()
        ti = 0 if lines and "-->" in lines[0] else 1
        if ti >= len(lines) or "-->" not in lines[ti]:
            continue
        start, end = (x.strip() for x in lines[ti].split("-->"))
        text = r"\N".join(lines[ti + 1:])
        events.append((_srt_ts_to_ass(start), _srt_ts_to_ass(end), text))
    head = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {WIDTH}\nPlayResY: {HEIGHT}\n"
        "ScaledBorderAndShadow: yes\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        f"Style: Default,{SUB_FONT},{SUB_FONT_SIZE},&H00FFFFFF,&H00000000,"
        f"&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,4,4,{SUB_MARGIN_V},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    body = "\n".join(f"Dialogue: 0,{s},{e},Default,,0,0,0,,{t}"
                     for s, e, t in events)
    return head + body + "\n"


def build_movie_cpk(
    source: Path,
    srt: Path,
    jp_cpk: Path,
    out: Path,
    *,
    fps: int = FPS,
    interpolate: bool = False,
    video_bitrate: str = DEFAULT_VIDEO_BITRATE,
    quiet: bool = False,
) -> Path:
    """Encode ``out`` (Sega FILM/CPK) from ``source`` video + ``srt`` subtitles,
    reusing the audio track from ``jp_cpk`` verbatim.

    Returns the output path. Raises on ffmpeg failure or if the result does not
    match the engine-fixed shape (320x224 Cinepak + 8-bit/22050/mono PCM).
    """
    source, srt, jp_cpk, out = map(Path, (source, srt, jp_cpk, out))
    for p in (source, srt, jp_cpk):
        if not p.exists():
            raise FileNotFoundError(p)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Run from the .srt's directory so the subtitles filter gets a bare filename
    # (no path-escaping headaches inside the filtergraph). Generate a pixel-exact
    # .ass next to it (PlayResY == frame height -> Eagle III renders 1:1).
    cwd = srt.parent
    ass = srt.with_suffix(".pixel.ass")
    ass.write_text(_srt_to_pixel_ass(srt), encoding="utf-8")
    # Subtitles are burned AFTER any frame interpolation so the text itself is
    # never motion-warped — interpolation only touches the underlying picture.
    parts = [f"scale={WIDTH}:{HEIGHT}:flags=lanczos"]
    if interpolate and fps != FPS:
        # genuine motion-compensated interpolation (source is natively 15fps)
        parts.append(
            f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
    parts.append(subtitles_filter(ass.name, FONTS_DIR))
    parts.append("format=rgb24")
    vf = ",".join(parts)
    # ffmpeg writes a scratch CPK; we then re-wrap it into the Saturn-exact
    # container with _remux_like_jp (ffmpeg's own layout does not play on hw).
    ffmpeg_out = out.with_name(out.name + ".ffmpeg.tmp")
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-loglevel", "error" if quiet else "info",
        "-i", str(source.resolve()),       # 0: upscaled video
        "-i", str(jp_cpk.resolve()),        # 1: JP CPK (audio source)
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(DURATION),
        "-filter:v", vf,
        "-r", str(fps),
        "-c:v", "cinepak",
        "-b:v", video_bitrate,
        # Force EXACTLY MATCH_STRIPS strips on every frame (min==max), so the
        # structure is uniform like the JP (which is always 2). 'max' alone lets
        # ffmpeg drop to 1 strip on simple frames — untested on the JP decoder.
        "-min_strips", str(MATCH_STRIPS),
        "-max_strips", str(MATCH_STRIPS),
        "-max_extra_cb_iterations", "4",    # better codebooks, slower
        "-c:a", "pcm_s8_planar", "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CH),
        "-f", "film_cpk",
        str(ffmpeg_out.resolve()),
    ]
    subprocess.run(cmd, cwd=cwd, check=True)

    # Re-wrap into the JP-exact container. Only the native 15fps cadence maps
    # onto the JP sample table; other framerates keep ffmpeg's layout (which is
    # NOT verified on real Saturn hardware — emulator/comparison use only).
    if JP_TIMEBASE % fps == 0:
        out.write_bytes(_remux_saturn(
            ffmpeg_out.read_bytes(), jp_cpk.read_bytes(), fps))
        ffmpeg_out.unlink()
    else:
        ffmpeg_out.replace(out)
        if not quiet:
            print(f"  WARNING: {fps}fps doesn't divide {JP_TIMEBASE} — kept ffmpeg "
                  "container; NOT Saturn-hardware verified")

    # verify engine-fixed shape before handing the file on
    f = _parse_film_fdsc(out.read_bytes())
    assert f["fourcc"] == b"cvid", f
    assert (f["width"], f["height"]) == (WIDTH, HEIGHT), f
    assert (f["a_channels"], f["a_bits"], f["a_rate"]) == (AUDIO_CH, 8, AUDIO_RATE), f
    if not quiet:
        size = out.stat().st_size
        print(f"\n{out}  {size:,} bytes  ({size*8/DURATION/1e6:.2f} Mbit/s avg)")
    return out


# --- disc-sourced encode (what `build.py --encode-movie` uses) ---------------
DEFAULT_SRT = REPO_ROOT / "assets" / "movie" / "opening_en.srt"


def require_ffmpeg() -> None:
    """ffmpeg does the Cinepak encode and the subtitle burn-in. It is the ONLY
    thing the patch needs beyond the standard library, and only on this path."""
    missing = [t for t in ("ffmpeg",) if shutil.which(t) is None]
    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} not found on PATH — the opening movie is "
            "encoded with ffmpeg (Debian/Ubuntu: 'sudo apt install ffmpeg'; "
            "macOS: 'brew install ffmpeg'; Windows: https://ffmpeg.org/download.html). "
            "Build without --encode-movie to keep the Japanese opening.")


def encode_from_disc(jp_cpk, out, srt=None, source=None, **kwargs):
    """Re-encode the disc's OWN opening with the English subtitles burned in.

    The video source defaults to `jp_cpk` itself: ffmpeg demuxes the Sega FILM
    container and decodes its Cinepak, so the user needs nothing but their
    Japanese disc (issue #6 — the upscaled master is not distributable). Audio
    is always taken from `jp_cpk` verbatim, so the Japanese voice track is
    preserved. Pass `source` to encode from a better master instead (an upscale
    of the same 84s opening); the result is sharper, everything else identical.
    """
    require_ffmpeg()
    jp_cpk, out = Path(jp_cpk), Path(out)
    return build_movie_cpk(Path(source) if source else jp_cpk,
                           Path(srt) if srt else DEFAULT_SRT,
                           jp_cpk, out, **kwargs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="upscaled source video (mp4/...)")
    ap.add_argument("srt", type=Path, help="subtitle file (.srt) timed to 84s")
    ap.add_argument("jp_cpk", type=Path, help="JP LANG.CPK (audio source)")
    ap.add_argument("out", type=Path, help="output LANG.CPK")
    ap.add_argument("--bitrate", default=DEFAULT_VIDEO_BITRATE,
                    help=f"video bitrate (default {DEFAULT_VIDEO_BITRATE})")
    ap.add_argument("--fps", type=int, default=FPS,
                    help=f"output framerate (default {FPS}; use 30 for smoother)")
    ap.add_argument("--interpolate", action="store_true",
                    help="motion-interpolate to --fps (source is natively 15fps)")
    args = ap.parse_args()
    build_movie_cpk(args.source, args.srt, args.jp_cpk, args.out,
                    fps=args.fps, interpolate=args.interpolate,
                    video_bitrate=args.bitrate)


if __name__ == "__main__":
    main()
