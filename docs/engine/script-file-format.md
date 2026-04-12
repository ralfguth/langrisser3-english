# Script File Format (`scripts/en/scenNNNE.txt`)

This is a behavioral reference for `parse_script_file()` in
[`tools/d00_tools.py`](../../tools/d00_tools.py). If you are editing these
files by hand, the rules below determine what the parser — and therefore the
build — will see.

When these docs and the parser disagree, **the parser is right**.

## Overall shape

Each file starts with a header that the parser ignores:

```
Langrisser III dumper [0x1418 to 0x3b93]

Cyber Warrior X
```

Then a stream of text lines, each ending with exactly one control code:

- `<$FFFE>` — end of entry (counts toward entry total)
- `<$FFFF>` — end of metadata-block entry (also counts)
- `<$FFFC>` — continuation within the same entry (newline)
- `<$FFFD>` — continuation within the same entry (different scroll/flag)

Blank lines are ignored. The file has no other framing.

## Parser behavior, step by step

From `parse_script_file` in `tools/d00_tools.py`:

1. Read the file as UTF-8.
2. For each line:
   1. `line.strip()`. Drop it if empty.
   2. Drop it if it starts with `Langrisser` or `Cyber` — that is how
      the CWX dumper header gets skipped. **Unconditional.**
   3. Append the line to an internal buffer.
   4. If the line ends with `<$FFFE>` or `<$FFFF>`, join the buffer
      into one string, append it to the entry list, clear the buffer.
3. After the loop, if the buffer is not empty, append it as a final
   entry. If that trailing buffer does not end with a terminator, a
   literal `<$FFFF>` is appended to it first. This is a safety net,
   not a feature to rely on.

## Consequences you will hit

### `<$FFFF>` counts as an entry

This is not a "real terminator vs. fake terminator" distinction. For
metadata blocks (typically a list of character names at the top of a
scenario), each `<$FFFF>` line is its own entry. A block like:

```
Diehärte<$FFFF>
Tiaris<$FFFF>
Riffany<$FFFF>
```

produces **three** entries, not one. Every name in the list advances
the entry counter.

### Merging two lines inside one entry

When two lines are joined because the first ends in `<$FFFC>` or
`<$FFFD>`, the join is a plain string concatenation — no space, no
newline is inserted. So

```
Before we begin, I have a gift for you.<$FFFC>
Please push the C button.<$FFFE>
```

becomes one entry whose text is literally

```
Before we begin, I have a gift for you.<$FFFC>Please push the C button.<$FFFE>
```

If you rely on a space appearing at the boundary, you must include the
space in the source text yourself.

### One line, one terminator

The parser only looks at the **last** control code on a line — it does
not split a line at an interior `<$FFFE>`. Writing
`Foo<$FFFE>Bar<$FFFE>` on a single line produces **one** entry whose
text is the literal string `Foo<$FFFE>Bar<$FFFE>`, not two entries. The
count goes wrong and the encoded text becomes garbage.

If you want two entries, put them on two lines.

### `Langrisser` / `Cyber` prefix trap

The header-skip check is prefix-based and unconditional. Any line whose
first word is `Langrisser` or `Cyber` will silently vanish. This has
never mattered for actual game text, but it is worth knowing before you
diagnose a "line that disappeared."

### Trailing unterminated content gets a synthetic `<$FFFF>`

If the last line in the file has no `<$FFFE>` or `<$FFFF>`, the parser
appends `<$FFFF>` to it and calls it an entry anyway. This is a safety
net for dumper bugs, not a feature. Always close your last entry
explicitly with the control code that makes sense for it.

## Sanity check: EN counts per file

```bash
python3 -c "
import sys; sys.path.insert(0, 'tools')
from d00_tools import parse_script_file
from pathlib import Path
for p in sorted(Path('scripts/en').glob('scen*E.txt')):
    print(f'{p.name}: {len(parse_script_file(p))}')
"
```

This prints one line per script, giving the entry count the build will
see. No JP reference needed, useful for quick sanity checks after an
edit.

## Round-trip to the binary

The parser returns entries as Python strings. `build.py` passes them
through the bigram encoder in [`tools/font_tools.py`](../../tools/font_tools.py)
and writes them into `D00.DAT` via `patch_d00_inplace` in
[`tools/d00_tools.py`](../../tools/d00_tools.py). Characters that are
not in the font's glyph table are silently dropped by the encoder —
historically this has affected `ä`, `ö`, `ü` (see `context.md` for the
current state of extended-Latin coverage).

For the rest of the pipeline see [`../../context.md`](../../context.md).
