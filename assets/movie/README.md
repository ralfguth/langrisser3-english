# Opening movie (LANG/LANG.CPK) — drop point

This directory is the **drop point** for the opening FMV. `build.py` injects
`LANG.CPK` into the disc when it is present (the `movie` module, on by default);
if it is absent, the build ships the Japanese opening unchanged. The only sanity
check here is that the file is a Sega FILM container (`magic == 'FILM'`).

- `LANG.CPK` — the encoded, English-subtitled movie. **Not committed** (~17 MB
  binary; this repo tracks no media). Place it here to ship it.

## The patch does not generate the movie

Encoding lives in its own project — **`../saturn-cinepak-muxer`** (its own git
repo). That is where the encoder, the subtitle `.srt`, the upscaled source, the
JP template, and the reverse-engineering write-up live. The patch only *consumes*
the finished `.CPK`.

To (re)generate and ship:

```bash
cd ../saturn-cinepak-muxer && ./build.sh         # writes media/LANG.CPK (15fps)
cp media/LANG.CPK ../langrisser3-english/assets/movie/LANG.CPK
cd ../langrisser3-english && python3 build.py    # injects it into the disc
```

The current `LANG.CPK` here is the 15 fps build, **confirmed playing on real
Saturn (Saroo)**: Cinepak 320×224, 2 strips, 4-byte aligned, JP audio verbatim,
Eagle III pixel-exact subtitles. (The encoder caps the bitrate under the Saturn's
2× CD read speed; 30 fps over-streams and stutters — see the muxer's README.)

To disable the English movie for a build: `LANG3_DISABLE=movie python3 build.py`.
