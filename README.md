# Langrisser III : English Patch (Sega Saturn)

A work-in-progress English translation patch for *Langrisser III* (Sega Saturn, Japan), built from your own Japanese disc image.

## About this patch

*Langrisser III* is a 1996 tactical RPG that never received an official English release. This patch translates the story, dialogue, menus, and interface so the game can be played end to end without knowing Japanese. Character and place names broadly follow the spellings used in *Langrisser Mobile*, the modern English release of the series.

**Version 0.7 made the patch 100% this project's own work.** Every change on the disc is generated from this repository against the original Japanese game: no third-party binaries in the pipeline, nothing carried over from CyberWarriorX's earlier v0.2 patch (credited below as groundwork, not as shipped code or data). The English script was reworked line by line against the Japanese, correcting mistranslations and trimming a few additions that weren't in the original, so each character's voice and the tone of every line follow the source.

## Status : v0.7 (work in progress)

**Working**

- The whole story plays start to finish in English, with every dialogue and narration line translated.
- The interface is translated: menus, the save/load screen, the name-entry keyboard, and item / class / spell names with their descriptions.
- The opening movie plays with English subtitles (see [The opening movie](#the-opening-movie)).
- A layout-QA toolkit that checks how every line wraps inside the game's text boxes, so dialogue is fitted correctly before the disc is built.
- A companion English strategy guide ([text](strategy-guide/langrisser3-guide.txt), [HTML](strategy-guide/langrisser3-guide.html)) generated from the translation itself.

**Still to do toward v1.0**

- Some in-game messages still use the original Japanese layout, like the misaligned level-up messages.
- A couple of menu boxes need resizing (e.g. in the equipment menu).
- A few in-game graphics are still in Japanese and need translating (e.g. the mid-game opening and the ending credits).
- A font and text-encoder refactor to tighten the remaining typography.
- A full playthrough test, including cheat codes, the secret scenarios, and both endings.

## Applying the patch

You need:

- **Python 3.10+** (check with `python3 --version`). The build itself uses only the standard library : no `pip install`, no packages to add.
- **Your own Japanese *Langrisser III* disc image** : a folder with a `.cue` file, the Track 01 data `.bin`, and the audio track `.bin` files. This patch requires the original disc; no game data is distributed here.
- **[ffmpeg](https://ffmpeg.org/download.html)** : required to patch the opening movie (`--encode-movie`). Not needed for anything else.

### Source ISO

The patch is built and tested against the Redump "3M" variant of the Japanese disc. Check your Track 01 (the data track, where all game files live) with `sha256sum`:

```
SHA-256: 557bfaaa37dc11b6190c46dca8841bc252dfe9f1b3ba8b77ff242843b2bff4c8
File:    Langrisser III (Japan) (3M) (Track 01).bin
Size:    77,178,624 bytes (32,815 sectors × 2,352 bytes)
```

Other Redump variants of the same Japanese disc are accepted by the build, but only (3M) is regression-tested : a different hash may still work, unverified.

### Steps

1. **Download the latest release** from [GitHub Releases](https://github.com/ralfguth/langrisser3-english/releases) (Source code ZIP) and extract it.

2. **Run the patcher:**

```bash
python3 build.py --jp-iso "/path/to/Langrisser III (Japan)"
```

The folder you point to should contain the `.cue` plus the Track 01 data `.bin` and all audio track `.bin` files.

This produces a self-contained folder under `build/` named after the `.cue` (e.g. `build/Langrisser III (English v0.7)/`) holding the `.cue` and all track `.bin` files : ready to play.

3. **Load in your emulator** : open the `.cue` inside that folder and play.

### The opening movie

The opening FMV is game data, so no video ships here : only its English subtitle track (`assets/movie/opening_en.srt`). Add `--encode-movie` and the patcher builds the subtitled opening from the movie on *your* disc, keeping the Japanese voice track:

```bash
python3 build.py --jp-iso "/path/to/Langrisser III (Japan)" --encode-movie
```

Requires ffmpeg, and can take a while. Without the flag your disc keeps the Japanese opening.

The encoder lives in [`tools/movie_tools.py`](tools/movie_tools.py) and is developed as a standalone, game-agnostic tool in [**saturn-cinepak-muxer**](https://github.com/ralfguth/saturn-cinepak-muxer), where the write-up on making Cinepak FMV play on real Saturn hardware also lives.

### Compatibility

|                                          | Music | Text | Character voices |
| -----------------------------------------| :---: | :--: | :--------------: |
| **Real Saturn hardware (via Saroo 0.9)** |  ✅   |  ✅  |        ✅        |
| **Ymir** (standalone emulator)           |  ✅   |  ✅  |        ✅        |
| **RetroArch + Beetle Saturn**            |  ✅   |  ✅  |        ✅        |

## Credits

* **Ralf Guth**: project maintainer, current patch author, JP-aligned translation revision, font work, engine fixes, build pipeline, releases, and ongoing maintenance.

## Acknowledgements

* **CyberWarriorX (Theo Berkau)**: Saturn reverse engineering, the original v0.2 patch, bigram font system, and menu translations.
* **Akari Dawn, ElfShadow, Oogami**: original English translation scripts, used as a draft baseline and revised against the Japanese source.
* **VermillionDesserts**: independent translation build and D00.DAT research.

## License

The code in this repository is licensed under the **GNU General Public License, version 3 or later** (`GPL-3.0-or-later`). See [`LICENSE`](LICENSE). This covers the build pipeline, the tools (`tools/`), the tests, the schemas and authored glossaries, and the English translation scripts (`scripts/`) : the maintainer's own contributions, to the extent of the rights he holds. It cannot grant rights over the original game or over the prior third-party work this project builds on.

### Third-party assets

* **`data/fonts/Mx437_CL_EagleIII_8x16.ttf`** and the in-game glyphs derived from it are from VileR's *Ultimate Oldschool PC Font Pack*, under **CC BY-SA 4.0**. Attribution: VileR / int10h.org. Details in [`data/fonts/SOURCES.md`](data/fonts/SOURCES.md).
* The English script began from a draft translation baseline by **Akari Dawn, ElfShadow and Oogami**, and from **CyberWarriorX's** v0.2 patch (bigram font, menu translations). Those contributions remain the work of their respective authors.

## Legal

This is an unofficial fan translation for educational and preservation purposes, not affiliated with, sponsored by, or endorsed by NCS / Masaya or any rights holder. *Langrisser III* and all related assets are © their respective owners. You must own a legitimate copy of *Langrisser III (Japan)* for Sega Saturn to use this patch.
