r"""classifier.py — assign a layout profile to each entry.

State machine drives the classification across an entire scen file:

    INITIAL_LABELS  ──FFFE+SCENARIO_PATTERN──►  SCENARIO_INTRO_16X5  (this entry = NARRATION_16X5)
    INITIAL_LABELS  ──FFFE+BULLET───────────►  OBJECTIVES_16X5      (this entry = OBJECTIVE_16X5)
    INITIAL_LABELS  ──FFFE (no marker)──────►  SCENE_12X4           (this entry = DIALOGUE_12X4; the last FFFF was the location label)
    INITIAL_LABELS  ──FFFF──────────────────►  (stay) LABEL_12X1
    SCENARIO_INTRO_16X5  ──FFFF─────────────►  SCENE_12X4 (label first)
    SCENARIO_INTRO_16X5  ──FFFE─────────────►  (stay) NARRATION_16X5
    OBJECTIVES_16X5  ──FFFF─────────────────►  SCENE_12X4 (label first)
    OBJECTIVES_16X5  ──FFFE+BULLET──────────►  (stay) OBJECTIVE_16X5
    SCENE_12X4  ──FFFE──────────────────────►  (stay) DIALOGUE_12X4
    SCENE_12X4  ──FFFF──────────────────────►  (stay) LABEL_12X1
    any  ──unmatched────────────────────────►  UNKNOWN  (→ error)

The "no marker" transition out of INITIAL_LABELS handles scens that
go straight from the character/location nameplates into dialogue —
common in continuation scenes that don't carry a new SCENARIO header
or objective list.

Profile names match the spec (`LABEL_12X1`, `OBJECTIVE_16X5`,
`NARRATION_16X5`, `DIALOGUE_12X4`, `UNKNOWN`). Confidences and
reasons live in `config/classifier-rules.json`; the rule set passed
to `classify_entries` is what selects them.

The bullet detector is `^\s*[•*]` against the entry's concatenated
visible text (text segments only — control codes and tokens excluded).
The SCENARIO detector is the existing
`tools/center_scenario_titles.py:SCENARIO_PATTERN`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from center_scenario_titles import SCENARIO_PATTERN  # noqa: E402
from layout_qa.parser import Entry  # noqa: E402


BULLET_PATTERN = re.compile(r'^\s*[•*]')


class ClassifierState(Enum):
    INITIAL_LABELS = 'INITIAL_LABELS'
    SCENARIO_INTRO_16X5 = 'SCENARIO_INTRO_16X5'
    OBJECTIVES_16X5 = 'OBJECTIVES_16X5'
    SCENE_12X4 = 'SCENE_12X4'


# Profile names.
# Two LABEL variants because rendering area + budget differ:
#   - CHARACTER nameplates render in the 12-tile dialog balloon. Hard
#     limit 12 (proven by 'Field Marshal Altemüller' = 12 tiles exact).
#   - LOCATION titles introduce a cutscene or battle and render in a
#     wider area: technically up to 16 tiles, but visually unpolished
#     past ~12. The simulator treats >12 as warning, >16 as error.
LABEL_CHARACTER_12X1 = 'LABEL_CHARACTER_12X1'
LABEL_LOCATION_16X1 = 'LABEL_LOCATION_16X1'
OBJECTIVE_16X5 = 'OBJECTIVE_16X5'
NARRATION_16X5 = 'NARRATION_16X5'
DIALOGUE_12X4 = 'DIALOGUE_12X4'
UNKNOWN = 'UNKNOWN'


@dataclass
class Classification:
    """One entry's assigned layout profile + provenance.

    `semantic_subtype` further qualifies LABEL_12X1 entries into
    `CHARACTER_NAME` (nameplate in the initial roster) vs `LOCATION`
    (the location title — last FFFF of the initial block, or any
    mid-file FFFF inside SCENE_12X4). For non-LABEL profiles it is
    None. The simulator doesn't use this — it's metadata for the
    reporter / human reviewer.
    """
    profile: str
    confidence: float
    reason: str
    state: str   # the state IN WHICH this entry was classified
    semantic_subtype: str | None = None


# Default rule table — used when no external `config/classifier-rules.json`
# is provided. Keys correspond to the transitions described in the docstring.
DEFAULT_RULES: Dict[str, Dict[str, float | str]] = {
    'INITIAL_LABEL_CHARACTER': {
        'confidence': 1.0,
        'reason': 'FFFF with next entry also FFFF — nameplate in roster',
    },
    'INITIAL_LABEL_LOCATION': {
        'confidence': 0.95,
        'reason': 'last FFFF before first FFFE — location title',
    },
    'INITIAL_SCENARIO': {
        'confidence': 0.95,
        'reason': 'SCENARIO marker matched at first FFFE entry',
    },
    'INITIAL_OBJECTIVE': {
        'confidence': 0.9,
        'reason': 'bullet prefix at first FFFE entry',
    },
    'INITIAL_TO_SCENE_DIALOGUE': {
        'confidence': 0.85,
        'reason': 'FFFE with no SCENARIO/bullet — assumed dialogue (last FFFF was location)',
    },
    'INTRO_NARRATION': {
        'confidence': 0.9,
        'reason': 'FFFE entry inside SCENARIO_INTRO_16X5 state',
    },
    'SCENE_SCENARIO': {
        'confidence': 0.95,
        'reason': 'SCENARIO marker recurring mid-scene — 16-wide title screen',
    },
    'INTRO_TO_SCENE_LOCATION': {
        'confidence': 0.95,
        'reason': 'first FFFF after SCENARIO intro = location label',
    },
    'OBJECTIVE_REPEAT': {
        'confidence': 0.9,
        'reason': 'bullet prefix inside OBJECTIVES_16X5 state',
    },
    'OBJECTIVE_TO_SCENE_LOCATION': {
        'confidence': 0.95,
        'reason': 'first FFFF after objectives = location label',
    },
    'SCENE_DIALOGUE': {
        'confidence': 0.9,
        'reason': 'FFFE entry inside SCENE_12X4 state',
    },
    'SCENE_LOCATION': {
        'confidence': 0.9,
        'reason': 'FFFF entry inside SCENE_12X4 state (mid-file location)',
    },
    'UNKNOWN': {
        'confidence': 0.0,
        'reason': 'no transition matched',
    },
}


def visible_text(entry: Entry) -> str:
    """Concatenate just the text segments — control codes and tokens excluded."""
    return ''.join(s.value for s in entry.segments if s.kind == 'text')


def _is_bullet(entry: Entry) -> bool:
    return bool(BULLET_PATTERN.match(visible_text(entry)))


def _has_scenario_marker(entry: Entry) -> bool:
    # SCENARIO_PATTERN was built to match the canonical wrap-around
    # form. For a single entry it suffices to .search() over the raw.
    return SCENARIO_PATTERN.search(entry.raw) is not None


def _rule(rules: Dict, key: str) -> Dict:
    if key not in rules:
        return DEFAULT_RULES[key]
    return rules[key]


def _classify_one(
    entry: Entry,
    state: ClassifierState,
    rules: Dict,
    next_entry: Entry | None,
) -> tuple[Classification, ClassifierState]:
    """Classify a single entry and return (Classification, next_state).

    `next_entry` is the FOLLOWING entry (or None if this is the last).
    Used to disambiguate character-name vs location LABEL inside
    INITIAL_LABELS by peeking at the next terminator AND its semantic
    markers (SCENARIO/bullet).
    """
    term = entry.terminator
    next_terminator = next_entry.terminator if next_entry else None

    def _cls(profile, rule_key, next_state, subtype=None):
        r = _rule(rules, rule_key)
        return (
            Classification(
                profile=profile,
                confidence=r['confidence'],
                reason=r['reason'],
                state=state.value,
                semantic_subtype=subtype,
            ),
            next_state,
        )

    # INITIAL_LABELS
    if state == ClassifierState.INITIAL_LABELS:
        if term == 'FFFF':
            # Lookahead: if the NEXT entry is also FFFF, this is still
            # in the character-name roster. If next is FFFE AND that
            # FFFE has no SCENARIO/bullet marker, this FFFF is the
            # trailing LOCATION label (e.g. "City of Laffel"). If the
            # next FFFE is a SCENARIO or objective bullet, this FFFF
            # is still a CHARACTER nameplate — the real location label
            # appears AFTER the intro/objective block.
            if next_terminator == 'FFFF':
                return _cls(LABEL_CHARACTER_12X1, 'INITIAL_LABEL_CHARACTER',
                            ClassifierState.INITIAL_LABELS,
                            subtype='CHARACTER_NAME')
            if next_terminator == 'FFFE' and next_entry is not None:
                if _has_scenario_marker(next_entry) or _is_bullet(next_entry):
                    # The trailing FFFF is still a character — real
                    # location comes after the intro/objectives block.
                    return _cls(LABEL_CHARACTER_12X1, 'INITIAL_LABEL_CHARACTER',
                                ClassifierState.INITIAL_LABELS,
                                subtype='CHARACTER_NAME')
            # next is FFFE without marker / None — this is the location.
            return _cls(LABEL_LOCATION_16X1, 'INITIAL_LABEL_LOCATION',
                        ClassifierState.INITIAL_LABELS,
                        subtype='LOCATION')
        if term == 'FFFE':
            if _has_scenario_marker(entry):
                return _cls(NARRATION_16X5, 'INITIAL_SCENARIO',
                            ClassifierState.SCENARIO_INTRO_16X5)
            if _is_bullet(entry):
                return _cls(OBJECTIVE_16X5, 'INITIAL_OBJECTIVE',
                            ClassifierState.OBJECTIVES_16X5)
            return _cls(DIALOGUE_12X4, 'INITIAL_TO_SCENE_DIALOGUE',
                        ClassifierState.SCENE_12X4)
        return _cls(UNKNOWN, 'UNKNOWN', state)

    # SCENARIO_INTRO_16X5
    if state == ClassifierState.SCENARIO_INTRO_16X5:
        if term == 'FFFF':
            return _cls(LABEL_LOCATION_16X1, 'INTRO_TO_SCENE_LOCATION',
                        ClassifierState.SCENE_12X4, subtype='LOCATION')
        if term == 'FFFE':
            return _cls(NARRATION_16X5, 'INTRO_NARRATION',
                        ClassifierState.SCENARIO_INTRO_16X5)
        return _cls(UNKNOWN, 'UNKNOWN', state)

    # OBJECTIVES_16X5
    if state == ClassifierState.OBJECTIVES_16X5:
        if term == 'FFFF':
            return _cls(LABEL_LOCATION_16X1, 'OBJECTIVE_TO_SCENE_LOCATION',
                        ClassifierState.SCENE_12X4, subtype='LOCATION')
        if term == 'FFFE':
            return _cls(OBJECTIVE_16X5, 'OBJECTIVE_REPEAT',
                        ClassifierState.OBJECTIVES_16X5)
        return _cls(UNKNOWN, 'UNKNOWN', state)

    # SCENE_12X4
    if state == ClassifierState.SCENE_12X4:
        # A SCENARIO title can recur mid-scene (e.g. scen068/scen110): it
        # opens a fresh scenario briefing — title → recap narration →
        # objectives — exactly as at file start. So enter the intro state,
        # not stay in SCENE: the briefing BODY renders in the 16-wide region
        # too, never the 12x4 dialog balloon. A following FFFF location label
        # returns to SCENE_12X4. (Verified: the only two corpus cases both
        # run title→narration→objectives→EOF, never title→dialogue.)
        if term == 'FFFE' and _has_scenario_marker(entry):
            return _cls(NARRATION_16X5, 'SCENE_SCENARIO',
                        ClassifierState.SCENARIO_INTRO_16X5)
        if term == 'FFFE':
            return _cls(DIALOGUE_12X4, 'SCENE_DIALOGUE',
                        ClassifierState.SCENE_12X4)
        if term == 'FFFF':
            return _cls(LABEL_LOCATION_16X1, 'SCENE_LOCATION',
                        ClassifierState.SCENE_12X4, subtype='LOCATION')
        return _cls(UNKNOWN, 'UNKNOWN', state)

    # Safety net — should never hit
    return _cls(UNKNOWN, 'UNKNOWN', state)


def classify_entries(
    entries: List[Entry],
    rules: Dict | None = None,
    scen_overrides: Dict[str, Dict] | None = None,
) -> List[Classification]:
    """Walk a list of entries (assumed in order, all from the same scen
    or spanning multiple scens — the state resets at no boundary; the
    caller is expected to pass entries from ONE scen file at a time).

    `scen_overrides` maps a scen id (e.g. 'scen124') to a dict with at
    minimum `dialogue_profile`: a profile name that replaces
    DIALOGUE_12X4 for every entry of that scen. FFFF labels are NOT
    overridden. Used for one-off scens whose narration body renders in
    a different region than the standard dialog balloon (verified via
    in-game playtest). Unmatched scen ids are no-ops.
    """
    if rules is None:
        rules = DEFAULT_RULES
    overrides = scen_overrides or {}
    state = ClassifierState.INITIAL_LABELS
    out: List[Classification] = []
    for i, entry in enumerate(entries):
        next_entry = entries[i + 1] if i + 1 < len(entries) else None
        classification, state = _classify_one(entry, state, rules, next_entry)
        override = overrides.get(entry.scen_id)
        if (
            override is not None
            and classification.profile == DIALOGUE_12X4
            and 'dialogue_profile' in override
            # jp_empty_only overrides are applied downstream (cli.py), where the
            # paired JP is available — only the JP-empty (narration) entries of a
            # MIXED scen get the narration profile; its dialogues stay 12x4.
            and not override.get('jp_empty_only')
        ):
            new_profile = override['dialogue_profile']
            classification = Classification(
                profile=new_profile,
                confidence=classification.confidence,
                reason=(
                    f'{classification.reason} → overridden to {new_profile} '
                    f'per config/layout-overrides.json[{entry.scen_id}]'
                ),
                state=classification.state,
                semantic_subtype=classification.semantic_subtype,
            )
        # Label remap: for one-off scens whose FFFF block is a pure
        # CHARACTER roster with NO trailing LOCATION label (scen001's
        # name-entry roster runs straight into goddess narration). The
        # generic state machine peeks the following FFFE-no-marker and
        # mis-types the last roster name as LOCATION; `label_profile`
        # pins every FFFF label to the configured profile. FFFE bodies
        # are untouched here.
        if (
            override is not None
            and entry.terminator == 'FFFF'
            and 'label_profile' in override
            and classification.profile
            in (LABEL_CHARACTER_12X1, LABEL_LOCATION_16X1)
            and classification.profile != override['label_profile']
        ):
            new_label = override['label_profile']
            classification = Classification(
                profile=new_label,
                confidence=classification.confidence,
                reason=(
                    f'{classification.reason} → label remapped to '
                    f'{new_label} per config/layout-overrides.json'
                    f'[{entry.scen_id}]'
                ),
                state=classification.state,
                semantic_subtype=(
                    'CHARACTER_NAME'
                    if new_label == LABEL_CHARACTER_12X1
                    else classification.semantic_subtype
                ),
            )
        out.append(classification)
    return out
