"""test_disembark_gate.py — the disembark gate must count the REAL debt.

The naming/forensic gate (`disembark_inventory.py`) reported score 0 while
`tools/byte_overlays.py` still shipped 305 un-RE'd inherited byte runs
(PROG_3/4/5/6). That made "score 0" a lie: the last block of the disembark —
the opaque byte overlays — was invisible to the meter.

This pins two invariants:

1. **Honest score** — the inventory score folds in the byte_overlays residual,
   so the gate only reaches 0 when every inherited byte run has been carved
   into a self-documenting engine-patch module (or a named declared text
   module) and removed from byte_overlays
   (feedback_patch_per_module_closed_scope).

2. **Monotonic ratchet** — the residual run count only goes DOWN. Re-adding an
   opaque overlay (or a disembark regression) fails the suite. Lower the
   baseline as overlays are carved out; never raise it.

Red state (pre-fix, 2026-06-14): render_report() returned score 0 with 305
residual runs present.
"""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

import build as build_module           # noqa: E402
import disembark_inventory             # noqa: E402


# Frozen 2026-06-14: DISEMBARK COMPLETE. byte_overlays is empty -> 0 inherited
# runs. This must stay 0; any non-zero means an opaque overlay was re-added.
# Carved: PROG_6 -> prog6_battle_cmd_width.py; PROG_3 -> prog_text_tools.py;
# PROG_4 magic-name -> prog4_spell_name_table.py; PROG_5 -> prog5_menu_geometry.py;
# PROG_4 geometry -> prog4_menu_geometry.py.
RESIDUAL_BASELINE = 0


def _residual_runs() -> int:
    return sum(len(v) for v in build_module.BYTE_OVERLAYS.values())


def test_gate_counts_byte_overlays_residual():
    """The gate score must include the byte_overlays residual. Red: score was
    0 while 305 inherited runs were still shipped — the meter ignored them."""
    residual = _residual_runs()
    _report, score = disembark_inventory.render_report()
    assert score >= residual, (
        f"disembark gate score {score} ignores {residual} byte_overlays "
        f"residual run(s) — the gate is lying about the real debt"
    )


def test_byte_overlays_residual_ratchet():
    """Monotonic: the inherited-byte-run count only goes down. If this fails
    with residual > baseline, an opaque overlay was re-added (regression). If
    residual drops below baseline, lower RESIDUAL_BASELINE to lock the gain."""
    residual = _residual_runs()
    assert residual <= RESIDUAL_BASELINE, (
        f"byte_overlays residual grew to {residual} (baseline "
        f"{RESIDUAL_BASELINE}) — disembark regressed"
    )


def test_gate_reaches_zero_only_when_overlays_empty():
    """Disembark is complete (score 0) ONLY when byte_overlays is empty AND the
    naming/forensic categories are clean. Guards against a future edit that
    zeroes the score while overlays remain."""
    _report, score = disembark_inventory.render_report()
    if _residual_runs() > 0:
        assert score > 0, (
            "score is 0 but byte_overlays still has residual runs — the gate "
            "must not report a complete disembark while overlays remain"
        )
