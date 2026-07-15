#!/usr/bin/env python3
"""test_polish_order.py — the walkthrough polish order must cover every scen.

The order that drives the 100% polish pass is the player's walkthrough sequence
(character creation -> each scenario's intro/battle/post cutscene, secret stages
interleaved at their unlock points -> endings). The one invariant that matters:
**every scen file is in the order exactly once** — so the polish pass cannot
silently skip a scen (which would leave the "100%" incomplete).
"""

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

from polish_order import build_order, all_scens_in_order  # noqa: E402

EXISTING = {p.stem[:-1] if p.stem.lower().endswith('e') else p.stem
            for p in (PROJ / 'scripts' / 'en').glob('scen*E.txt')}


def test_order_covers_every_scen_exactly_once():
    scens = all_scens_in_order()
    assert len(scens) == len(set(scens)), 'a scen appears twice in the order'
    assert set(scens) == EXISTING, (
        'order does not match the scen files exactly:\n'
        f'  missing from order: {sorted(EXISTING - set(scens))}\n'
        f'  in order but no file: {sorted(set(scens) - EXISTING)}')


def test_secret_stage_battles_present():
    scens = set(all_scens_in_order())
    for sid in ('scen038', 'scen039', 'scen040', 'scen041'):
        assert sid in scens


def test_creation_first_then_scenario_one_then_endings_last():
    scens = all_scens_in_order()
    # creation quiz before Sc01 battle; Sc01 battle before Sc02 battle; endings last
    assert scens.index('scen001') < scens.index('scen002') < scens.index('scen003')
    # Sc01 intro cutscene precedes its battle
    assert scens.index('scen042') < scens.index('scen002')
    assert scens[-1] == 'scen125'


def test_secret_stage_one_falls_after_scenario_four():
    scens = all_scens_in_order()
    # ?1 (battle scen038) unlocks after Sc04 (battle scen005) and before Sc05 (scen006)
    assert scens.index('scen005') < scens.index('scen038') < scens.index('scen006')


def test_build_order_sections_have_titles_and_items():
    order = build_order()
    assert order and all(sec.get('title') for sec in order)
    assert all('scen' in it and 'role' in it
               for sec in order for it in sec['items'] if 'scen' in it)
