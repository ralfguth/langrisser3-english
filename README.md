# Langrisser III — English Translation Patch (Sega Saturn)

A work-in-progress English translation patch for Langrisser III (Sega
Saturn, Japan), built from the original Japanese disc image. The patch
covers all 125 dialogue sections (using the Akari Dawn draft as a
base), a thicker and more readable font optimised for CRT TVs, and select menu/UI overlays.
A JP-aligned revision pass is ongoing to fix misaligned entries and
wordy phrasing from the draft.

## Status

Playable end-to-end. Build takes ~45 seconds and produces a
sector-shifted ISO with 125 sections and 13,110 dialogue entries
encoded.

Audited entry-by-entry against the JP binary so far: Lushiris
prologue, Scenario 01 Floating Castle, the inter-scenario cutscene,
Scenario 02 Insane in Laffel, and Scenario 03 Laufel. All other
chapters inherit the original draft translation.

### Known issues

The unaudited chapters carry structural problems inherited from the
draft source: 17 scenario sections have the wrong number of dialogue
entries (misaligned with the JP binary), and 54 sections have
incorrect control-code parity. These issues can cause dialogue boxes
to display the wrong text, skip lines, or behave erratically. The
ongoing revision pass works through these chapter by chapter.

**Menu / UI translation is partial.** The CWX patch translated 1,424
of 2,518 JP UI strings (56.6%); 728 are still raw JP bytes that
render as gibberish in-game (most notably **all 701 item
descriptions**), and CWX dropped 366 entries entirely from tables
that didn't fit the English tile budget (e.g. fntsys11 lost 256
entries, fntsys4 lost 96). UI strings are currently shipped from
CWX's binary patch, not from the script tree; replacing that pipeline
with a script-driven UI is on the roadmap.

Character and place names follow Langrisser Mobile's English
localization where available (Dieharte, Liffany, Freya, Emerick,
Gerold, Feraquea, Bozel, Riguler, etc.).

## Building the patch

Requirements:

- Python 3.10+
- Your own Japanese Langrisser III disc image (CUE/BIN, with Track 01
  data and audio tracks)
- Optional: `chdman` (from MAME tools) for CHD output

Steps:

```bash
git clone https://github.com/ralfguth/langrisser3-english
cd langrisser3-english

# Configure the JP disc directory once (add to ~/.bashrc to persist):
export LANG3_JP_DIR="/path/to/Langrisser III (Japan)"

python3 build.py
```

The configured directory should contain the `.cue` plus the Track 01
data `.bin` and audio track `.bin` files. You can also override per
invocation with `--jp-iso "/other/path"`.

Add `--chd` to also produce a single-file CHD (recommended for
RetroArch + Beetle Saturn):

```bash
python3 build.py --chd
```

## Playing

The build writes to `build/`:

- `Langrisser_III_English.cue` — load in **Ymir** or **RetroArch + Beetle Saturn**
- `Langrisser_III_English.chd` — load in **RetroArch + Beetle Saturn**
  (only present if you passed `--chd`)

### Emulator compatibility

| Target                              | Music | Text | Character voices |
| ----------------------------------- | :---: | :--: | :--------------: |
| **Real Saturn hardware (Saroo)**    |  ✅   |  ✅  |        ✅        |
| **Ymir** (standalone emulator)      |  ✅   |  ✅  |        ✅        |
| **RetroArch + Beetle Saturn**       |  ✅   |  ✅  |        ✅        |
| **mednafen** (standalone)           |  ?    |  ?   |        ?         |
| **Kronos**                          |  ?    |  ?   |        ?         |

mednafen and Kronos are unconfirmed — reports welcome.

Beetle Saturn voice playback was broken in v0.5 and earlier; v0.5.1
fixes it by rewriting the in-sector MSF headers of Track 2 (XA voice
streams) so they match the post-shift physical position on disc.
Beetle's CD block uses the in-sector MSF to filter incoming sectors,
and a stale value made it reject every voice sector.

## Repository layout

- `build.py` — single-command build pipeline.
- `tools/` — extraction, encoding, audit, and font tooling. Notable:
  - `iso_tools.py` — ISO9660 reader, batch sector-shift writer,
    Track 2 MSF rewrite.
  - `d00_tools.py` — D00.DAT script container parser/encoder.
  - `font_tools.py` — bigram tile map, EN font generator.
  - `translation_audit.py` — per-scenario JP↔EN parity report.
  - `font_diff.py`, `migrate_cwx_bins.py` — focused helpers.
- `scripts/en/` — 125 EN scenario scripts plus menu/font references.
- `patches/` — same-size menu/UI binary overlays (font, skill names,
  battle UI).

## Credits

- **CyberWarriorX (Theo Berkau)** — Saturn reverse engineering, the
  original v0.2 patch, bigram font system, menu translations.
- **Akari Dawn, ElfShadow, Oogami** — original English translation
  scripts (used as a draft baseline; being revised against the
  Japanese source).
- **VermillionDesserts** — independent translation build, D00.DAT
  research, English font.
- **Ralf Guth** — current build pipeline, JP-aligned translation
  pass, font/encoder tooling.

## Legal

This is a fan translation patch for educational and preservation
purposes. You must own a legitimate copy of *Langrisser III (Japan)*
for Sega Saturn. No copyrighted game data is distributed in this
repository.
