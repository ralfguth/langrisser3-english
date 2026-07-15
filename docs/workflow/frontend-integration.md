# Workflow: frontend integration

The upcoming dashboard is **Vite + React + Apache ECharts**, lives in
a separate project, and consumes the JSON produced by the analyzer.
This doc is for the team building that project.

## Inputs

You'll typically load one of two JSONs:

| File | When | Shape |
| --- | --- | --- |
| `reports/layout-qa-report.json` | development, debug | `FullReport` (entries[*] included) |
| `reports/history/snapshot-YYYY-MM-DD_LABEL.json` | trend views, prod dashboard | `TrimmedSnapshot` (no entries[*], has snapshot frontmatter) |

The trimmed snapshot is ~80 KB; the full report is ~20 MB. Use the
right one for the right view.

## Wiring

```typescript
import type {
  LayoutQAReport,
  FullReport,
  TrimmedSnapshot,
  EntryStatus,
  LayoutProfile,
  IssueCode,
} from "@layout-qa/types";  // or relative path to types/layout-qa.ts
```

`types/layout-qa.ts` is hand-maintained but kept in sync with the
JSON Schema by a pytest. Vendor or symlink it into the SPA project;
when the schema bumps, refresh the vendored copy.

For runtime validation, point any JSON Schema validator at
`schema/layout-qa-0.3.1.schema.json`:

```typescript
import Ajv from "ajv";
import schema from "@layout-qa/schema-0.3.1.json";

const ajv = new Ajv();
const validate = ajv.compile(schema);
if (!validate(payload)) throw new Error(JSON.stringify(validate.errors));
```

## Discriminated narrowings

```typescript
function isTrimmed(r: LayoutQAReport): r is TrimmedSnapshot {
  return !!r.snapshot;
}

if (isTrimmed(report)) {
  // report.scenarios[*] has no `entries` — don't render the Inspector.
} else {
  // Full report — Entry Inspector data is available.
}
```

## Charts → data paths

Recommended ECharts mappings:

| Chart | Source path | Notes |
| --- | --- | --- |
| **Overview cards** | `projectSummary.*` | 7 numbers, no transform needed |
| **Status donut** | `summary.byStatus` | 3 slices |
| **Per-profile bars** | `summary.byProfileStatus` | stacked ERROR / PLAYABLE / POLISHED |
| **Per-profile fill** | `summary.lineUtilization` | bars: avgLine vs budget; avgFillRatio |
| **Issue breakdown** | `summary.byIssueScope` | bars with two series (occurrences, entriesAffected) |
| **Scenario scatter** | `scenarios[*].readinessRate / .polishRate` | size = entryCount, color = severity |
| **Scenario heatmap** | `scenarios[*].byIssue` | rows × issue codes |
| **Worst-N files** | sort `scenarios[*]` by `byStatus.ERROR` desc | for ranking tables |
| **Entry timeline** | `scenarios[i].entries[*].status` | colored strip per scen |
| **Entry Inspector** | `scenarios[i].entries[j].tileUsage.balloons[*].lines[*]` | full + paired JP via `entries[j].jp` |

ECharts `dataset` is a great fit — the same per-file array drives
multiple charts via `transform` / `encode`.

## Trend views

For "how is the patch improving over time", load every snapshot in
`reports/history/` (or use `query trend` which returns the same as
markdown):

```typescript
const snapshots: TrimmedSnapshot[] = await Promise.all(
  files.map(f => fetch(f).then(r => r.json()))
);
const series = snapshots
  .sort((a, b) => a.snapshot.date.localeCompare(b.snapshot.date))
  .map(s => ({ date: s.snapshot.date, value: s.projectSummary.playabilityRate }));
```

Color by `snapshot.label` if helpful (e.g. baselines vs feature
landings).

## Filtering

The schema's closed vocabularies make filter UIs trivial:

```typescript
const STATUS_OPTIONS: EntryStatus[] = ["ERROR", "PLAYABLE", "POLISHED"];
const PROFILE_OPTIONS: LayoutProfile[] = [
  "LABEL_CHARACTER_12X1", "LABEL_LOCATION_16X1", "OBJECTIVE_16X5",
  "NARRATION_16X5", "DIALOGUE_12X4", "UNKNOWN",
];
// IssueCode similar.
```

## Common pitfalls

- **Don't compute readiness/polish from scratch**. The fields
  `projectSummary.playabilityRate`, `summary.byProfileStatus[*].readiness`,
  and `scenarios[*].readinessRate` are pre-computed. Use them.
- **`byIssueScope[code].count` vs `.occurrences`**: same number;
  `count` is a 0.1.0 alias kept for back-compat. Prefer `occurrences`
  in new code.
- **Empty corpus**: `playabilityRate` and `polishRate` default to
  `1.0` (vacuous truth). Sanity-check `entriesAnalyzed > 0` before
  showing "100% ready" UI for a freshly initialized fork.
- **Snapshot label clashes**: two snapshots can share the same
  label on different dates. `query` resolves a bare label to the
  latest snapshot with that label. Filenames disambiguate.

## See also

- [json-contract.md](../json-contract.md) — every field documented
  with examples.
- [cli-reference.md](../cli-reference.md) — how to produce the JSONs
  the SPA reads.
- `schema/layout-qa-0.3.1.schema.json` (patch repo).
- `types/layout-qa.ts` (patch repo).
