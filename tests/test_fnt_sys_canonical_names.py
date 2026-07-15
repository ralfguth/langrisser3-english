"""Canonical character-name forms in the LIVE fntsys scripts.

The FNT_SYS strings are built from scripts/en/fntsysNE.txt every build
(encode_fntsys). Name canon lives in lang3_local_docs/NAMES AND TERMS.txt;
script variants are fixed on sight, never the table.

History: this file previously validated the archived 0.2 patch-era blob
(archive/v02_baseline/fnt_sys.bin) "for posterity". That archive was
deleted (0.2 patch reference = the 'English Menus v0.2' ISO, forensic only),
and the pipeline is script-driven now, so the invariant moved to the
scripts themselves (2026-06-10, roadmap T02). Extend NAME_RENAMES as the
T05 name-accuracy sweep (fntsys4/10/11) lands.
"""

import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts" / "en"

# (obsolete_form, canonical_form, expected_min_occurrences_of_canonical)
NAME_RENAMES = [
    ("Dieharte",   "Diehärte",   1),   # protagonist default name
    ("Altemuller", "Altemüller", 1),   # field marshal
    ("Bozel",      "Böser",      1),   # demon overlord
    ("Riguler",    "Rigüler",    1),   # empire name
]


@pytest.fixture(scope="module")
def fntsys_text() -> str:
    files = sorted(SCRIPTS_DIR.glob("fntsys*E.txt"))
    if not files:
        pytest.skip(f"no fntsys*E.txt under {SCRIPTS_DIR}")
    assert len(files) == 15, f"expected 15 fntsys scripts, found {len(files)}"
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


class TestFntSysCanonicalNames:
    """The shipped fntsys scripts must contain only canonical name forms."""

    @pytest.mark.parametrize("old,new,min_new_count", NAME_RENAMES)
    def test_old_form_absent(self, old, new, min_new_count, fntsys_text):
        count = fntsys_text.count(old)
        assert count == 0, (
            f"fntsys scripts still contain {count} occurrence(s) of obsolete "
            f"{old!r}; canonical form is {new!r} (NAMES AND TERMS.txt)"
        )

    @pytest.mark.parametrize("old,new,min_new_count", NAME_RENAMES)
    def test_new_form_present(self, old, new, min_new_count, fntsys_text):
        count = fntsys_text.count(new)
        assert count >= min_new_count, (
            f"fntsys scripts contain only {count} occurrence(s) of canonical "
            f"{new!r}; expected at least {min_new_count}"
        )
