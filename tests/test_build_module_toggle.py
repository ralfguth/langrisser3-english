"""test_build_module_toggle.py — build.py honours the per-module feature toggle.

Pins that:
  * with nothing disabled, the assembled engine overlay is byte-identical to
    merging every engine module (the default = full build invariant);
  * engine modules never write the same offset, so the merge is order-
    independent (toggling one can't shift another's bytes);
  * disabling a module removes exactly its runs;
  * the build's engine-module names line up with the registry.
"""

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

import build as B            # noqa: E402
import patch_registry as reg  # noqa: E402


def _merge(dicts):
    out = {}
    for d in dicts:
        for path, edits in d.items():
            out.setdefault(path, []).extend(edits)
    return out


def test_engine_overlays_default_equals_all():
    """Nothing disabled -> identical to merging every engine module dict."""
    expected = _merge(B.ENGINE_MODULE_DICTS.values())
    assert B.engine_overlays(set()) == expected


def test_engine_module_names_match_registry():
    """Every ENGINE_MODULE_DICTS key is a registered engine-patch module; the
    only registry engine name not here is the encoder 'prog3_text_tables'."""
    assert set(B.ENGINE_MODULE_DICTS) == set(reg.ENGINE_PATCH_MODULES) - {"prog3_text_tables"}


def test_no_overlapping_offsets_across_engine_modules():
    """No two engine modules touch the same byte -> merge order is irrelevant,
    so toggling one module cannot change another's output."""
    seen = {}
    for name, d in B.ENGINE_MODULE_DICTS.items():
        for path, edits in d.items():
            for off, chunk in edits:
                for b in range(off, off + len(chunk)):
                    key = (path, b)
                    assert key not in seen, (
                        f"{name} overlaps {seen[key]} at {path}:0x{b:05X}"
                    )
                    seen[key] = name


def test_disabling_a_module_removes_exactly_its_runs():
    full = B.engine_overlays(set())
    without = B.engine_overlays({"prog6_battle_cmd_width"})
    p6 = B.ENGINE_MODULE_DICTS["prog6_battle_cmd_width"]["LANG/PROG_6.BIN"]
    # PROG_6 only carried prog6 runs -> its key disappears entirely
    assert "LANG/PROG_6.BIN" in full
    assert "LANG/PROG_6.BIN" not in without
    # other files untouched
    assert without.get("LANG/PROG_4.BIN") == full.get("LANG/PROG_4.BIN")
    assert len(p6) == 3


def test_disabling_all_engine_modules_yields_empty():
    assert B.engine_overlays(set(B.ENGINE_MODULE_DICTS)) == {}
