# Langrisser III — English Translation Patch (Sega Saturn)

A work-in-progress English translation patch for Langrisser III (Sega
Saturn, Japan), built from the original Japanese disc image. All 125
dialogue sections, menus, UI, and font are translated; the project is
in a JP-aligned revision pass to fix legacy issues from the draft
translation source.

## Status

Playable end-to-end. Build takes ~45 seconds and produces a
sector-shifted ISO with 125 sections and 13,110 dialogue entries
encoded.

Audited entry-by-entry against the JP binary so far: Lushiris
prologue, Scenario 01 Floating Castle, the inter-scenario cutscene,
Scenario 02 Insane in Laffel, and Scenario 03 Laufel. Later chapters
still inherit the original draft translation and may show occasional
misaligned dialogue or wordy phrasing — tracked in `tests/` as XFAIL
lists (17 sections still short of JP entry count, 54 still drifting
on control-code parity).

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
python3 build.py --jp-iso "/path/to/Langrisser III (Japan)"
```

The directory passed to `--jp-iso` should contain the `.cue` plus the
Track 01 data `.bin` and audio track `.bin` files.

Add `--chd` to also produce a single-file CHD (recommended for
RetroArch + Beetle Saturn):

```bash
python3 build.py --jp-iso "..." --chd
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
and a stale value made it reject every voice sector. Other tested
fan-translation builds of Langrisser III (CWX 0.2, VermillionDesserts)
and discs rebuilt with `cd-replace` carry the same bug; CWX 0.2's
own build pipeline is the only prior work that handled it correctly.

## Repository layout

- `build.py` — single-command build pipeline.
- `tools/` — extraction, encoding, audit, and font tooling. Notable:
  - `iso_tools.py` — ISO9660 reader, batch sector-shift writer,
    Track 2 MSF rewrite.
  - `d00_tools.py` — D00.DAT script container parser/encoder.
  - `font_tools.py` — bigram tile map, EN font generator.
  - `translation_audit.py` — per-scenario JP↔EN parity report.
  - `balloon_opcodes.py` — D00 balloon-type classifier.
  - `list_named_entries.py`, `fix_wrap.py`, `font_diff.py`,
    `migrate_cwx_bins.py` — focused helpers.
- `tests/` — pytest suite (currently 113 passed, 11 skipped).
- `scripts/en/` — 125 EN scenario scripts plus menu/font references.
- `patches/` — same-size menu/UI binary overlays (font, skill names,
  battle UI).

## Tests

```bash
python3 -m pytest tests/
```

Coverage spans D00 round-trip, encoder coverage, font tile inventory,
per-scenario entry-count parity with JP, and JP↔EN control-code
parity.

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
