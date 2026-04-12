# The Entry Count Invariant

> **Rule.** For every scenario section, the number of entries in the EN
> script must exactly equal the number of entries in the corresponding JP
> section of `D00.DAT`. If it doesn't, the game breaks.

This is the single most important rule in the project. Every time it has
been broken, the game has visibly malfunctioned, and every defense in
`tests/test_entry_counts.py` exists because of it.

## Why the rule exists

The game reads scenario strings **by index**, not sequentially. Concretely:

- A `D00.DAT` section contains a fixed-size offset table followed by
  entry bodies.
- Each entry has a numbered slot in that offset table, indexed `0..K-1`.
- Game code retrieves a string with something conceptually equivalent
  to `display_string(section=N, index=I)`, where `I` is a compile-time
  constant baked into the game's scenario bytecode or pointer tables.
- There is no "next string" linked list. Strings are fetched by array
  lookup.

If the EN script for section `N` has `K-1` entries instead of `K`, then
every downstream index reference points to the wrong string. For the
character-creation questionnaire in `scen001`, that means:

- The question slot holds the answer of a later question.
- The answer slots for a given question belong to the previous question.
- The game's "what did you pick" flag ends up wired to the wrong slot,
  so the character-creation result is garbage.

The player sees this as: "the questionnaire is scrambled," "dialogue
answers don't match the question," or "the wrong tutorial hint appears."

## The Lushiris regression (commit `5a27497`)

A batch edit on `scen001E.txt` replaced two `<$FFFE>` terminators with
`<$FFFC>` continuations, merging two pairs of entries. The section
entry count went from **169 → 167**.

What happened next:

1. `measure.py` padded the missing entries at the **end** of the
   section with empty strings so the binary layout stayed internally
   consistent.
2. `build.py` completed without warning.
3. All 35 existing tests passed.
4. The game launched. The Lushiris prologue played strings from the
   wrong slots: opening lines were replaced by parts of the
   character-creation questionnaire, and the questionnaire itself
   read answers from the wrong question.

The fix was `git checkout 200f3dd -- scripts/en/scen001E.txt`. The
audit and defenses are tracked in
[`../../CLAUDE_TODO_ENTRY_COUNTS.md`](../../CLAUDE_TODO_ENTRY_COUNTS.md).

## What counts as an entry

Only two control codes close an entry:

| Code        | Ends an entry? | Typical use |
| ----------- | -------------- | ----------- |
| `<$FFFE>`   | Yes            | End of dialogue line |
| `<$FFFF>`   | Yes            | End of metadata-block item (e.g. character name list) |
| `<$FFFC>`   | No             | Continuation (newline, same entry) |
| `<$FFFD>`   | No             | Continuation with different scroll/flag behavior |

Only touch `<$FFFC>` / `<$FFFD>` when restructuring text within an
existing entry. **Never** add or remove `<$FFFE>` or `<$FFFF>`.

For the full parser behavior see
[`script-file-format.md`](script-file-format.md).

## How to verify one section

```bash
python3 -c "
import sys; sys.path.insert(0, 'tools')
from d00_tools import parse_d00, parse_script_file
from pathlib import Path
sections = parse_d00(Path('build/d00_jp.dat').read_bytes())
n = 1  # scen_num (change this)
idx = n - 1
jp = sections[idx].entry_count
en = len(parse_script_file(Path(f'scripts/en/scen{n:03d}E.txt')))
print(f'scen{n:03d}: JP={jp} EN={en} delta={en-jp:+d}')
"
```

## How to list every current mismatch

```bash
python3 -c "
import sys; sys.path.insert(0, 'tools')
from d00_tools import parse_d00, parse_script_file
from pathlib import Path
sections = parse_d00(Path('build/d00_jp.dat').read_bytes())
for sec in sections:
    n = sec.index + 1
    p = Path(f'scripts/en/scen{n:03d}E.txt')
    if not p.exists(): continue
    en = len(parse_script_file(p))
    jp = sec.entry_count
    if en != jp:
        print(f'scen{n:03d}: JP={jp} EN={en} delta={en-jp:+d}')
"
```

The output of this snippet is the living truth. Any entry in
`tests/test_entry_counts.py::ENTRY_COUNT_XFAIL` that does not appear
here should be removed from the whitelist; anything appearing here
that is **not** in the whitelist is a regression and must be fixed
before committing.

## Defenses in `tests/`

- **`test_entry_counts.py::test_entry_counts_match`** — compares EN
  count to JP count for every translated section. Whitelisted
  pre-existing mismatches are frozen in `ENTRY_COUNT_XFAIL`. Any
  deviation from the whitelist (new regression, or whitelisted case
  now fixed and needing removal) fails the test. Bypasses
  `measure.py`'s tail padding so middle-merge bugs are caught.

- **`test_entry_counts.py::test_scen001_lushiris_prologue_order`** —
  a canary that verifies known anchor strings in `scen001E.txt`
  appear in a plausible narrative order. Defense in depth against a
  reshuffle that happens to preserve the total count but still
  scrambles the character-creation questionnaire.

Run both with `pytest -q`. If either fails, do not commit until fixed.

## If the rule is broken

1. Do **not** commit.
2. Use `git log -- scripts/en/scenNNNE.txt` to find the last commit
   where the count matched.
3. `git checkout <commit> -- scripts/en/scenNNNE.txt` to revert just
   that file.
4. Re-run the verification snippet above and `pytest -q`. Both must be
   green.
5. If you intended to shorten the reverted text, shorten it again
   under the invariant: keep the `<$FFFE>/<$FFFF>` count, edit only
   the text inside entries.

The golden reference commit for the current project baseline is
`200f3dd` ("Estado atual: 81 EN, 44 JP - antes de restaurar
scen035E"). `scen001E.txt` was restored from this commit after the
Lushiris regression.
