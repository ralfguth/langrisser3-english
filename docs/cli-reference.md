# CLI reference

All five subcommands live in `tools.layout_qa.cli`. Invoke as:

```bash
python3 -m tools.layout_qa.cli <subcommand> [options]
```

`--help` works at every level.

## `analyze` — run the analyzer

Reads `scripts/<lang>/scen*E.txt`, classifies each entry by layout
profile, simulates wrap, and writes a full JSON report.

```bash
python3 -m tools.layout_qa.cli analyze --all \
    --output reports/layout-qa-report.json

# Limited to a single scen:
python3 -m tools.layout_qa.cli analyze scen019 \
    --output reports/scen019.json

# With JP source paired by entry index (enables the Entry Inspector
# in the dashboard — each entry gets a `jp` field).
python3 -m tools.layout_qa.cli analyze --all \
    --jp-scripts scripts/jp \
    --output reports/layout-qa-report.json
```

Key flags:

| flag | default | meaning |
| --- | --- | --- |
| `--scripts DIR` | `scripts/en` | source dir of `scenNNN[Ee].txt` files |
| `--jp-scripts DIR` | unset | when set, JP scen files paired by index → `entries[*].jp` |
| `--output FILE` | `reports/layout-qa-report.json` | JSON output path |
| `--lang CODE` | `en` | threaded into the JSON's `lang` field |
| `--approved FILE` | `config/layout_qa_approved.json` | per-line approvals (DIALOGUE only) |
| `--overrides FILE` | `config/layout-overrides.json` | per-scen profile overrides |

Exit codes: `0` clean, `2` errors found in corpus, `3` tool failure.

> **Removed:** `simulate-wrap` and the `layout-qa-wrapped.json`
> projection no longer exist. They wrapped a shadow copy that ate
> spaces after punctuation and masked `broken_word_wrap`, so every
> "wrap potential" metric was computed on corrupted text. Analyze and
> report run on the real source only.

## `worklist` — rewrite triage

Consumes the source report (`reports/layout-qa-report.json`) and emits
a CSV + markdown ranked list of balloons that overflow even at the
budget — i.e. things that need **rewriting** (shortening), not just
FFFC tuning.

```bash
python3 -m tools.layout_qa.cli worklist
# rows (CSV):    1406 → reports/layout-qa-rewrite-worklist.csv
# rows (MD):     50   → reports/layout-qa-rewrite-worklist.md
```

Sorted by lines-over-budget desc, then by total lines used. One row
per **unique balloon**; the simulator emits multiple overflow issues
per balloon (one per spilled line) but the worklist deduplicates so
each row is one rewrite target.

## `report` — markdown decision dashboard

```bash
python3 -m tools.layout_qa.cli report --source reports/layout-qa-report.json
```

Writes `reports/layout-qa-readiness.md` by default. See
[workflow/analyzing.md](workflow/analyzing.md) for what each section
means.

| flag | default | meaning |
| --- | --- | --- |
| `--source` | (legacy `--input`) | the source report JSON |
| `--output` | `reports/layout-qa-readiness.md` | markdown path |
| `--top` | `15` | rows in worst-N tables |

## `snapshot` — committable history

Captures a trimmed (~80 KB) snapshot of the latest analyze output
into the sibling history repo for trend tracking. See
[workflow/snapshots.md](workflow/snapshots.md).

```bash
# Capture.
python3 -m tools.layout_qa.cli snapshot \
    --label post-override \
    --note "scen124 reclassified to NARRATION_16X5"

# List existing.
python3 -m tools.layout_qa.cli snapshot --list

# Diff two — by filename, basename, label, or YYYY-MM-DD.
python3 -m tools.layout_qa.cli snapshot \
    --diff baseline post-override
```

| flag | default | meaning |
| --- | --- | --- |
| `--input` | `reports/layout-qa-report.json` | full JSON to trim |
| `--history` | `reports/history` | output dir (symlinked sibling repo) |
| `--label` | required for capture | slug-friendly id (e.g. `post-fix`) |
| `--note` | empty | free-text in the JSON frontmatter |
| `--list` | — | enumerate snapshots, exit |
| `--diff A B` | — | high-level diff, exit |

## `query` — token-cheap agent surface

Reads the latest snapshot and prints small markdown answers (< 2k
tokens) so an agent can triage state without parsing the full JSON.

```bash
python3 -m tools.layout_qa.cli query state              # headline numbers
python3 -m tools.layout_qa.cli query top-files \
    --by errors -n 10                                   # ranked files
python3 -m tools.layout_qa.cli query file scen124       # one file
python3 -m tools.layout_qa.cli query issue balloon_line_overflow
python3 -m tools.layout_qa.cli query trend playabilityRate
python3 -m tools.layout_qa.cli query catalog            # static reference
```

See [agent-cookbook.md](agent-cookbook.md) for use patterns.

## Exit codes

Common to every subcommand:

```
0  success
2  errors found in corpus (`analyze` only)
3  tool failure (bad argument, missing file, etc.)
```

## See also

- [json-contract.md](json-contract.md) — the JSON shape every
  subcommand consumes or produces.
- [workflow/analyzing.md](workflow/analyzing.md) — what the numbers
  mean.
