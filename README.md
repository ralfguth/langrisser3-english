# Langrisser III - English Translation Patch (Sega Saturn)

An English translation patch for Langrisser III on Sega Saturn, built from scratch using the original Japanese disc image.

## Character Names

| Japanese Original | English   |
| ----------------- | --------- |
| Diharto           | Dieharte  |
| Riffany           | Liffany   |
| Flaire            | Freya     |
| Emaillink         | Emerick   |
| Geriord           | Gerold    |
| Sieghart          | Gickhardt |
| Ferakia           | Feraquea  |
| Boser             | Bozel     |

Uses the official localized names from Langrisser Mobile where available.
Full reference: [docs/langrisser-mobile-name-map.md](docs/langrisser-mobile-name-map.md)

## How to Patch

**Requirements:**

- Python 3.10+
- Your own Japanese Langrisser III disc image (CUE/BIN format)

**Steps:**

1. Clone this repository:
   
   ```bash
   git clone https://github.com/ralfguth/langrisser3-english
   ```

2. Run the build script pointing to your Japanese disc:
   
   ```bash
   python3 build.py --jp-iso /path/to/your/Langrisser_III_Japan/
   ```
   
   The directory should contain the `.cue` file and the Track 01 `.bin` file.

3. Load `build/Langrisser_III_English.cue` in a Saturn emulator (Ymir, Mednafen, RetroArch + Beetle Saturn).

Build time is under 60 seconds. No additional dependencies required.

## What Gets Patched

- **All 125 dialogue sections** translated to English (in-game cutscenes, battle dialogue, tutorials)
- **Menus and UI** (skills, items, unit classes, battle text)
- **VermillionDesserts' English font** (1691 tiles, bigram encoding)
- **ISO rebuilt in-order** — supports files larger than original via sector shifting with full directory record updates (including Track 2 ADPCM voice data)

## Credits

- **CyberWarriorX (Theo Berkau)** — Saturn reverse engineering, original v0.2 patch, bigram font system, menu translations
- **Akari Dawn, ElfShadow, Oogami** — Complete English translation scripts
- **VermillionDesserts** — Independent translation build, D00.DAT expansion research, English font, 4-byte block alignment discovery
- **Ralf Guth** — Build pipeline, custom encoder, ISO rebuilder, translation fitting

## Legal

This is a fan translation patch for educational and preservation purposes.
You must own a legitimate copy of Langrisser III (Japan) for Sega Saturn.
No copyrighted game data is included in this repository.
