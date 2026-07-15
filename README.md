# Langrisser III : English Patch (Sega Saturn)

A work-in-progress English translation patch for *Langrisser III* (Sega Saturn, Japan), built from the original Japanese disc image.

## About this patch

*Langrisser III* is a 1996 tactical RPG that never received an official English release. This patch translates the game's story, dialogue, menus, and interface into English so it can be played end to end without knowing Japanese.

**Version 0.7 is a major revision: the patch is now 100% this project's own work.** Every change on the disc is generated from this repository's source against the original Japanese game: there are no third-party binaries in the pipeline, and nothing is carried over from CyberWarriorX's earlier v0.2 patch (credited below as groundwork, not as shipped code or data). Building on the earlier fan-translation draft, the English script was reworked line by line against the Japanese, correcting mistranslations and trimming a few additions that weren't in the original, so each character's voice and the tone of every line follow the source.

Character and place names broadly follow the spellings used in *Langrisser Mobile*, the modern English release of the series.

## Status : v0.7 (work in progress)

Version 0.7 is a radical step up in quality: the patch is now fully self-contained, and the entire script was rewritten and re-checked line by line against the Japanese.

**Working**

- The whole story plays start to finish in English, with every dialogue and narration line translated.
- The interface is translated: menus, the save/load screen, the name-entry keyboard, and item / class / spell names with their descriptions.
- The opening movie plays with English subtitles.
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

- **Python 3.10+** (check with `python3 --version`)
- **Your own Japanese *Langrisser III* disc image** : a folder with a `.cue` file, the Track 01 data `.bin`, and the audio track `.bin` files. This patch requires the original disc; no game data is distributed here.

### Source ISO

The patch is built and tested against the Redump "3M" variant of the Japanese disc. Track 01 (the data track, where all game files live) must hash to:

```
SHA-256: 557bfaaa37dc11b6190c46dca8841bc252dfe9f1b3ba8b77ff242843b2bff4c8
File:    Langrisser III (Japan) (3M) (Track 01).bin
Size:    77,178,624 bytes (32,815 sectors × 2,352 bytes)
```

Verify with:

```bash
sha256sum "Langrisser III (Japan) (3M) (Track 01).bin"
```

Other Redump variants of the same Japanese disc are supported by filename globbing in the build pipeline, but only the (3M) variant is regression-tested. If your disc dump has a different Track 01 hash, the build may still work but is unverified.

### Steps

1. **Download the latest release** from [GitHub Releases](https://github.com/ralfguth/langrisser3-english/releases) (Source code ZIP) and extract it.

2. **Run the patcher:**

```bash
python3 build.py --jp-iso "/path/to/Langrisser III (Japan)"
```

The folder you point to should contain the `.cue` plus the Track 01 data `.bin` and all audio track `.bin` files.

This produces a self-contained folder under `build/` named after the `.cue` (e.g. `build/Langrisser III (English v0.7)/`) holding the `.cue` and all track `.bin` files : ready to play.

3. **Load in your emulator** : open the `.cue` inside that folder and play.

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

The code in this repository is licensed under the **GNU General Public License, version 3 or later** (`GPL-3.0-or-later`). See [`LICENSE`](LICENSE). This covers the build pipeline, the extraction and layout tools (`tools/`), the tests, the schemas and authored glossaries, and the English translation scripts (`scripts/`).

This grant covers the maintainer's own contributions, to the extent of the rights he holds. It does not, and cannot, grant rights over the original game or over the prior third-party work this project builds on (see **Acknowledgements** and **Legal**).

### Third-party assets

* **`data/fonts/Mx437_CL_EagleIII_8x16.ttf`**, and the in-game glyphs derived from it, are from VileR's *Ultimate Oldschool PC Font Pack* and remain under **CC BY-SA 4.0**. Attribution: VileR / int10h.org. Details in [`data/fonts/SOURCES.md`](data/fonts/SOURCES.md).
* The English script began from a draft translation baseline by **Akari Dawn, ElfShadow and Oogami**, and from **CyberWarriorX's** v0.2 patch (bigram font, menu translations). Those contributions remain the work of their respective authors.

## Legal

This is an unofficial fan translation patch for educational and preservation purposes. It is not affiliated with, sponsored by, or endorsed by NCS / Masaya or any rights holder. *Langrisser III* and all related assets are © their respective owners. You must own a legitimate copy of *Langrisser III (Japan)* for Sega Saturn to use this patch. No copyrighted game data is distributed in this repository.
