# Langrisser III - English Translation Patch v0.4 (Sega Saturn)

An English translation patch for Langrisser III on Sega Saturn, built from scratch using the original Japanese disc image.

## How to Patch

**Requirements:**
- Python 3.10+
- Your own Japanese Langrisser III disc image (CUE/BIN format)

**Steps:**

1. Clone this repository:
   ```bash
   git clone https://github.com/user/langrisser3-english
   cd langrisser3-english
   ```

2. Run the build script pointing to your Japanese disc:
   ```bash
   python3 build.py --jp-iso /path/to/your/Langrisser_III_Japan/
   ```
   The directory should contain the `.cue` file and the Track 01 `.bin` file.

3. Load `build/Langrisser_III_English.cue` in a Saturn emulator (Ymir, Mednafen, RetroArch + Beetle Saturn).

Build time is under 10 seconds. No additional dependencies needed.

## What Gets Patched

- **All 125 dialogue sections** translated to English (in-game cutscenes, battle dialogue, tutorials)
- **Menus and UI** (skills, items, unit classes, battle text)
- **Custom bigram font** generated from embedded glyph data (1395 bigram pairs)
- **Original disc structure preserved** — no file relocation, no sector corruption

## Project History

The Langrisser III Saturn translation has a long history of community effort:

- **2001** — **CyberWarriorX (Theo Berkau)** released the first partial translation patch (v0.2), which included menu translations, a bigram font system, and Saturn disc reverse engineering work.
- **2006-2010** — **Akari Dawn**, **ElfShadow**, and **Oogami** produced a complete English script translation covering all 125 scenario sections.
- **2010s** — Several community projects attempted to combine CWX's tools with the Akari Dawn scripts, but encountered technical dead ends: corrupted dialogue data, broken name screens, and encoding mismatches caused by undocumented assumptions in the original patch tooling.
- **2026** — This project (v0.4) was started from scratch. Instead of building on top of CWX's insertion tools, we wrote a new pipeline: a custom bigram encoder, pixel-level font tile generation, and an in-place D00.DAT patcher that respects the Saturn engine's sector-based file access. The result is a clean build that patches a stock Japanese ISO without corrupting game data.

### What Makes v0.4 Different

Previous attempts failed because they inherited binary patches without fully understanding the Saturn engine's constraints:

- **D00.DAT is sector-locked.** The game reads dialogue data by absolute sector position, not by ISO directory entries. Moving D00.DAT breaks all dialogue. Our patcher writes English text directly into the original sectors.
- **Each section has a fixed size budget.** English text that exceeds the original Japanese section's byte count corrupts the next section. Our encoder reports overflows and the translation is shortened to fit.
- **UI tiles are interspersed in the font.** The game engine references specific tile indices for UI decorations (borders, icons). Our tile map skips these positions so they're never overwritten.
- **The bigram system is the key to fitting English text.** Japanese uses one 16x16 tile per character. English uses bigrams: two 8px letters per tile. This effectively doubles the character density per tile code, making English text fit in the same space.

## Technical Overview

The build pipeline:

1. Reads the Japanese Track 01 disc image (raw 2352-byte sectors, Mode 2 Form 1)
2. Extracts `FONT.BIN` (1691 tiles x 32 bytes) and `D00.DAT` (3.8 MB, 125 sections) from the ISO9660 filesystem
3. Generates 1438 English font tiles from embedded glyph bitmaps, patched onto the JP font base (preserving UI tiles)
4. Encodes 125 English scripts into 2-byte tile codes using greedy bigram matching
5. Writes the translated text into each D00.DAT section in-place (same size, same sectors)
6. Applies menu/UI translation patches (same-size overlays)
7. Recalculates EDC/ECC checksums for all modified sectors
8. Assembles the final CUE/BIN disc image with all 22 audio tracks preserved

### Project Structure

```
build.py              Build script (run this)
scripts/en/           125 English translation scripts
patches/              Menu/UI translation patches (binary overlays)
tools/
  font_tools.py       Bigram font generator (self-contained, all glyphs embedded)
  d00_tools.py        D00.DAT parser, encoder, and in-place patcher
  iso_tools.py        ISO9660 Mode 2 Form 1 read/write with EDC/ECC
  script_cleaner.py   Encoding fixes for translation scripts
  jp_dumper.py        Japanese text dumper (development tool)
tests/                Automated test suite
```

## Credits

- **CyberWarriorX (Theo Berkau)** — Saturn reverse engineering, original v0.2 patch, bigram font system, menu translations
- **Akari Dawn, ElfShadow, Oogami** — Complete English translation scripts
- **Ralf Guth** — v0.4 build pipeline, custom encoder, font tile generation, translation fitting
- **Career Soft / NCS / Masaya** — Langrisser III (1996)

## Legal

This is a fan translation patch for educational and preservation purposes.
You must own a legitimate copy of Langrisser III (Japan) for Sega Saturn.
No copyrighted game data is included in this repository.
