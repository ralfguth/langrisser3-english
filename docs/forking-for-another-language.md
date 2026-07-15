# Forking for another language

The repo is dual-purpose: it ships the English patch in
`scripts/en/`, and it's a **reusable framework** for any other
language. Russian, French, Italian, Brazilian Portuguese — same
tooling, different `scripts/<lang>/`.

This doc lists the pieces a fork has to touch, in order.

## What stays untouched

Everything under `tools/` is language-agnostic. The analyzer, the
classifier, the wrap simulator, the dashboard, the snapshot system —
all of them treat the language as an opaque label.

You generally won't fork the tooling. Pull from upstream.

## What every fork touches

### 1. `scripts/<lang>/`

Replace `scripts/en/` with your own `scripts/ru/` (or `scripts/fr/`,
etc.). The pipeline reads any directory you point `--scripts` at; no
hard-coded "en".

```bash
python3 -m tools.layout_qa.cli analyze --all \
    --scripts scripts/ru \
    --lang ru \
    --jp-scripts scripts/jp \
    --output reports/layout-qa-report.json
```

`--lang` threads into the JSON's `lang` field — purely informational,
the analyzer doesn't branch on it.

### 2. Font tile map

`tools/font_tools.py` carries `CHAR_TILE_MAP` and `BIGRAM_TILE_MAP`
— the inventory of glyph tiles and bigram collapses that the
encoder + simulator share.

If your language adds glyphs (Cyrillic for Russian, accented Latin
for German, etc.):

- Add the new chars to `CHAR_TILE_MAP` with their tile codes.
- Add high-frequency bigrams to `BIGRAM_TILE_MAP` for compression.
- Verify with `tests/test_font_tiles.py`.

The `encoding_risk` warning fires when a char in your script isn't
in either map — use it to find gaps fast.

### 3. The sibling history repo

Each fork owns its own snapshot history. Create a sibling repo:

```bash
mkdir -p ~/romhack/lang3_layout_qa_history_ru
cd ~/romhack/lang3_layout_qa_history_ru
git init -b main
# Copy README.md and .gitignore from lang3_layout_qa_history,
# update the language banner in the README.

cd <your-fork>/langrisser3-english
rm -rf reports                                # if not symlinked yet
ln -s ~/romhack/lang3_layout_qa_history_ru reports
```

Then capture your first baseline:

```bash
python3 -m tools.layout_qa.cli analyze --all \
    --output reports/layout-qa-report.json
python3 -m tools.layout_qa.cli snapshot \
    --label baseline-ru \
    --note "first analysis of Russian fork"
```

### 4. JP pairing source

`--jp-scripts scripts/jp` points at the canonical Japanese script
dumps (same across all forks — they're the source of truth). Keep
the JP dump in sync with upstream English so JP↔your-lang pairing
by entry index stays correct.

If your fork translates **from** another language (e.g. Russian
from English rather than from JP), still pass `--jp-scripts scripts/jp`
so the Entry Inspector gets the original. The analyzer doesn't care
which language you translated from; the JP pairing is informational.

### 5. Per-scen overrides

`config/layout-overrides.json` carries reclassifications confirmed
by in-game playtest. The English fork has `scen124` mapped to
`NARRATION_16X5` because epilogues render in the wider region.

If your fork's playtest confirms the same render, copy that override.
If you confirm new ones (some forks find render surprises specific
to their build), add them.

### 6. Output naming

The build pipeline tags the output `.cue` per-language. Convention:

```
Langrisser ({Language} v{Ver}).cue
```

Set `--lang` consistently and the build will follow.

### 7. Names + terms canon

This is **not** about the tooling, but every translation needs a
canonical glossary so character names + terms don't drift across the
~125 scen files. The English fork keeps `NAMES AND TERMS.txt` as its
canonical glossary. Your fork builds the equivalent. Drift kills polish
faster than any other class of bug.

## What doesn't transfer

The 9 issue codes, the 6 layout profiles, the 12×4 / 16×5 budgets —
all of these are properties of the **game engine**, not the
language. They don't change per fork.

## A new-fork checklist

- [ ] `scripts/<lang>/scenNNNE.txt` populated (translation in progress)
- [ ] `tools/font_tools.py` extended for any new glyphs
- [ ] Sibling git repo created + `reports/` symlinked
- [ ] `--lang` set in CLI scripts/aliases
- [ ] First baseline snapshot captured
- [ ] Names canon in place

## See also

- [getting-started.md](getting-started.md) — first run.
- [cli-reference.md](cli-reference.md) — every flag.
- [workflow/snapshots.md](workflow/snapshots.md) — sibling repo.
