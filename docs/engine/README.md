# Langrisser III Engine Notes

This directory collects what we've learned about how Langrisser III (Saturn,
JP) actually reads text at runtime, and the rules you cannot break when
editing `scripts/en/*.txt`. It is meant as a quick on-ramp for any agent or
developer who has never touched this project before, so they can stop
re-discovering the same traps.

These docs supplement — they do not replace — the higher-level pipeline and
architecture documents already in the repo:

- [`../../README.md`](../../README.md) — what `build.py` does end to end
- [`../../context.md`](../../context.md) — pipeline stages, CWX patches,
  font system, bigram encoding, in-place patch strategy, size budget
- [`../../SHORTENING_GUIDE.md`](../../SHORTENING_GUIDE.md) — workflow for
  fitting EN text into the JP sector budget
- [`../../CLAUDE_TODO_ENTRY_COUNTS.md`](../../CLAUDE_TODO_ENTRY_COUNTS.md) —
  active remediation plan for entry-count regressions

If you only read one file in *this* directory, read
[`entry-count-invariant.md`](entry-count-invariant.md). The rule it describes
has broken the project twice and is the thing most likely to break it again.

## Files in this directory

| File | What it answers |
| ---- | --------------- |
| [`entry-count-invariant.md`](entry-count-invariant.md) | Why entry count per section must match JP exactly; post-mortem of the Lushiris regression; how to verify. |
| [`script-file-format.md`](script-file-format.md) | What `parse_script_file` actually does; which control codes terminate entries; quirks you will hit editing scripts by hand. |
| [`gotchas.md`](gotchas.md) | Traps that have wasted time before: `measure.py` silent padding, the `lang3a2` off-by-one, tile codes vs Shift-JIS, and friends. |
| [`scen001-annotated.md`](scen001-annotated.md) | Worked example: the character-creation section, broken down by entry range, so you can see the invariants in real data. |

## Top 10 facts to know (TL;DR)

1. **The game reads strings by index, not sequentially.** A single
   out-of-order string in the middle of a section shifts every string
   after it and silently corrupts dialogue that comes later. This is
   the core engine constraint.

2. **Per-section EN entry count must equal JP entry count.** Not "close
   to," not "differ by padding." Exactly. See
   [`entry-count-invariant.md`](entry-count-invariant.md).

3. **`<$FFFE>` ends an entry. `<$FFFF>` also ends an entry** (used for
   metadata blocks such as character name lists). `<$FFFC>` and
   `<$FFFD>` are continuations *inside* one entry and do not change the
   count. See [`script-file-format.md`](script-file-format.md).

4. **Swapping `<$FFFE>` for `<$FFFC>` is the exact bug** that broke the
   Lushiris prologue in commit `5a27497`. Never do it.

5. **`measure.py` silently pads missing entries at the tail** of a
   section, so a bug that merges or loses entries in the **middle**
   still produces a valid-looking build. This is why middle-of-section
   regressions can pass with 35 green tests.

6. **`scripts/en/scenNNNE.txt` maps to D00.DAT section index `NNN - 1`.**
   `tests/test_entry_counts.py::test_entry_counts_match` is
   authoritative — trust it over any other alignment theory.

7. **`parse_script_file` drops header lines.** Any line starting with
   `Langrisser` or `Cyber` is skipped unconditionally (artifact of the
   CWX dumper header).

8. **`lang3a2/.../jp/scen1.sjs` is off by one.** It has 170 entries
   versus the real D00's 169 — one extra character name ("エマーリンク")
   that does not exist in the shipped `D00.DAT`. Never trust `lang3a2`
   JP dumps as authoritative; trust `parse_d00(build/d00_jp.dat)`.

9. **JP text is stored as 2-byte big-endian tile indices** into the
   game's font table, **not** Shift-JIS. Decoding raw `D00.DAT` bytes
   as SJIS gives garbage. Some glyph codes are outside the ASCII range
   (e.g. `0x03a2` = "‥").

10. **`D00.DAT` is patched in place at its original extent.** A section
    that outgrows its allocated sector span is left as JP and reported
    as `kept JP` in the build output. See `context.md` for the
    in-place patching strategy and size budget.

## What these docs are not

- Not a substitute for reading `tools/d00_tools.py`. When a fact here
  contradicts the parser, the parser is authoritative — fix these docs.
- Not a full reverse-engineering reference. They document the parts
  that have bitten us, not everything about the engine.
- Not memory (in the agent sense). These are project docs under git.
  If you find something wrong, edit the file and commit.

## Updating these docs

- Add new entries here when a new trap is found and confirmed (not on
  suspicion).
- Prefer concrete examples (file names, line numbers, commit SHAs,
  runnable commands) over prose.
- Mark claims as verified by showing the code or data that supports
  them. Unverified hypotheses belong in commit messages or PR
  descriptions, not here.
