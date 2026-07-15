// TypeScript contract for the Langrisser III Layout QA JSON output.
//
// Authoritative shape lives in schema/layout-qa-0.3.1.schema.json
// (JSON Schema draft 2020-12). These types mirror that file. Keep
// them in lockstep — every schema bump touches both.
//
// Consumed by the Vite/React/ECharts dashboard project. Import with:
//
//     import type { LayoutQAReport } from "./types/layout-qa";
//
// All field names match the JSON exactly (camelCase, not snake_case).
//
// Generated artefacts:
//   - Full report:    reports/layout-qa-{report,wrapped}.json
//   - Trimmed snap:   reports/history/snapshot-YYYY-MM-DD_LABEL.json
//                     (same shape; entries[] is omitted + has `snapshot`)

// ---------------------------------------------------------------------------
// Vocabularies — closed enumerations locked by the schema.
// ---------------------------------------------------------------------------

export type EntryStatus = "ERROR" | "PLAYABLE" | "POLISHED";

export type LayoutProfile =
  | "LABEL_CHARACTER_12X1"
  | "LABEL_LOCATION_16X1"
  | "OBJECTIVE_16X5"
  | "NARRATION_16X5"
  | "DIALOGUE_12X4"
  | "HEROINE_DIARY"
  | "UNKNOWN";

export type IssueCode =
  // errors — disqualify readiness
  | "line_budget_exceeded"
  | "label_overflow"
  | "balloon_line_overflow"
  | "broken_word_wrap"
  | "unknown_layout_profile"
  // CHOICE-fit errors — player-facing menu option breaks its slot
  | "choice_overflow"
  | "choice_multiline"
  // spoken-punctuation gate (colon, semicolon, em-dash forbidden in prose)
  | "forbidden_punctuation"
  // warnings — disqualify polish only
  | "implicit_wrap_without_fffc"
  | "low_line_usage"
  | "special_token_overflow_risk"
  | "encoding_risk"
  | "line_padding_space"
  // info — advisory only, does NOT disqualify polish
  | "fluidity_headroom";

export type IssueSeverity = "error" | "warning" | "info";

/** A normalized rate in [0, 1]. Percentages are `rate * 100`. */
export type Rate = number;

// ---------------------------------------------------------------------------
// Top-level report
// ---------------------------------------------------------------------------

export interface LayoutQAReport {
  /** Pinned. Bumped on every additive or breaking change. */
  schemaVersion: "0.3.1";
  /** ISO-8601 UTC timestamp of the run. */
  generatedAt: string;
  /** Language code (e.g. "en"). */
  lang: string;
  tool: {
    name: string;
    version: string;
    [extra: string]: unknown;
  };
  /** Present only on trimmed snapshots (reports/history/). */
  snapshot?: SnapshotMeta;
  projectSummary: ProjectSummary;
  summary: Summary;
  scenarios: Scenario[];
}

// ---------------------------------------------------------------------------
// Snapshot frontmatter
// ---------------------------------------------------------------------------

export interface SnapshotMeta {
  /** YYYY-MM-DD. */
  date: string;
  label: string;
  gitCommit?: string;
  gitBranch?: string;
  note?: string;
}

// ---------------------------------------------------------------------------
// Project-level headline numbers
// ---------------------------------------------------------------------------

export interface ProjectSummary {
  filesAnalyzed: number;
  entriesAnalyzed: number;
  entriesError: number;
  entriesPlayable: number;
  entriesPolished: number;
  playabilityRate: Rate;
  polishRate: Rate;
}

// ---------------------------------------------------------------------------
// Detailed aggregates
// ---------------------------------------------------------------------------

export type ByStatusCounts = Record<EntryStatus, number>;
export type ByProfileCounts = Partial<Record<LayoutProfile, number>>;
export type ByIssueCounts = Partial<Record<IssueCode, number>>;

export interface ProfileStatusBucket {
  ERROR: number;
  PLAYABLE: number;
  POLISHED: number;
  total: number;
  readiness: Rate;
  polish: Rate;
}

export type ByProfileStatus = Partial<Record<LayoutProfile, ProfileStatusBucket>>;

export interface IssueScope {
  /** Alias for `occurrences` kept for 0.1.0 callers. */
  count: number;
  occurrences: number;
  entriesAffected: number;
  /** Unique balloons. Only meaningful for codes whose detail carries a
   * `balloon` field (primarily balloon_line_overflow). */
  balloonsAffected: number;
  filesAffected: number;
}

export type ByIssueScope = Partial<Record<IssueCode, IssueScope>>;

export interface LineUtilization {
  /** Number of entries that contributed to these averages. */
  samples: number;
  /** Average of each entry's worst (max-tile) line. */
  avgMaxLine: number;
  /** Average of each entry's mean per-line tile count. */
  avgLine: number;
  /** Mean of per-entry avg fill ratios — the headline utilization. */
  avgFillRatio: Rate;
  /** Mean of (entry.maxLine / width). Legacy view from 0.1.0. */
  avgFillRatioOfMaxLine: Rate;
}

export type ByProfileLineUtilization = Partial<
  Record<LayoutProfile, LineUtilization>
>;

export interface Summary {
  scenarioCount: number;
  entryCount: number;
  byStatus: ByStatusCounts;
  byProfile: ByProfileCounts;
  byProfileStatus: ByProfileStatus;
  byIssue: ByIssueCounts;
  byIssueScope: ByIssueScope;
  lineUtilization: ByProfileLineUtilization;
  playabilityRate: Rate;
  polishRate: Rate;
  /** Scen ids reclassified via config/layout-overrides.json. */
  overridesApplied: string[];
}

// ---------------------------------------------------------------------------
// Per-scenario shape
// ---------------------------------------------------------------------------

export interface Scenario {
  /** Always `scen` + 3 digits, e.g. "scen019". */
  id: string;
  /** Path relative to the patch repo root. */
  path: string;
  entryCount: number;
  byStatus: ByStatusCounts;
  byIssue: ByIssueCounts;
  readinessRate: Rate;
  polishRate: Rate;
  /** Present in full reports; dropped from trimmed snapshots. */
  entries?: Entry[];
  /** True when this scen holds in-world diary/letter entries (HEROINE_DIARY). */
  hasDiary?: boolean;
}

// ---------------------------------------------------------------------------
// Per-entry shape (only in full reports)
// ---------------------------------------------------------------------------

export interface Classification {
  /** 0..1 confidence assigned by the classifier rule that fired. */
  confidence: number;
  reason: string;
  state: string;
}

export interface Line {
  /** Index within the parent balloon. */
  index: number;
  tiles: number;
  fillRatio: Rate;
  /** Visible text on this rendered line. Tokens (e.g. `<$F600><$0000>`)
   * appear literally; other control codes are stripped. */
  text: string;
}

export interface Balloon {
  /** Index within the entry. 0 = first balloon. */
  index: number;
  lines: Line[];
}

export interface TileUsage {
  /** Width-and-max-lines budget the entry was measured against.
   * The second element is null for scrolling profiles (HEROINE_DIARY) that
   * have no line-count ceiling. */
  budget: [number, number | null];
  linesUsed: number;
  maxLine?: number;
  minLine?: number;
  avgLine?: number;
  avgFillRatio?: Rate;
  /** Structured per-balloon, per-line breakdown for the Entry Inspector. */
  balloons?: Balloon[];
  /** When set, lines explicitly approved despite their `low_line_usage`. */
  approvedLines?: Array<[number, number]>;
}

export interface Issue {
  code: IssueCode;
  severity: IssueSeverity;
  detail?: Record<string, unknown>;
}

export interface Entry {
  index: number;
  terminator: "FFFE" | "FFFF" | "";
  profile: LayoutProfile;
  semantic_subtype: string | null;
  classification: Classification;
  status: EntryStatus;
  tileUsage: TileUsage;
  issues: Issue[];
  /** Raw JP entry paired by index. Present when --jp-scripts was passed.
   * `null` when an EN entry has no JP counterpart. */
  jp?: string | null;
}

// ---------------------------------------------------------------------------
// Convenience: discriminated narrowings
// ---------------------------------------------------------------------------

/** A scenario from a trimmed snapshot — `entries` is guaranteed absent. */
export type TrimmedScenario = Omit<Scenario, "entries">;

/** A full (non-snapshot) report — `entries` is guaranteed present. */
export interface FullScenario extends Scenario {
  entries: Entry[];
}

export type FullReport = LayoutQAReport & { scenarios: FullScenario[] };
export type TrimmedSnapshot = LayoutQAReport & {
  snapshot: SnapshotMeta;
  scenarios: TrimmedScenario[];
};
