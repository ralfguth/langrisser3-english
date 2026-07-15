"""test_layout_qa_entry_override.py — per-entry layout-profile override.

A MIXED scen (real 12-wide dialogue + ONE stray narration card) needs that one
entry promoted to NARRATION_16X5 without touching the rest. scen113 is the case:
the SC-36 epilogue is the Altemüller/Varna farewell (real DIALOGUE_12X4), but the
lone closing-narration card [77] ("Thus Chaos's revival was prevented…") renders
in the wide 16x5 narration box — the game auto-wraps narration at 16, dialogue at
12 (user 2026-06-23), confirmed by the sibling verified scen124 epilogue bank.
The state machine stays in SCENE_12X4 and mis-bins [77]; a per-scen
``dialogue_profile`` override would wrongly promote the whole farewell, and
``jp_empty_only`` does not apply ([77] is JP-paired). ``entry_overrides`` promotes
ONLY the named index.

Red state (mechanism absent): scen113[77] classifies as DIALOGUE_12X4.
"""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from layout_qa.cli import _process_one  # noqa: E402

EN = PROJ / 'scripts' / 'en'
JP = PROJ / 'scripts' / 'jp'


def _scen113(ovr):
    return _process_one(EN / 'scen113E.txt', {}, scen_overrides=ovr,
                        jp_scripts_dir=JP)


def _profile(scenario, idx):
    return next(e for e in scenario['entries'] if e['index'] == idx)['profile']


def test_entry_override_promotes_only_the_named_entry():
    ovr = {'scen113': {'entry_overrides': {'77': 'NARRATION_16X5'}}}
    scenario = _scen113(ovr)
    assert _profile(scenario, 77) == 'NARRATION_16X5'
    # the farewell dialogue around it stays 12-wide
    assert _profile(scenario, 75) == 'DIALOGUE_12X4'


def test_no_override_leaves_entry_as_dialogue():
    scenario = _scen113({})
    assert _profile(scenario, 77) == 'DIALOGUE_12X4'
