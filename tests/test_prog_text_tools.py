"""test_prog_text_tools.py — lock the prog_3 magic-name encoder contract.

Caminho B of the 0.2 patch disembark (branch new-ui-patch). The encoder
replaces the static prog_3 magic-name slot writes (formerly in
tools/byte_overlays.py PROG_3_OVERLAY) with a script-driven generator
that reads scripts/en/prog3_magicE.txt. These tests pin the encoder
output so future translation edits can't silently break layout
(slot count, slot width, stride, ASCII-only, null padding).
"""

from pathlib import Path

import pytest

from tools import prog_text_tools as ptt


PROJ = Path(__file__).resolve().parent.parent
SCRIPT = PROJ / "scripts" / "en" / "prog3_magicE.txt"
SKILL_SCRIPT = PROJ / "scripts" / "en" / "prog3_skillE.txt"


def test_default_script_exists():
    assert SCRIPT.exists(), f"missing default script {SCRIPT}"


def test_encoder_emits_one_entry_per_slot():
    entries = ptt.encode_prog3_magic_table()
    assert len(entries) == ptt.PROG3_MAGIC_COUNT == 55


def test_encoder_writes_at_stride_aligned_offsets():
    entries = ptt.encode_prog3_magic_table()
    for i, (off, chunk) in enumerate(entries):
        assert off == ptt.PROG3_MAGIC_TABLE_BASE + i * ptt.PROG3_MAGIC_STRIDE
        assert len(chunk) == ptt.PROG3_MAGIC_NAME_WIDTH
        # ASCII-only; tail must be null-padded.
        assert all(b < 0x80 for b in chunk)


def test_known_slots_match_canonical_names():
    """Spot-check the slots that historically mattered.

    Slots 12+13 are the HP/MP Drain pair where the old static overlay
    wrote only the ' Drain' tail; the encoder now owns the full slot.
    """
    entries = dict(ptt.encode_prog3_magic_table())
    assert entries[0x3394C].rstrip(b"\x00") == b"Fire"
    assert entries[0x33A3C].rstrip(b"\x00") == b"HP Drain"
    assert entries[0x33A50].rstrip(b"\x00") == b"MP Drain"
    # ビルダー = "Builder" (Cho Aniki cameo: Adon/Samson's Builder Planet),
    # NOT the Norse "Baldur" — the summon set carries Masaya self-references.
    assert entries[0x33D84].rstrip(b"\x00") == b"Builder"


def test_encoded_overlays_targets_prog_3():
    overlays = ptt.encoded_overlays()
    assert "LANG/PROG_3.BIN" in overlays
    expected = (ptt.encode_prog3_skill_pointers()
                + ptt.encode_prog3_skill_table()
                + ptt.encode_prog3_magic_table())
    assert overlays["LANG/PROG_3.BIN"] == expected


# ---- skill table ----

def test_skill_script_exists():
    assert SKILL_SCRIPT.exists(), f"missing {SKILL_SCRIPT}"


def test_skill_encoder_emits_one_entry_per_slot():
    entries = ptt.encode_prog3_skill_table()
    assert len(entries) == ptt.PROG3_SKILL_COUNT == 9


def test_skill_encoder_writes_at_pointer_defined_offsets():
    """The table is POINTER-INDEXED (see prog_text_tools), NOT uniform stride.
    Each entry must land on its pointer-defined offset and be ASCII."""
    entries = ptt.encode_prog3_skill_table()
    for (off, chunk), want_off in zip(entries, ptt.PROG3_SKILL_OFFSETS):
        assert off == want_off
        assert all(b < 0x80 for b in chunk)


def test_skill_known_slots_match_canonical_names():
    """Treatment[7]/Item[8] sit at their DEDICATED pointer offsets (0x331A6 /
    0x331B0), not the uniform-stride 0x331A0/0x331AC. Writing them uniform was
    the in-game "Treatment" -> "ent" bug (the pointer reads 0x331A6). Each name
    is NUL-terminated within its slot. See tests/test_prog3_skill.py."""
    entries = dict(ptt.encode_prog3_skill_table())
    assert entries[0x3314C].rstrip(b"\x00") == b"Kiai Shout"
    assert entries[0x33170].rstrip(b"\x00") == b"Berserk"
    assert entries[0x33194].rstrip(b"\x00") == b"Double Magic"
    assert entries[0x33194].endswith(b"\x00")          # must be NUL-terminated
    assert entries[0x331A6].rstrip(b"\x00") == b"Treatment"
    assert entries[0x331B0].rstrip(b"\x00") == b"Item"


def test_skill_does_not_touch_metadata_at_0x331b8():
    """The metadata array starts at PROG3_SKILL_REGION_END = 0x331B8.
    No encoder write may extend into that range."""
    for off, chunk in ptt.encode_prog3_skill_table():
        assert off + len(chunk) <= 0x331B8, (
            f"encoder write 0x{off:X}+{len(chunk)} crosses into metadata at 0x331B8"
        )


def test_skill_overlong_name_rejected(tmp_path):
    script = tmp_path / "prog3_skillE.txt"
    lines = ["Kiai"] * (ptt.PROG3_SKILL_COUNT - 1) + ["ThisNameIsTooLong"]
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bytes > slot"):
        ptt.encode_prog3_skill_table(script_path=script)


def test_overlong_name_rejected(tmp_path):
    script = tmp_path / "prog3_magicE.txt"
    lines = ["Fire"] * (ptt.PROG3_MAGIC_COUNT - 1) + ["ThisNameIsWayTooLong"]
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bytes > slot"):
        ptt.encode_prog3_magic_table(script_path=script)


def test_wrong_line_count_rejected(tmp_path):
    script = tmp_path / "prog3_magicE.txt"
    script.write_text("Fire\nIce\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected 55 lines"):
        ptt.encode_prog3_magic_table(script_path=script)
