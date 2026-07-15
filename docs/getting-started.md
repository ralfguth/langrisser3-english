# Getting started

You just cloned the repo and want to know whether the translation
fits. This is the 30-minute path.

## Prerequisites

```bash
python3 --version      # ≥ 3.10 (uses match-style typing in places)
pip install jsonschema # only needed if you'll run the schema tests
```

A Saturn ISO is **not** needed for running the analyzer — it only
reads `scripts/<lang>/*.txt`. The ISO is required for building the
patch (separate `build.py`), not for measuring it.

## First run — full pipeline

```bash
cd langrisser3-english   # or your fork

# 1. Analyze the source — the real, shippable state of scripts on disk.
python3 -m tools.layout_qa.cli analyze --all \
    --output reports/layout-qa-report.json

# 2. Render the dashboard.
python3 -m tools.layout_qa.cli report \
    --source reports/layout-qa-report.json
```

Output: `reports/layout-qa-readiness.md`. Open it in any markdown
viewer. It reports `readiness` (playability) and `polish` on the real
source — see [analyzing.md](workflow/analyzing.md).

## Where are the reports?

`reports/` in this repo is a **symlink** to a sibling git repo —
`~/romhack/lang3_layout_qa_history/` for the English patch. Forks
should mirror that pattern with their own sibling repo
(`lang3_layout_qa_history_ru/` for Russian, etc.). See
[forking-for-another-language.md](forking-for-another-language.md)
for the why and the how.

The patch repo's `.gitignore` excludes `reports/` so nothing leaks
into your patch history.

## What to read next

- **First-time impression**: read [workflow/analyzing.md](workflow/analyzing.md)
  to understand `playability` vs `polish`.
- **Triage what to fix**: [workflow/fixing-overflows.md](workflow/fixing-overflows.md).
- **Capture a milestone**: [workflow/snapshots.md](workflow/snapshots.md).
- **Forking for another language**: [forking-for-another-language.md](forking-for-another-language.md).

## Sanity check

If `python3 -m tools.layout_qa.cli analyze --all` runs to completion
and the printed playability + polish numbers are between 0% and 100%,
the install is fine. The full pytest suite (`python3 -m pytest`) is
the formal verification — currently 908 tests passing.
