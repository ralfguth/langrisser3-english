# Opening movie (LANG/LANG.CPK)

The opening FMV is game data, so this directory holds only **`opening_en.srt`**,
the English subtitle track (ours, committed). The video itself is never
distributed here.

## Building the English opening

`python3 build.py --encode-movie` reads `LANG/LANG.CPK` off the user's own disc,
burns `opening_en.srt` into it, and injects the result (needs `ffmpeg`). It is
slow — the whole movie is re-encoded through a single-threaded Cinepak
encoder. The
encoder is `tools/movie_tools.py`; the Japanese audio is reused verbatim, and the
output clones the JP container exactly — Sega FILM 1.08, timebase 30, audio-first
priming, exactly 2 Cinepak strips per frame, every chunk 4-byte aligned. Anything
less black-screens or resets on real hardware (the SH-2 Cinepak decoder faults on
misaligned reads); ffmpeg's own `film_cpk` layout does **not** play.

The CPK is streamed off the disc, so its bitrate must stay under the Saturn's 2×
CD read speed (~2.46 Mbit/s): 15 fps (~1.6 Mbit/s) streams cleanly, 30 fps
over-streams and stutters. Resolution is fixed at 320×224.

`--movie-source path.mp4` encodes from a cleaner master of the same 84-second
opening instead of the disc's already-compressed Cinepak — sharper picture,
everything else identical. This is how the release builds are made.

## Drop point for a prebuilt CPK

Without `--encode-movie`, the build injects `LANG.CPK` from this directory if it
is here (magic must be `FILM`), and otherwise ships the Japanese opening. The
file is **not committed** (~17 MB of game-derived video). Use `LANG3_MOVIE_CPK`
to point at one elsewhere, or `LANG3_DISABLE=movie` to force the JP opening.

## Upstream

The encoder is developed as a standalone, game-agnostic tool in
[**saturn-cinepak-muxer**](https://github.com/ralfguth/saturn-cinepak-muxer),
together with the reverse-engineering write-up on making Cinepak FMV play on real
Saturn hardware. `tools/movie_tools.py` is the vendored copy the patch builds
with — fixes belong upstream first.
