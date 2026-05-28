# Langrisser III : English Patch (Sega Saturn)

A work-in-progress English translation patch for *Langrisser III* (Sega Saturn, Japan), built from the original Japanese disc image.

<div align="center">
<table>
  <tr>
    <td><img src="assets/screenshots/01.png" width="320" /></td>
    <td><img src="assets/screenshots/02.png" width="320" /></td>
  </tr>
  <tr>
    <td><img src="assets/screenshots/03.png" width="320" /></td>
    <td><img src="assets/screenshots/04.png" width="320" /></td>
  </tr>
  <tr>
    <td><img src="assets/screenshots/05.png" width="320" /></td>
    <td><img src="assets/screenshots/06.png" width="320" /></td>
  </tr>
  <tr>
    <td><img src="assets/screenshots/07.png" width="320" /></td>
    <td><img src="assets/screenshots/08.png" width="320" /></td>
  </tr>
</table>
</div>

## About this patch

*Langrisser III* is a 1996 tactical RPG that never received an official English release. This patch translates the game's dialogue, story, and most of the menus into English so it can be played end-to-end without knowing Japanese.

Character and place names broadly follow the spellings used in *Langrisser Mobile*, the modern English release of the series.

## Status : v0.6 (work in progress)

This is an unfinished translation. The story can be followed from start to finish, but expect rough edges:

- Some dialogue lines are still being polished against the original Japanese. Phrasing may feel awkward in places.
- Some lines still break in the middle of words, and some text boxes that were one box in JP still take more than one box in EN.
- Item descriptions, and other UI text are still untranslated and will appear as garbled characters in-game.

Future releases will continue to polish the dialogue and replace the remaining Japanese UI text.

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

This produces `build/Langrisser_III_English.cue` and all track `.bin` files : ready to play.

3. **Load in your emulator** : open `build/Langrisser_III_English.cue` and play.

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

## Legal

This is a fan translation patch for educational and preservation purposes. You must own a legitimate copy of *Langrisser III (Japan)* for Sega Saturn. No copyrighted game data is distributed in this repository.
