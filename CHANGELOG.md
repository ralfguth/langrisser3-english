# Changelog

All notable changes to the **Langrisser III English patch** (Sega Saturn) since v0.4.

The repository ships only source: you build the patched game from your own Japanese disc
(see the [README](README.md)). No copyrighted game data is included. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); dates are `YYYY-MM-DD`.

## [Unreleased]

### Added
- The patcher can now build the English-subtitled opening movie itself: run it with
  `--encode-movie` and it takes the movie off your own disc, burns the subtitles in, and
  puts it back. **ffmpeg is required to patch the movie**, and it can take a while, so it
  only runs when you ask for it, and so far it has only been tested on Linux. Without the
  flag your disc keeps the Japanese opening, exactly as before. ([#6])

### Fixed
- Building the patch no longer needs the Pillow imaging package. In 0.7.0 the build ran
  almost to the end and then stopped with "No module named 'PIL'" unless you had it
  installed; now a plain Python 3 is enough, as the README always said. ([#7])

[#6]: https://github.com/ralfguth/langrisser3-english/issues/6
[#7]: https://github.com/ralfguth/langrisser3-english/issues/7

## [0.7.0] - 2026-07-06

The whole game, interface included, is now playable in English. The dialogue was revised
line by line against the original Japanese, then given a full naturalness pass so
characters speak plain, everyday English instead of stiff "translation English".

### Added
- The entire in-game interface is translated: item, class, and spell names and their
  descriptions, menus, the save/load screen, and the name-entry keyboard. The previously
  unreadable menus are gone.
- The title screen now shows the full-color English logo with a translation credit.
- The opening movie plays with burned-in English subtitles, confirmed on real hardware.
  Note: the movie itself is game data and is not in this repository. The build embeds
  the subtitled opening only if you provide the video file (the subtitle track ships
  here); otherwise your disc keeps the original Japanese opening.
- A companion strategy guide (plain text and HTML) covering character creation, classes,
  the love-index system, every item, all 36 scenarios plus the 5 secret stages, and the
  endings. It is generated from the translation itself, so every quote and menu choice
  in the guide matches the game word for word.
- The hidden heroine diary entries, a secret in-game extra, are now translated.
- A layout-checking toolkit that simulates how each line wraps inside the game's text
  boxes, so dialogue can be fitted correctly before the disc is built.
- A project license (GPL-3.0-or-later).

### Changed
- Every line of dialogue was re-read in its character's voice and rewritten wherever it
  sounded stiff, bookish, or old-fashioned: polite speech stays polite but natural, and
  casual speech reads like everyday talk.
- Item pickup messages now follow one consistent style ("Acquired the Angel Ring!"),
  matching the official series localization.
- Laughs and shock reactions were standardized so each character always sounds like
  themselves.
- The build no longer depends on any third-party binaries. Every menu and interface
  change is generated from this project's own source, making the patch fully
  self-contained and reproducible from the Japanese disc alone.

### Fixed
- Questions and exclamations that earlier drafts had flattened into plain statements got
  their punctuation back, so lines land with the original's energy.
- A handful of lines spoken by the wrong character, or about the wrong subject, were
  caught in playtesting and corrected.
- The narration subtitles in the voiced story cutscenes now stay on screen longer before
  clearing, instead of scrolling away too early.
- The script matches the original's structure exactly, so no line can be pushed into the
  wrong character's mouth.
- Several interface layout glitches were corrected (menus, the field command box, status
  messages, and screen titles).

## [0.6.1] - 2026-05-27

Maintenance release. No gameplay or text changes; the built disc is identical to v0.6.

### Changed
- Cleaned up the build output and named the resulting disc image after the release and
  language, e.g. `Langrisser III (English v0.6.1).cue`.

## [0.6] - 2026-05-25

First broadly playable release: the dialogue is in English with a proper font.

### Added
- A new English font across dialogue, menus, and narration.
- English subtitles for the voiced cutscenes, which previously showed nothing.
- A small engine fix so a speaker's name sits on its own line above the dialogue.

### Changed
- The English script was aligned to the original's structure across all scenarios and
  story recaps, so text appears where the game expects it.

### Known limitations (at the time)
- Parts of the interface were still in Japanese (resolved in v0.7.0).

## [0.5.2] - 2026-04-29

Bugfix release ([#3](https://github.com/ralfguth/langrisser3-english/issues/3)). No text
or audio changes versus v0.5.1.

### Fixed
- The build now finds the game's audio tracks no matter how your rip names them; before,
  a naming mismatch could silently produce a disc with no sound.

## [0.5.1] - 2026-04-29

Bugfix release: character voices play again on more emulators.

### Fixed
- After the disc layout shifts to make room for the longer English text, the voice tracks
  now keep working on emulators that strictly validate disc addressing.

## [0.5.0] - 2026-04-29

Clean rebuild from the Japanese disc that establishes the build pipeline and the
infrastructure used to drive the project toward v1.0.

### Added
- A single-command build that produces the patched disc from your Japanese copy.
- Character and place names standardized to the official Langrisser Mobile spellings.
- An automated test suite and audit tools that check the translation against the original.

### Note
- Character voices were silent on some emulators (fixed in v0.5.1).

## [0.4] - 2026-04-29

Historical baseline, tagged retroactively. The starting point combines CyberWarriorX's
base hack with Akari Dawn's earlier English translation; later releases are rebuilt on top
of it from the Japanese disc.
