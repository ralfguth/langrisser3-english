# Langrisser III patch toolkit — docs

Public usage documentation for the analyzer + dashboard tooling
that lives in `tools/layout_qa/`. The toolkit is **language-agnostic**:
it ships with the English translation in `scripts/en/`, but any
team can fork the repo and put a different `scripts/<lang>/` next
to it. The tooling adapts.

This directory is intentionally small. Each file is < ~150 lines so
a reader can navigate by audience instead of plowing through one
big README.

## Pick your audience

| You are… | Start with |
| --- | --- |
| Translating into a new language (Russian, etc.) | [getting-started.md](getting-started.md) → [forking-for-another-language.md](forking-for-another-language.md) |
| A Claude agent helping that team | [agent-cookbook.md](agent-cookbook.md) |
| Adding a feature to the tooling itself | [cli-reference.md](cli-reference.md) → [json-contract.md](json-contract.md) |
| Building the Vite/React/ECharts dashboard | [json-contract.md](json-contract.md) → [workflow/frontend-integration.md](workflow/frontend-integration.md) |

## Full index

Reference / onboarding:

- [getting-started.md](getting-started.md) — first 30 minutes on the repo
- [cli-reference.md](cli-reference.md) — all 5 subcommands + flags
- [json-contract.md](json-contract.md) — JSON shape + schema + TS types
- [forking-for-another-language.md](forking-for-another-language.md) — adapting `scripts/<lang>/` and glyphs
- [agent-cookbook.md](agent-cookbook.md) — copy-paste recipes for LLM agents

Workflow guides:

- [workflow/analyzing.md](workflow/analyzing.md) — pipeline `analyze → wrap → analyze → report`
- [workflow/snapshots.md](workflow/snapshots.md) — capture, list, diff, trend
- [workflow/fixing-overflows.md](workflow/fixing-overflows.md) — worklist → rewrite triage
- [workflow/frontend-integration.md](workflow/frontend-integration.md) — how the SPA consumes the JSON

## What this toolkit does

In one sentence: **measure how well a translation fits the game's
balloon/label layout, in a way that's safe to track over time and
trustworthy enough to drive a dashboard.**

Concretely:

- A deterministic wrap simulator reproduces Sega Saturn's
  budget-exhaustion line breaking.
- 9 issue codes classify every problem (overflow, broken word,
  poor utilization, etc.).
- Every entry buckets to `ERROR` / `PLAYABLE` / `POLISHED`.
- A markdown dashboard answers three questions: *is it playable?*
  *is it polished?* *what's irreducible?* (i.e. what won't fit even
  after optimal `<$FFFC>` insertion).
- A committable snapshot system tracks progress over time in a
  sibling git repo so the patch repo's history stays slim.
- An agent-cheap `query` subcommand returns < 2k-token markdown
  answers so future Claude sessions can read state without burning
  through the JSON.

## Glossary

- **Entry** — one non-blank line of a `scen*E.txt` file; ends in
  `<$FFFE>` (narration) or `<$FFFF>` (label).
- **Balloon** — one `<$FFFD>`-separated bubble within an entry.
- **Line** — one rendered line within a balloon (or the whole entry
  for labels).
- **Tile** — the unit the game measures budgets in. 1 ASCII char ≈
  1 tile; bigrams collapse common pairs to 1 tile.
- **Profile** — layout class with a budget (e.g. `DIALOGUE_12X4` =
  12 tiles × 4 lines).
- **Source** — the actual scripts on disk; the only thing analyzed.
