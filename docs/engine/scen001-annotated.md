# `scen001E.txt` Annotated Reference

`scen001E.txt` is the character-creation and tutorial section for the
very first scenario. It has **169 entries** (matching JP), and because
the game reads strings by index every entry has a fixed semantic role.
This file documents those roles so that future edits know what they
are touching.

Roles below were verified by comparing
`parse_script_file(scripts/en/scen001E.txt)` side-by-side with the
`lang3a2/.../jp/scen1.sjs` dump and reconciling against the entry
count from `parse_d00(build/d00_jp.dat)`. The dump has a known
off-by-one issue (an extra Emerlink name at metadata position 18 that
does not exist in the shipped `D00.DAT`); the role assignments below
use the **real** `D00.DAT` indexing.

## Structural groups

| Entries | Role | Terminator |
| ------- | ---- | ---------- |
| 0–17    | Character name metadata (18 names) | `<$FFFF>` |
| 18–30   | Opening narrative (Lushiris prologue, questionnaire setup) | `<$FFFE>` |
| 31      | "Before we begin" + "Please push the C button" (gift hand-off) | `<$FFFE>` |
| 32–47   | "Great unit" and three "hero quality" question/answer blocks | `<$FFFE>` |
| 48–71   | Six variants of "Which do you enjoy the most?" (wind / breeze) | `<$FFFE>` |
| 72–140  | Character-creation questions with 3-answer triples each | `<$FFFE>` |
| 141–168 | Tutorial Q&A (opt-in prompts and explanation bodies) | `<$FFFE>` |

## Entries 0–17: character names

Eighteen entries, one name each, terminated with `<$FFFF>`. Order is
fixed by the game code — do not reorder.

| Idx | EN           | JP source            |
| --- | ------------ | -------------------- |
| 0   | Diehärte     | ディハルト           |
| 1   | Tiaris       | ティアリス           |
| 2   | Riffany      | リファニー           |
| 3   | Luna         | ルナ                 |
| 4   | Sophia       | ソフィア             |
| 5   | Flaire       | フレア               |
| 6   | Lewin        | ルイン               |
| 7   | Silver Wolf  | シルバー・ウルフ     |
| 8   | Gilbert      | 剣豪ギルバート       |
| 9   | Pierre       | ピエール             |
| 10  | Fauvel       | 賢者ファーベル       |
| 11  | Dios         | ディオス             |
| 12  | Jügler       | 聖獣ジュグラー       |
| 13  | Jessica      | 大魔術師ジェシカ     |
| 14  | Kirikaze     | 霧風                 |
| 15  | Do Kahni     | 勇者ド・カーニ       |
| 16  | Altemüller   | アルテミュラー       |
| 17  | Varna        | ファーナ             |

Title honorifics in JP (剣豪, 賢者, 聖獣, 大魔術師, 勇者) are dropped
in EN. This is an intentional space-saving choice, not a translation
bug.

**Do not** look at `lang3a2/.../jp/scen1.sjs` and conclude a 19th
name (`エマーリンク` / "Emerlink") is missing — that dump is off by
one. See [`gotchas.md`](gotchas.md).

## Entries 18–30: opening narrative

Read sequentially by the game. The order is load-bearing: a reshuffle
breaks the Lushiris dialogue flow. The
`test_scen001_lushiris_prologue_order` canary in
`tests/test_entry_counts.py` pins this order using anchor strings,
and was added specifically because commit `5a27497` silently scrambled
this range.

Narrative beats, in order:

- **18** — "...Young man who wishes to be a knight..." / "...Child
  destined to alter history..." / "Wake up, open your eyes."
- **19** — "My name is Lushiris. / On earth I am the goddess of light."
  (Two lines joined by `<$FFFC>` inside one entry — the JP source
  does the same.)
- **20** — Larcuss prospered under my protection
- **21** — Darkness rises throughout the world
- **22** — Peace will end and an age of unrest is dawning
- **23** — "You are not helpless, nor pawns / I only open paths"
- **24** — "Your heart's desire shapes the world"
- **25** — "I need you to answer some questions"
- **26** — "First of all, tell me your name"
- **27** — "Shall I start from the beginning?" (tutorial restart prompt)
- **28** — Long tutorial-end farewell: mentions hiring mercenaries
- **29** — Short tutorial-end farewell: "I shall expect great deeds"
- **30** — "Answer my questions truthfully"

Entries 28 and 29 are two distinct endings the game selects between.
Both must exist; do not dedupe them.

## Entry 31: gift hand-off

One entry containing two lines joined by `<$FFFC>`:

```
Before we begin, I have a gift for you.<$FFFC>
Please push the C button.<$FFFE>
```

This is the hand-off to the character-creation questionnaire. The "C
button" string is position-sensitive; don't swap it with a
neighbouring entry.

## Entries 32–47: "Key quality" and "hero quality" questions

Four question-and-triple blocks:

- **32** — "What is the key quality of a great unit?"
  - **33 / 34 / 35** — Leadership / Mobility / Destructive power
- **36** — "What is required to become a hero?" (variant 1)
  - **37 / 38 / 39** — Courage / Charisma / Indomitable mind
- **40** — "What is required to become a hero?" (variant 2)
  - **41 / 42 / 43** — Kindness / Courage / Indomitable mind
- **44** — "What is required to become a hero?" (variant 3)
  - **45 / 46 / 47** — Kindness / Charisma / Indomitable mind

The question text **repeats on purpose**. The game selects one of the
three hero-quality variants based on earlier answers and reads the
answer strings from the matching slot range. Merging or deduping the
repeated questions will break the selection logic.

## Entries 48–71: wind/breeze preference

Six variants of "Which of these do you enjoy the most?", each with a
question entry followed by three answer entries. Same structural
rule: do not dedupe variants, do not reorder answers within a triple.

## Entries 72–140: personality and creation questions

Roughly fifteen question blocks, each typically one question entry
plus three answer entries. A couple of them (96 / 100 / 121) are
two-line setups where an extra entry describes the scenario before
the question. Topics covered, in order:

- 72 — Where does God reside?
- 76 — What saves the world from ruin?
- 80 — What do you want in a commanded unit?
- 84 — What should a great army possess? (first option is
  "A commander's own might", matching the JP `己の力` option)
- 88 — What do you seek most in life?
- 92 — What cause will you devote your life to?
- 96 — Enemy surprise attack scenario / "What will you do?"
- 100 — Besieged ally scenario / "What is your command?"
- 105 — If you gained great power, how would you use it?
- 109 — What is love to you?
- 113 — What do you expect from this world?
- 117 — What must a ruler possess?
- 121 — Farewell to lover scenario / "What do you do?"
- 125 — "What defines a man?" (JP `男とは！`)
- 129 — At the start of battle, what do you need most?
- 133 — What do you seek in a unit?
- 137 — Lastly, for what purpose do you fight?

Entry 125 was previously mistranslated as "You are a boy, aren't
you?" with answers phrased as "No, a ..." — this inverted the sense
of the JP rhetorical. Fixed in commit `7e1fca0`.

## Entries 141–168: tutorial Q&A

Twenty-eight entries forming "Shall I explain X?" → long explanation
body pairs, plus the top-level opt-in prompt.

- **141** — Top-level: "Do you need an explanation of the rules?"
- **142 / 143** — Flow of battle (prompt / body)
- **144 / 145** — Prep screen and hiring troops
- **146 / 147** — Battle system (semi-real-time)
- **148 / 149** — Commands (Move / Recover / Magic / Item / Use / Summon)
- **150** — Skill, command combinations, preview of Mode / Formation,
  Execute Turn note
- **151 / 152** — Unit modes (Normal / High Mobility / Defense)
- **153 / 154** — Formations (Square / Spear / Wall / Slant)
- **155 / 156 / 157** — Battle mode (contact, 3D scene, orders)
- **158 / 159** — Affinities (Infantry → Spear → Cavalry cycle,
  Bowmen vs flyers, Monks vs undead, Sailors on water)
- **160 / 161** — Class change concept + feature (two separate prompts)
- **162** — Class change details body
- **163 / 164** — Class upgrades (Divine Blessing / 15 levels)
- **165 / 166** — Experience gain
- **167 / 168** — Useful shortcuts (Y, A, X, B buttons)

Entry 154 (formations) and entry 159 (affinities) had stray glyph
escapes (`ys z`, `ybz`, `y\z`, `y_zy^z`) and untranslated JP layout
markers (`@`) before commit `7e1fca0`, where they were replaced with
plain-text labels and a rewritten opening line.

## Editing checklist for `scen001E.txt`

1. Read [`entry-count-invariant.md`](entry-count-invariant.md) first.
2. Before and after any edit, verify:
   - `parse_script_file` returns exactly **169** entries
   - `pytest -q` passes, including
     `test_entry_counts_match` and
     `test_scen001_lushiris_prologue_order`
   - `python3 build.py` reports `125 sections patched EN, 0 kept JP`
3. If you change the semantic content of entries 18–30 (Lushiris
   prologue), update the anchor list in
   `test_scen001_lushiris_prologue_order` accordingly.
4. Never merge two entries, never split one entry into two, never
   reorder entries across a terminator. Only text *inside* an entry
   is fair game.
