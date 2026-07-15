# Workflow: fixing overflows

After the analyzer runs, errors fall into two kinds:

- **Wrap-fixable** — `implicit_wrap_without_fffc` / word-split: the line
  fits, it just needs explicit `<$FFFC>` breaks at **word boundaries**
  (never mid-word).
- **Rewrite-required** — `balloon_line_overflow`: the balloon overflows
  even at the budget. Fix by rewriting the line shorter against the JP.

This doc is about the rewrite worklist.

## Generate it

```bash
python3 -m tools.layout_qa.cli worklist
# rows (CSV):    1406 → reports/layout-qa-rewrite-worklist.csv
# rows (MD):     50   → reports/layout-qa-rewrite-worklist.md
```

CSV holds every overflowing balloon. The markdown is the top-N
(default 50) for human reading.

## How rows are ranked

1. **`linesOver`** desc — actualLines − maxLines. A balloon
   overflowing by 4 lines outranks one overflowing by 1.
2. **`linesUsed`** desc — total lines emitted in the entry (a proxy
   for content size).
3. Lexicographic (`scen`, `entry`, `balloon`) as deterministic tiebreaker.

The simulator can emit multiple `balloon_line_overflow` issues
against the same balloon (one per line that spilled). The worklist
dedupes those — each row is one unique balloon, kept at its worst
severity.

## CSV columns

| column | meaning |
| --- | --- |
| `scen` | scen id (e.g. `scen124`) |
| `entry` | entry index in the file |
| `profile` | DIALOGUE_12X4 / NARRATION_16X5 / etc. |
| `balloon` | balloon index in the entry (0-based) |
| `actualLines` | lines the simulator emitted |
| `maxLines` | profile max |
| `linesOver` | actualLines − maxLines |
| `linesUsed` | total lines in the entry (across all balloons) |
| `maxLineTiles` | worst single line tile count |
| `lineBudget` | profile width (tiles per line) |
| `snippet` | visible text of the entry, truncated to ~80 chars |

`snippet` is a quick eyeball — for the full source you'll go to the
scen file. For balloon-level rendering, use the
[Entry Inspector](../json-contract.md) via the JSON's
`tileUsage.balloons[*].lines[*]`.

## A typical attack order

1. Generate worklist.
2. Look at top 10 — usually clustered in a few files. Order rewrites
   by file (less context-switching).
3. For each balloon: read the JP source (use `--jp-scripts scripts/jp`
   on analyze so the JSON carries `entries[*].jp`), decide the cut.
4. Edit `scripts/<lang>/scenNNNE.txt`. Don't merge/split `<$FFFE>`
   entries (entry count is structural — pointers shift).
5. Re-run `analyze` — the entry's status should move.

Tip: do file-at-a-time edits, snapshot at meaningful chunks, then
`snapshot --diff` to confirm the rewrite reduced errors.

## What NOT to do

- Don't change the `<$FFFE>` count. It's a structural code that
  drives in-game pointers.
- Don't strip `<$FFFD>` balloon breaks unless the JP source also
  fits in one balloon.
- Don't translate UI grid hiragana (out of scope for layout-qa, but
  a frequent gotcha — see the project's regression-lessons memo).
- Insert `<$FFFC>` only at **word boundaries**; a mid-word break or a
  lost space after punctuation is a `broken_word_wrap` error.

## Cross-checking

After a rewrite session:

```bash
# Re-analyze the real source — the only report.
python3 -m tools.layout_qa.cli analyze --all \
    --output reports/layout-qa-report.json

# Refresh dashboard.
python3 -m tools.layout_qa.cli report \
    --source reports/layout-qa-report.json

# Capture a snapshot if the milestone deserves it.
python3 -m tools.layout_qa.cli snapshot \
    --label scen124-rewrite-pass1 \
    --note "scen124 epilogues rewritten down to fit"

# Diff with the previous snapshot to confirm direction.
python3 -m tools.layout_qa.cli snapshot --diff baseline scen124-rewrite-pass1
```

## See also

- [cli-reference.md](../cli-reference.md) — `worklist` subcommand.
- [workflow/snapshots.md](snapshots.md) — capturing progress.
- [agent-cookbook.md](../agent-cookbook.md) — agent prompts for
  rewrite suggestions (against JP, with proper canon).
