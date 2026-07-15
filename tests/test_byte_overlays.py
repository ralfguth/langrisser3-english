"""test_byte_overlays.py — sanity check static BYTE_OVERLAYS vs the JP baseline.

This is **scaffolding only**, valid while binaries are still shipped as raw
inherited byte deltas (prog_4, prog_5, prog_6, syswin, plus the residual
prog_3 runs). Project direction is to disembark each into a self-documenting
engine-patch module or script-driven encoder we own
(feedback_patch_per_module_closed_scope); when a binary is disembarked its
overlay shrinks/disappears here and its own module test takes over (e.g.
tools/prog3_nameplate_new_line.py -> tests/test_prog3_nameplate_new_line.py).

History: until 2026-06-10 this file compared overlays against
archive/v02_baseline/*.bin copies. That archive was deleted (the 0.2 patch
reference is the 'English Menus v0.2' ISO, forensic only), so the checks
were ported to the live JP baseline (roadmap T02): every overlay run must
lie inside its target file, and every target must actually CHANGE the JP
bytes (an all-no-op overlay means the offsets drifted or the patch is dead).
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

from iso_tools import build_file_index, extract_file_data
import build as build_module


JP_ENV = "LANG3_JP_DIR"


@pytest.fixture(scope="module")
def jp_image():
    jp_dir = os.environ.get(JP_ENV)
    if not jp_dir:
        pytest.skip(f"{JP_ENV} env var not set")
    candidates = list(Path(jp_dir).glob("*rack*01*.bin")) or \
                 list(Path(jp_dir).glob("*rack*1*.bin")) or \
                 list(Path(jp_dir).glob("*.bin"))
    if not candidates:
        pytest.skip(f"no Track 01 .bin in {jp_dir}")
    return candidates[0].read_bytes()


@pytest.fixture(scope="module")
def jp_index(jp_image):
    return build_file_index(jp_image)


@pytest.mark.parametrize("iso_path", sorted(build_module.BYTE_OVERLAYS))
def test_overlay_runs_lie_inside_target_file(jp_image, jp_index, iso_path):
    """Every (offset, chunk) run must fit within the JP file it patches.
    An out-of-range run means the offset table drifted (wrong binary,
    wrong baseline, or a typo'd offset) and would corrupt the build."""
    entry = jp_index.get(iso_path)
    assert entry is not None, f"{iso_path} not in JP ISO"

    for off, chunk in build_module.BYTE_OVERLAYS[iso_path]:
        if isinstance(chunk, int):
            chunk = bytes([chunk])
        assert 0 <= off and off + len(chunk) <= entry.size, (
            f"{iso_path} overlay run [0x{off:08X}:0x{off + len(chunk):08X}] "
            f"exceeds file size 0x{entry.size:08X}"
        )


def test_prog7_ships_jp_verbatim():
    """DECISION (T10, archive/docs/20260610_prog7_forensics.md): the 7
    0.2 patch-v0.2 bytes in PROG_7 retarget descriptors at byte-identical
    PROG_3 code (prologue-skip) and edit a code list — 0.2 patch-runtime
    machinery, not text. We ship PROG_7 exactly as JP; nothing may
    overlay it without reopening that RE."""
    from prog3_nameplate_new_line import PROG3_NAMEPLATE_NEW_LINE
    from prog3_statup_template import PROG3_STATUP_TEMPLATE
    from a0lang_options_menu_geometry import A0LANG_OPTIONS_MENU_GEOMETRY
    sources = {"BYTE_OVERLAYS": build_module.BYTE_OVERLAYS,
               "nameplate": PROG3_NAMEPLATE_NEW_LINE,
               "statup": PROG3_STATUP_TEMPLATE,
               "options_geometry": A0LANG_OPTIONS_MENU_GEOMETRY}
    offenders = [name for name, src in sources.items()
                 if "LANG/PROG_7.BIN" in src]
    assert not offenders, (
        f"PROG_7 must ship JP-verbatim (T10 decision); patched by: {offenders}"
    )


@pytest.mark.parametrize("iso_path", sorted(build_module.BYTE_OVERLAYS))
def test_overlay_changes_jp_bytes(jp_image, jp_index, iso_path):
    """Each overlay target must differ from the JP baseline in at least one
    patched byte. If applying the overlay reproduces JP exactly, the patch
    is dead weight (or the offsets silently drifted to a no-op region)."""
    entry = jp_index.get(iso_path)
    assert entry is not None, f"{iso_path} not in JP ISO"

    jp_bytes = extract_file_data(jp_image, entry.extent, entry.size)
    changed = 0
    for off, chunk in build_module.BYTE_OVERLAYS[iso_path]:
        if isinstance(chunk, int):
            chunk = bytes([chunk])
        if jp_bytes[off:off + len(chunk)] != chunk:
            changed += 1
    assert changed > 0, (
        f"{iso_path}: no overlay run changes the JP baseline — dead patch "
        f"or drifted offsets"
    )
