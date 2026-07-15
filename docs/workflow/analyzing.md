# Workflow: analyzing

How to run the pipeline and interpret the numbers.

## The pipeline

```
scripts/<lang>/scen*E.txt
        │
        ▼
   analyze ─────────────►  reports/layout-qa-report.json   (the real, shippable state)
        │
        ▼
   report ──────────────►  reports/layout-qa-readiness.md  (dashboard)
```

There is **one** report: the analysis of the real source scripts. An
earlier "wrap potential" projection (a `simulate-wrap` shadow + a
`layout-qa-wrapped.json`) was **removed** — it wrapped a shadow that
ate spaces after punctuation and masked `broken_word_wrap`, so its
numbers were fiction. Measure the
artifact that ships, never a machine-massaged shadow of it.

## Status bucket

Every entry is exactly one of:

```
ERROR     → any error issue
PLAYABLE  → no errors; may carry implicit_wrap_without_fffc or low_line_usage
POLISHED  → no errors AND no warnings
```

Invariant: `POLISHED ⊆ PLAYABLE ⊆ all_entries`.

Two derived rates per file / per profile / project-wide:

```
readinessRate = (PLAYABLE + POLISHED) / total       "is it shippable?"
polishRate    =              POLISHED  / total      "is it well-presented?"
```

## Issue catalog

5 errors disqualify readiness:

| code | meaning |
| --- | --- |
| `line_budget_exceeded` | reserved; FFFC-bounded segment > per-line budget |
| `label_overflow` | single-line LABEL_*X1 content > width (the label cannot wrap) |
| `balloon_line_overflow` | more rendered lines than the balloon allows |
| `broken_word_wrap` | engine wrap would split a word mid-word |
| `unknown_layout_profile` | classifier could not assign a profile |

4 warnings disqualify polish only:

| code | meaning |
| --- | --- |
| `implicit_wrap_without_fffc` | engine wraps at a safe boundary without explicit `<$FFFC>` |
| `low_line_usage` | non-final line < 50% of budget (poor utilization) |
| `special_token_overflow_risk` | `<$F600><$0000>` would push line past budget |
| `encoding_risk` | text contains a char not in the tile map (would be silently dropped) |

Live reference: `python3 -m tools.layout_qa.cli query catalog`.

## Layout profiles

| profile | budget | notes |
| --- | --- | --- |
| `LABEL_CHARACTER_12X1` | 12 × 1 | strict — `label_overflow` if > 12 |
| `LABEL_LOCATION_16X1` | 16 × 1 | polish-warn above 12 tiles |
| `OBJECTIVE_16X5` | 16 × 5 | mission bullets |
| `NARRATION_16X5` | 16 × 5 | scenario intros + epilogues |
| `DIALOGUE_12X4` | 12 × 4 | the vast majority of in-balloon text |
| `UNKNOWN` | — | classifier fallback; counted as ERROR |

The classifier is a state machine over `<$FFFE>` / `<$FFFF>` /
markers like SCENARIO and bullet prefixes. For scens that don't fit
the standard pattern (e.g. scen124 epilogues render in 16×5 not
12×4), use `config/layout-overrides.json` to remap.

## Where the numbers come from

For each entry, the simulator:

1. Walks tokens left to right, accumulating tile counts per line.
2. Wraps when the next tile would exceed the per-line budget.
3. Records the line tile count + visible text + balloon index.
4. Emits issue codes when limits are crossed.

Stats published per entry (`tileUsage`):

- `maxLine`, `minLine`, `avgLine`, `avgFillRatio` (averaged across
  every emitted line of every balloon in the entry).
- `balloons[*].lines[*]` — the structured per-line breakdown the
  Entry Inspector needs.

## Word-split / lost-space defects

`broken_word_wrap` also fires on **source-text** defects the width
check can't see: an explicit `<$FFFC>` dropped inside a word
(`Excelle<$FFFC>ncy`) or a space lost after punctuation
(`order,Varna`) — `detail.reason` is `fffc_splits_word`,
`fffc_splits_contraction`, or `missing_space_after_punctuation`.
These are the fingerprint of a mechanical hard-wrap and render
visibly broken in-game. Fix by re-breaking at word boundaries and
restoring the space — never by sawing through a word to make it fit.

## See also

- [cli-reference.md](../cli-reference.md) — exact invocations.
- [workflow/fixing-overflows.md](fixing-overflows.md) — how to act
  on the numbers.
- [workflow/snapshots.md](snapshots.md) — track these numbers
  over time.
- [json-contract.md](../json-contract.md) — every field documented.
