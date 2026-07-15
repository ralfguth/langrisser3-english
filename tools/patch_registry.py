"""tools/patch_registry.py — per-module feature toggle for the patch.

Every owned patch the build applies has a stable NAME and is ENABLED by default.
To disable one for a build, add its name to ``DISABLED_MODULES`` below — or pass
it via the ``LANG3_DISABLE`` env var (comma-separated) for a one-off build
without editing this file. Default (empty) = every module on = byte-identical to
a normal full build.

Why: each owned patch is a closed-scope module (feedback_patch_per_module_closed_scope),
so each can be turned off independently. Two uses:
  * Playtest debugging — isolate a rendering regression by disabling the
    suspect module and rebuilding (e.g. LANG3_DISABLE=prog6_battle_cmd_width).
  * Comparison builds — disable everything to ship a JP-baseline build, or
    disable just the geometry modules to A/B the layout.

Module names
------------
ENGINE_PATCH_MODULES — the owned SH-2/geometry/glue byte-patch modules and the
PROG_3 text-table encoder (prog3_text_tables = prog_text_tools.encoded_overlays:
magic + skill name tables + the skill pointer redirect).

TEXT_ENCODER_MODULES — the whole-file regenerators:
  font     = generate_english_font (FONT.BIN glyphs)
  scen_d00 = insert_translations / rebuild_d00 (LANG/SCEN/D00.DAT dialogue)
  fntsys   = encode_fntsys (FNT_SYS.BIN UI string table)
  syswin   = encode_syswin (SYSWIN.BIN battle-window strings)
  plot     = encode_plot_script (PLOT.DAT chapter recaps)

Disabling a TEXT_ENCODER module ships that file as JP (mojibake / Japanese), so a
full disable set produces an effectively-Japanese build — useful for diffing.
"""

import os

# ---------------------------------------------------------------------------
# THE DISABLE LIST — the only thing you normally edit.
# Empty = every module on (byte-identical full build). Add names to skip them.
# Example: DISABLED_MODULES = {"prog6_battle_cmd_width", "prog5_menu_geometry"}
# ---------------------------------------------------------------------------
DISABLED_MODULES: set[str] = set()

ENGINE_PATCH_MODULES = (
    "prog3_nameplate_new_line",
    "prog3_statup_template",
    "prog3_item_use_glue",
    "prog4_field_box_geometry",
    "prog4_equip_title",
    "prog4_spell_name_table",
    "prog4_menu_geometry",
    "prog5_menu_geometry",
    "prog6_battle_cmd_width",
    "a0lang_options_menu_geometry",
    "a0lang_title_menu_geometry",
    "a0lang_loadsave_title",
    "a0lang_item_action_box",
    "prog3_text_tables",
)

TEXT_ENCODER_MODULES = (
    "font",
    "scen_d00",
    "fntsys",
    "syswin",
    "plot",
)

# ASSET_MODULES — prebuilt binary assets injected into the ISO (not encoded from
# text at build time). Each is optional: if its asset file is absent the build
# falls back to the JP original.
#   movie = LANG/LANG.CPK opening FMV (English-subtitled, see tools/movie_tools.py)
# NOTE: the title-screen patch-author credit (LANG/TITLE.DG2, tools/title_dg2.py)
# is deliberately NOT a module here. It is MANDATORY and hardwired into build.py:
# every build embeds the credit and the build aborts if it cannot, so there is no
# toggle that could disable it.
ASSET_MODULES = (
    "movie",
)

ALL_MODULES = ENGINE_PATCH_MODULES + TEXT_ENCODER_MODULES + ASSET_MODULES

_ENV_VAR = "LANG3_DISABLE"


def _env_disabled() -> set[str]:
    raw = os.environ.get(_ENV_VAR, "")
    return {n.strip() for n in raw.split(",") if n.strip()}


def disabled_modules() -> set[str]:
    """Effective disable set: the config list plus any LANG3_DISABLE env names."""
    return set(DISABLED_MODULES) | _env_disabled()


def is_enabled(name: str) -> bool:
    """True unless `name` is in the effective disable set."""
    return name not in disabled_modules()


def validate(disabled: set[str]) -> set[str]:
    """Return any names in `disabled` that are not real module names (typo guard)."""
    return set(disabled) - set(ALL_MODULES)
