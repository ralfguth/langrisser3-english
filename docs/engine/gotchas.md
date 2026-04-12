# Gotchas and Traps

Things that have silently wasted time on this project. If you are touching
scripts or writing a tool that reads `D00.DAT`, skim this first.

## `measure.py` silently pads short sections

If an EN section has fewer entries than the corresponding JP section,
`measure.py` pads the **tail** of the section with empty strings so
the offset table stays valid and the binary fits in its sector
budget. The build succeeds, no warning appears, and
`build/Langrisser_III_English.cue` is produced.

But if entries were lost or merged in the **middle** of the section,
every string after the merge is shifted by the delta. The trailing
padding hides the mismatch from `build.py`, while in-game behavior
silently breaks.

This is how the Lushiris regression (commit `5a27497`) passed CI with
35 green tests. The defense is
`tests/test_entry_counts.py::test_entry_counts_match`: it compares EN
entry count to JP entry count directly, bypassing `measure.py`'s
padding, and any new mismatch fails immediately.

## `lang3a2` JP dumps are not trustworthy as alignment references

`lang3a2/TRANSLATION DUMPS & SCRIPTS/script/jp/scen1.sjs` parses to
**170 entries** (with `parse_script_file`), but the shipping
`D00.DAT` section 0 has **169 entries**. The extra entry in the dump
is a character name `エマーリンク` (Emerlink) at metadata position
18 — it does not exist in the shipped game.

**Consequence.** If you open `lang3a2/.../jp/scen1.sjs` as "the JP
reference" and align entry `N` in EN against entry `N` in the dump,
everything from the metadata block onward is off by one, and you
will "fix" text that was not broken.

**What to trust instead.** Load the JP `D00.DAT` directly:

```python
from pathlib import Path
import sys; sys.path.insert(0, 'tools')
from d00_tools import parse_d00
sections = parse_d00(Path('build/d00_jp.dat').read_bytes())
jp_section_0 = sections[0]
print(jp_section_0.entry_count)  # 169 — authoritative
```

It is not yet known whether other `lang3a2/*.sjs` files have the same
drift or different drift. Assume drift is possible; verify entry
counts against `parse_d00(...)` whenever you need to cross-reference.

## JP text in `D00.DAT` is tile codes, not Shift-JIS

Each entry in a `D00.DAT` section is a sequence of 2-byte big-endian
indices into the game's font table. It is **not** Shift-JIS, UTF-8, or
any other standard encoding. Decoding the raw bytes as SJIS or UTF-8
gives you garbage.

The high byte is usually `0x00` for ASCII-range glyphs and nonzero
for special glyphs. For example, the first five glyph codes of
`D00.DAT` section 0 entry 0 are:

```
00 a3 00 80 00 7f 00 c7 00 96  → "Diehärte"
```

and entry 18 begins with `03 a2 03 a2 …`, where `0x03a2` is the
glyph index for "‥" (double-dot leader) — the opening of the Lushiris
prologue ("‥‥騎士を志す若者よ" / "...Young man who wishes to be a
knight").

**If you want to read JP as text,** use the `lang3a2/.../jp/*.sjs`
dumps with the off-by-one caveat from the previous section — those
files are in `cp932` and decode normally. **If you want to verify
binary alignment** against the real game data, work with the
`parse_d00(...)` output instead and treat entries as opaque byte
blobs.

## `parse_script_file` silently drops header lines

Any line whose first word is `Langrisser` or `Cyber` is skipped
unconditionally. This is how the CWX dumper header gets stripped:

```
Langrisser III dumper [0x1418 to 0x3b93]

Cyber Warrior X
```

Two header lines, two discards, and parsing begins at the next
non-blank line. If you ever have legitimate game text starting with
one of those words, it will vanish from the entry list without
comment. In practice this has never mattered, but it's worth knowing
before you chase a "line that disappeared from the build."

## Don't put two `<$FFFE>` on the same line

The parser reads one line at a time and only checks whether the line
**ends** with a terminator. Writing `Foo<$FFFE>Bar<$FFFE>` on a
single line gives you **one** entry whose text is literally
`Foo<$FFFE>Bar<$FFFE>`, not two entries. The resulting count is
wrong and the encoded binary is corrupted.

One line, one terminator. Split onto two lines to get two entries.

## `D00.DAT` is patched in place, never rebuilt

`rebuild_d00()` exists in `tools/d00_tools.py` but is **not used**
by `build.py`. The game reads files by absolute sector on the disc,
not through the ISO9660 filesystem, so any file relocation causes a
black screen. `patch_d00_inplace()` is the only supported write path.

Practical consequence: if you make a section too large to fit in its
allocated sector span, the build still succeeds, but that specific
section will remain Japanese in the final ISO. Watch for the

```
D00.DAT: X sections patched, Y kept JP (too large)
```

line in `build.py` output. "Kept JP" means: your edit was rejected,
but quietly.

See [`../../context.md`](../../context.md) for the full explanation
of the in-place patching strategy, the D00.DAT extent, and the
bigram-encoding approach.

## Trailing `<$FFFC>` on the last line of a file

Because `parse_script_file` flushes the buffer only on `<$FFFE>` or
`<$FFFF>`, a file that ends with a `<$FFFC>` line leaves that line
dangling. The safety net adds a synthetic `<$FFFF>`, making that
dangling line a final entry — but one with a trailing `<$FFFC>` still
inside it, which encodes differently from a normal final entry. If
you hit a file whose last entry "looks weird," check for a stray
`<$FFFC>` at end-of-file.
