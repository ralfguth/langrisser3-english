# Workflow: snapshots

Snapshots are the committable history of the patch. Each captures a
~80 KB trim of the full analyze output, with a frontmatter that pins
git commit + branch + date so a future reader can answer "what did
the state look like at PR X?"

## Where snapshots live

`reports/` in the patch repo is a **symlink** to a sibling git repo
(e.g. `~/romhack/lang3_layout_qa_history/` for the English patch).
The sibling repo's `history/` directory holds the committed JSONs.

The patch repo ignores `reports/` so snapshots don't bloat the patch
history. The sibling repo's `.gitignore` ignores the ephemeral
artifacts (full JSON, dashboard markdown) so only the trims are
tracked.

Forks for other languages: create your own
`lang3_layout_qa_history_<lang>/` sibling repo and symlink. See
[forking-for-another-language.md](../forking-for-another-language.md).

## Capturing

```bash
# Refresh the analyzer first (snapshot reads the latest JSON).
python3 -m tools.layout_qa.cli analyze --all \
    --jp-scripts scripts/jp \
    --output reports/layout-qa-report.json

# Now capture.
python3 -m tools.layout_qa.cli snapshot \
    --label post-override \
    --note "scen124 reclassified to NARRATION_16X5"
# Snapshot written: reports/history/snapshot-2026-05-27_post-override.json (78.6 KB)
```

The `--label` becomes the slug in the filename and the
identifier you'll use to refer to this snapshot later. Keep it short,
slug-friendly, descriptive.

By default, snapshot reads `reports/layout-qa-report.json` (the source
report). Pass `--input` to choose a different source JSON.

## Listing

```bash
python3 -m tools.layout_qa.cli snapshot --list
# reports/history/snapshot-2026-05-20_baseline.json
# reports/history/snapshot-2026-05-27_post-override.json
# reports/history/snapshot-2026-05-27_wrap-fix.json
```

Sorted chronologically (the date is in the filename).

## Diffing

```bash
python3 -m tools.layout_qa.cli snapshot \
    --diff baseline post-override
```

The two args accept any identifier:

- full filename: `snapshot-2026-05-27_post-override.json`
- basename: `snapshot-2026-05-27_post-override`
- label only: `post-override` (resolves to latest snapshot with that label)
- date only: `2026-05-27` (latest snapshot from that date)

The diff highlights:

- Readiness / polish deltas in percentage points.
- Entry-count deltas per status.
- Issue codes whose count changed.
- Top 10 file movers (Δ readiness + Δ polish).

It's the simplest "is the patch improving?" sanity check.

## Snapshot frontmatter

Every captured snapshot starts with:

```json
{
  "schemaVersion": "0.3.1",
  "snapshot": {
    "date": "2026-05-27",
    "label": "post-override",
    "gitCommit": "8a38621",
    "gitBranch": "main",
    "note": "scen124 override applied"
  },
  "projectSummary": { ... },
  ...
}
```

`gitCommit` + `gitBranch` are best-effort: they come from `git rev-
parse` on the patch repo. If you're running from outside a git repo
they're empty strings.

## When to capture vs not

- **Capture**: after a milestone, before/after a feature, when you
  want to compare later.
- **Skip**: during in-progress experimentation. The dashboard
  (`report` subcommand) does the same numerical analysis without
  committing anything, and ephemeral artifacts are gitignored.

There is no auto-snapshot. Decide explicitly.

## Trend tracking via `query`

```bash
python3 -m tools.layout_qa.cli query trend playabilityRate
# → time series, one row per snapshot, ascending date
```

Works for any number in `projectSummary`:

- `playabilityRate`, `polishRate`
- `entriesError`, `entriesPlayable`, `entriesPolished`
- `entriesAnalyzed`, `filesAnalyzed`

`--since YYYY-MM-DD` limits to recent snapshots.

## See also

- [cli-reference.md](../cli-reference.md) — full `snapshot` + `query`
  flag reference.
- [agent-cookbook.md](../agent-cookbook.md) — agent uses of the
  history.
