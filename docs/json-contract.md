# JSON contract

The analyzer emits JSON to drive every downstream consumer
(dashboard, snapshots, queries, the upcoming Vite/React/ECharts SPA).
The shape is **formally locked**:

- `schema/layout-qa-0.3.1.schema.json` — JSON Schema draft 2020-12
- `types/layout-qa.ts` — TypeScript interfaces mirroring the schema
- `tests/test_layout_qa_schema.py` — keeps both honest

Every report produced by `metrics.aggregate()` validates against the
schema on every test run. The schema rejects unknown enum values,
out-of-range rates, missing required keys.

## Versioning

Top-level `schemaVersion` is pinned. Today: `"0.3.1"`. The schema
file's `x-target-schema-version` extension declares which version it
validates — keep them in lockstep on every bump.

Bump policy: additive changes still bump (so consumers can pin and
get the new fields opt-in). Breaking changes require a new schema
file at the new version, and old snapshots stay valid against their
own schema.

## Top-level shape

```json
{
  "schemaVersion": "0.3.1",
  "generatedAt": "2026-05-27T22:00:00+00:00",
  "lang": "en",
  "tool": {"name": "layout_qa", "version": "0.3.1"},
  "snapshot": { ... },        // present ONLY on trimmed snapshots
  "projectSummary": { ... },  // flat headline numbers
  "summary": { ... },         // nested aggregates
  "scenarios": [ ... ]        // per-file blocks
}
```

`snapshot` is the frontmatter on committable trims:

```json
"snapshot": {
  "date": "2026-05-27",
  "label": "post-override",
  "gitCommit": "8a38621",
  "gitBranch": "main",
  "note": "scen124 override applied"
}
```

## `projectSummary` — headline

Flat numbers for cards / the Vite SPA's top row:

```json
"projectSummary": {
  "filesAnalyzed": 125,
  "entriesAnalyzed": 13110,
  "entriesError":    1412,
  "entriesPlayable":  403,
  "entriesPolished": 11295,
  "playabilityRate":   0.892,
  "polishRate":        0.862
}
```

## `summary` — aggregates

Used by charts, tables, drill-downs:

| key | shape | use |
| --- | --- | --- |
| `byStatus` | `{ERROR, PLAYABLE, POLISHED}: int` | overall donut |
| `byProfile` | `{profile: int}` | profile distribution |
| `byProfileStatus` | `{profile: {ERROR, PLAYABLE, POLISHED, total, readiness, polish}}` | per-profile bars |
| `byIssue` | `{code: int}` | issue bar chart |
| `byIssueScope` | `{code: {occurrences, entriesAffected, balloonsAffected, filesAffected}}` | issue impact at the right unit |
| `lineUtilization` | `{profile: {avgLine, avgMaxLine, avgFillRatio, samples}}` | histograms / heatmaps |
| `overridesApplied` | `string[]` | which scens were reclassified |

## `scenarios[*]` — per-file

```json
{
  "id": "scen019",
  "path": "scripts/en/scen019E.txt",
  "entryCount": 142,
  "byStatus": { "ERROR": 12, "PLAYABLE": 8, "POLISHED": 122 },
  "byIssue": { "balloon_line_overflow": 18, ... },
  "readinessRate": 0.915,
  "polishRate": 0.859,
  "entries": [ ... ]          // present in full reports; dropped from snapshots
}
```

## `entries[*]` — per-entry detail (Entry Inspector)

Only in full reports. Each entry carries:

```json
{
  "index": 42,
  "terminator": "FFFE",
  "profile": "DIALOGUE_12X4",
  "semantic_subtype": null,
  "classification": { "confidence": 0.9, "reason": "...", "state": "SCENE_12X4" },
  "status": "ERROR",
  "tileUsage": {
    "budget": [12, 4],
    "linesUsed": 5,
    "maxLine": 12, "minLine": 4,
    "avgLine": 8.6, "avgFillRatio": 0.717,
    "balloons": [
      {
        "index": 0,
        "lines": [
          { "index": 0, "tiles": 11, "fillRatio": 0.917, "text": "Sir Diehärte," },
          { "index": 1, "tiles": 12, "fillRatio": 1.0,   "text": "we must hurry" },
          { "index": 2, "tiles": 12, "fillRatio": 1.0,   "text": "before they ar" },
          { "index": 3, "tiles": 4,  "fillRatio": 0.333, "text": "rive again."   }
        ]
      }
    ]
  },
  "issues": [
    {
      "code": "balloon_line_overflow",
      "severity": "error",
      "detail": { "balloon": 0, "actualLines": 5, "maxLines": 4 }
    }
  ],
  "jp": "「殿下、急がなければ！」<$FFFE>"
}
```

`jp` is **optional** — present only when `analyze --jp-scripts DIR`
was used. `null` if the EN entry has no JP counterpart at that index.

`tileUsage.balloons[*].lines[*].text` contains the visible characters
that fell on that simulated line, plus the literal `<$F600><$0000>`
for protagonist-name tokens. Other control codes (e.g. `<$FFFB>`
pause) are stripped.

## Trimmed snapshots

`snapshot.py:trim()` produces a small committable copy of a full
report. It drops `scenarios[*].entries` (which is 90%+ of the bytes)
and prepends the `snapshot` frontmatter. Everything else is byte-
identical.

A trimmed snapshot is recognizable as: `report.snapshot` present AND
no `scenarios[*].entries`.

## TypeScript narrowings

`types/layout-qa.ts` ships discriminated narrowings so a consumer
can enforce the distinction:

```typescript
type FullReport     = LayoutQAReport & { scenarios: FullScenario[] };
type TrimmedSnapshot = LayoutQAReport & {
  snapshot: SnapshotMeta;
  scenarios: TrimmedScenario[];
};
```

`TrimmedScenario` is `Omit<Scenario, "entries">`.

## Closed vocabularies

These four enums are locked by the schema. Adding a new value
requires bumping `schemaVersion` and updating both the JSON Schema
and the TypeScript file (a pytest enforces that they match):

```
EntryStatus  = "ERROR" | "PLAYABLE" | "POLISHED"
LayoutProfile = "LABEL_CHARACTER_12X1" | "LABEL_LOCATION_16X1"
              | "OBJECTIVE_16X5" | "NARRATION_16X5"
              | "DIALOGUE_12X4" | "UNKNOWN"
IssueCode    = 12 codes (see `query catalog` for the authoritative list)
IssueSeverity = "error" | "warning" | "info"
```

## See also

- [cli-reference.md](cli-reference.md) — how to produce these JSONs.
- [workflow/frontend-integration.md](workflow/frontend-integration.md)
  — consuming from a TypeScript / Vite app.
- [agent-cookbook.md](agent-cookbook.md) — reading state without
  parsing the full JSON.
