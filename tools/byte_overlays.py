"""tools/byte_overlays.py — owned byte patches over JP binaries (DISEMBARK COMPLETE).

This dict used to carry the raw byte-level deltas inherited from the third-party
0.2 patch. As of 2026-06-14 the disembark is COMPLETE: every inherited byte run
has been reverse-engineered and carved into a self-documenting engine-patch
module (feedback_patch_per_module_closed_scope), so `BYTE_OVERLAYS` is now empty.

build.py still imports `BYTE_OVERLAYS` and merges it with the per-module overlays;
keeping it as an empty dict preserves that wiring and the test scaffolding
(tests/test_byte_overlays.py) without shipping any opaque inherited bytes.

Where each binary's patches now live
------------------------------------
- LANG/PROG_3.BIN — magic/skill name tables + skill pointer redirect:
  tools/prog_text_tools.py (encoders, script-driven); nameplate newline:
  tools/prog3_nameplate_new_line.py; stat-up glue: tools/prog3_statup_template.py;
  item-use の-glue: tools/prog3_item_use_glue.py.
- LANG/PROG_4.BIN — magic-icon spell-name TEXT table (declared byte-identical,
  Phase-B re-encode pending): tools/prog4_spell_name_table.py; field 2x2 command
  box: tools/prog4_field_box_geometry.py; equip-title repoint:
  tools/prog4_equip_title.py; all remaining menu display-list geometry:
  tools/prog4_menu_geometry.py.
- LANG/PROG_5.BIN — menu display-list geometry: tools/prog5_menu_geometry.py.
- LANG/PROG_6.BIN — in-battle command-box widths: tools/prog6_battle_cmd_width.py.
- LANG/PROG_7.BIN — ships JP-verbatim (T10 decision, archive/docs/20260610_prog7_forensics.md).
- A0LANG.BIN — OPTIONS menu geometry: tools/a0lang_options_menu_geometry.py;
  item-action box: tools/a0lang_item_action_box.py.
"""

# Disembark complete — no inherited byte runs remain. (Do not re-add opaque
# deltas here; carve any new engine patch into its own RE'd module instead.)
BYTE_OVERLAYS: dict[str, list[tuple[int, bytes]]] = {}
