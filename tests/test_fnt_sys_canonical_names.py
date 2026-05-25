"""Assert that patches/fnt_sys.bin contains the CANONICAL encoded
forms of character names, not the obsolete CWX-era variants.

fntsys*E.txt scripts are NOT compiled by build.py — patches/fnt_sys.bin
ships as a same-size overlay. When a character is renamed in the
script canon (Altemuller → Altemüller, Bozel → Böser, etc.), the
fnt_sys.bin blob silently retains the old encoded byte sequence until
someone runs an in-place hex patch.

These tests cross-check the binary blob against the encoder output
for each canonical name to catch this drift.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "tools"))

import pytest
from tools.font_tools import CHAR_TILE_MAP, BIGRAM_TILE_MAP
from tools.d00_tools import encode_text_to_entry

FNT_SYS_PATH = PROJECT_DIR / "patches" / "fnt_sys.bin"


@pytest.fixture(scope="module")
def fnt_sys_bytes() -> bytes:
    if not FNT_SYS_PATH.exists():
        pytest.skip(f"fnt_sys.bin not present at {FNT_SYS_PATH}")
    return FNT_SYS_PATH.read_bytes()


def _encode(text: str) -> bytes:
    return encode_text_to_entry(text, CHAR_TILE_MAP, BIGRAM_TILE_MAP)


# (obsolete_form, canonical_form, expected_min_occurrences_of_canonical)
NAME_RENAMES = [
    ("Dieharte",   "Diehärte",   4),   # protagonist placeholder + name-input grid
    ("Altemuller", "Altemüller", 4),   # field marshal name (multiple slots)
    ("Bozel",      "Böser",      1),   # demon overlord
    ("Riguler",    "Rigüler",    4),   # empire name
]


class TestFntSysCanonicalNames:
    """fnt_sys.bin must contain only the canonical (renamed) byte
    sequences for character names, not the obsolete CWX-era forms."""

    @pytest.mark.parametrize("old,new,min_new_count", NAME_RENAMES)
    def test_old_form_absent(self, old, new, min_new_count, fnt_sys_bytes):
        old_bytes = _encode(old)
        count = fnt_sys_bytes.count(old_bytes)
        assert count == 0, (
            f"fnt_sys.bin still contains {count} occurrence(s) of obsolete "
            f"{old!r} (encoded {old_bytes.hex()}). Run the in-place patch to "
            f"rename to {new!r} (encoded {_encode(new).hex()})."
        )

    @pytest.mark.parametrize("old,new,min_new_count", NAME_RENAMES)
    def test_new_form_present(self, old, new, min_new_count, fnt_sys_bytes):
        new_bytes = _encode(new)
        count = fnt_sys_bytes.count(new_bytes)
        assert count >= min_new_count, (
            f"fnt_sys.bin contains only {count} occurrence(s) of canonical "
            f"{new!r} (encoded {new_bytes.hex()}); expected at least "
            f"{min_new_count}."
        )

    @pytest.mark.parametrize("old,new,min_new_count", NAME_RENAMES)
    def test_byte_lengths_match(self, old, new, min_new_count):
        """In-place patch requires same byte length."""
        old_len = len(_encode(old))
        new_len = len(_encode(new))
        assert old_len == new_len, (
            f"Cannot patch {old!r}→{new!r} in place: old={old_len}B, new={new_len}B"
        )
