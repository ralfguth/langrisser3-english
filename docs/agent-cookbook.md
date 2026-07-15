# Agent cookbook

You are an LLM agent helping a translation team. Goal: read state
and act with minimal token spend — don't parse the 20 MB full JSON,
don't read the Python source, don't grep the corpus when an
aggregate already exists.

This file is your stable reference. The patch repo + `tools/layout_qa/`
internals can shift; the contracts here don't.

## Token-cheap recipes

### "What's the state of the patch?"

```bash
python3 -m tools.layout_qa.cli query state
```

Returns ~30 lines of markdown: project summary, top issue codes,
snapshot frontmatter. Always start here.

### "Which files should I attack first?"

```bash
python3 -m tools.layout_qa.cli query top-files --by errors -n 10
python3 -m tools.layout_qa.cli query top-files --by overflow -n 10
python3 -m tools.layout_qa.cli query top-files --by polish -n 10
```

Three different orderings. By absolute error count (biggest single-
file wins), by `balloon_line_overflow` (rewrite triage), by polish
(near-perfect files that need only a sweep).

### "Tell me about one file"

```bash
python3 -m tools.layout_qa.cli query file scen124
```

Returns the file's readiness/polish rate, its byStatus, its byIssue
breakdown. Ten or twenty lines. Use BEFORE opening the source file.

### "What's the impact of one issue code?"

```bash
python3 -m tools.layout_qa.cli query issue balloon_line_overflow
```

Total occurrences, entries affected, balloons affected, files
affected, and a top-10 ranking of which files contain it.

### "Is the patch improving?"

```bash
python3 -m tools.layout_qa.cli query trend playabilityRate
python3 -m tools.layout_qa.cli query trend polishRate
python3 -m tools.layout_qa.cli query trend entriesError --since 2026-05-01
```

Time series across all committed snapshots. Each is a small
markdown table.

### "What does X issue code mean?"

```bash
python3 -m tools.layout_qa.cli query catalog
```

Static reference for the 9 issue codes + 6 layout profiles + the
status bucket. Always available, doesn't need a snapshot.

## Common compound flows

### Triage session

```bash
python3 -m tools.layout_qa.cli query state
python3 -m tools.layout_qa.cli query top-files --by errors -n 5
# pick the worst one
python3 -m tools.layout_qa.cli query file <picked-scen>
# read its issues, decide rewrite/wrap-tune
```

### Diff after a rewrite

```bash
python3 -m tools.layout_qa.cli snapshot --list
# pick before + after labels/dates
python3 -m tools.layout_qa.cli snapshot --diff before-fix after-fix
```

### Verify a regression suspicion

```bash
python3 -m tools.layout_qa.cli query issue broken_word_wrap
# top files? was a known clean file affected?
```

## What NOT to do

- **Don't read the full JSON via Read tool** if a `query` covers it.
  `reports/layout-qa-report.json` is 10-20 MB. The CLI is designed
  to give you targeted slices.
- **Don't read `tools/layout_qa/*.py`** to answer "what does this
  issue code mean". Use `query catalog`.
- **Don't grep `scripts/en/`** for "is text X in scen Y" when the
  pipeline already aggregated it. `query file scen019` tells you
  status + issues.
- **Don't insert `<$FFFC>` mid-word or eat a space after punctuation**
  to make text fit — that renders broken and is a `broken_word_wrap`
  error. Wrap at word boundaries only. (A wrap-simulation tool that
  did exactly this was removed.)
- **Don't pivot to script edits in a tooling branch**, or vice
  versa. The repo's workflow expects one feature per branch with
  defined scope.

## Reading translation context

When a balloon needs a rewrite, the JSON's `entries[i].jp` field
(when analyze was run with `--jp-scripts scripts/jp`) gives you the
canonical Japanese source. Rewrite EN to mirror JP structure
(`feedback_jp_structural_mirroring`):

- Match `<$FFFE>` entry count exactly.
- Match `<$FFFD>` balloon breaks per entry.
- Keep `<$F600>` placeholders where JP has them.
- Use canonical names from the project's NAMES AND TERMS canon —
  never re-translate a character name from scratch.

If you don't have access to the JP source, ask the user to re-run
analyze with `--jp-scripts`. Don't translate from English alone.

## Snapshot frontmatter

Each snapshot pins `gitCommit` + `gitBranch`. To answer "what did
the state look like at PR X?":

```bash
python3 -m tools.layout_qa.cli snapshot --list
# eyeball the labels / dates / commits — pick one
python3 -m tools.layout_qa.cli query state \
    --history reports/history   # uses latest by default
```

If the user wants a specific older snapshot, `snapshot --diff` is
the readable view; for raw access, read the snapshot JSON directly
(they're ~80 KB, agent-cheap).

## See also

- [cli-reference.md](cli-reference.md) — full subcommand reference.
- [json-contract.md](json-contract.md) — JSON shape for the rare
  case you do need to parse it.
- [workflow/fixing-overflows.md](workflow/fixing-overflows.md) —
  human-side rewrite guidance.
