"""test_patch_registry.py — the per-module feature toggle.

Every owned patch (engine byte-patch module, text encoder, the font) has a
stable name and is ENABLED by default. The toggle is a disable-list: empty by
default (all modules on -> byte-identical to a full build), names added to it (or
to the LANG3_DISABLE env var) are skipped by build.py.

This pins the toggle semantics; tests/test_build_module_toggle.py pins that
build.py actually honours it.
"""

import importlib
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import patch_registry as reg


def test_default_disabled_is_empty():
    """Default config = no modules disabled = byte-identical full build."""
    assert reg.DISABLED_MODULES == set()


def test_all_modules_covers_engine_and_text_no_dups():
    assert (set(reg.ENGINE_PATCH_MODULES) | set(reg.TEXT_ENCODER_MODULES)
            | set(reg.ASSET_MODULES)) == set(reg.ALL_MODULES)
    assert len(reg.ALL_MODULES) == len(set(reg.ALL_MODULES)), "duplicate module name"
    # the carved + pre-existing engine modules, the text encoders, and the
    # asset modules are all named
    for name in ("prog6_battle_cmd_width", "prog5_menu_geometry",
                 "prog4_menu_geometry", "prog4_spell_name_table",
                 "prog3_text_tables", "font", "scen_d00", "fntsys",
                 "syswin", "plot", "movie"):
        assert name in reg.ALL_MODULES, f"{name} not registered"


def test_is_enabled_default_true():
    for name in reg.ALL_MODULES:
        assert reg.is_enabled(name)


def test_is_enabled_false_when_in_disabled_set(monkeypatch):
    monkeypatch.setattr(reg, "DISABLED_MODULES", {"prog6_battle_cmd_width"})
    assert not reg.is_enabled("prog6_battle_cmd_width")
    assert reg.is_enabled("prog5_menu_geometry")


def test_env_var_merges_into_disabled(monkeypatch):
    monkeypatch.setenv("LANG3_DISABLE", "fntsys, plot ")
    assert reg.disabled_modules() >= {"fntsys", "plot"}
    assert not reg.is_enabled("fntsys")
    assert not reg.is_enabled("plot")


def test_validate_flags_unknown_names():
    assert reg.validate({"prog6_battle_cmd_width"}) == set()
    assert reg.validate({"not_a_real_module"}) == {"not_a_real_module"}
