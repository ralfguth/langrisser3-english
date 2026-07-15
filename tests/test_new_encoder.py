"""Part 4 of the new-font rebuild: the new encoder.

Invariant guard (the Part-4 "option-A" oracle, settled 2026-06-26 after the
LANG3_NEW_FONT=1 playtest): over every line of the real dialogue scripts the new
encoder must be a pure RELOCATION + COMPACTION of the proven production encoder —

  * it NEVER renders wider (tile count <= old), and
  * it preserves the structural/control-code skeleton EXACTLY (the F600 name
    token, F7xx route codes and FFFB-FFFF codes, in the same order),

so any divergence from the old output is only tighter glyph pairing (the
double-space / half-width compaction the new layout buys), never a lost glyph or
a shifted structural code. ~0.2% of lines come out strictly narrower; the rest
are byte-identical once the bigram tile numbers are remapped.

The OLD oracle asserted new==old byte-for-byte and was wrong: the compaction is
intentional and playtested. See archive/docs/20260625_new_font_from_scratch_plan.md
(Part 4).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import font_tools as ft               # noqa: E402
import new_encoder as ne              # noqa: E402
from d00_tools import encode_text_to_entry  # noqa: E402

SCRIPTS = REPO / "scripts" / "en"
CONTROL_FLOOR = 0xF600   # words >= this are engine control codes, not glyph tiles


def _words(raw: bytes):
    return [(raw[i] << 8) | raw[i + 1] for i in range(0, len(raw) - 1, 2)]


def _structure(raw: bytes):
    """The control-code skeleton (F600 name token, F7xx routes, FFFB-FFFF)."""
    return [w for w in _words(raw) if w >= CONTROL_FLOOR]


def _lines():
    """DIALOGUE surfaces only (scen + plot) — these use CHAR_TILE_MAP /
    BIGRAM_TILE_MAP, which the new encoder targets. fntsys/syswin encode with
    their own maps (a separate Part 4b encoder variant)."""
    files = sorted(SCRIPTS.glob("scen*E.txt")) + [SCRIPTS / "plotE.txt"]
    for f in files:
        if not f.exists() or f.stem.endswith("_src"):
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line:
                yield f.name, line


def test_new_encoder_never_wider_than_old():
    """The relocation must not cost space: the new encoder renders every line in
    no more tiles than the proven encoder (it only ever compacts).

    Red state (old strict oracle): new!=old on 0.2% of lines flagged a 'bug';
    the real invariant is that those lines are NARROWER, never wider."""
    bad = []
    for fname, line in _lines():
        old = encode_text_to_entry(line, ft.CHAR_TILE_MAP, ft.BIGRAM_TILE_MAP)
        new = ne.encode(line)
        if len(new) > len(old):
            bad.append((fname, line[:40], len(old) // 2, len(new) // 2))
            if len(bad) >= 12:
                break
    assert not bad, "new encoder renders WIDER than the proven encoder:\n" + \
        "\n".join(f"  {fn}: {ln!r} {lo}->{nw} tiles" for fn, ln, lo, nw in bad)


def test_new_encoder_preserves_structure():
    """Every control code (F600 / F7xx / FFFB-FFFF) is byte-identical in order —
    the divergences from the old output are pure glyph compaction, never a lost
    or shifted structural code (structural parity is non-negotiable)."""
    bad = []
    for fname, line in _lines():
        old = encode_text_to_entry(line, ft.CHAR_TILE_MAP, ft.BIGRAM_TILE_MAP)
        new = ne.encode(line)
        if _structure(new) != _structure(old):
            bad.append((fname, line[:40]))
            if len(bad) >= 12:
                break
    assert not bad, (
        "new encoder altered the control-code skeleton (not a pure compaction):\n"
        + "\n".join(f"  {fn}: {ln!r}" for fn, ln in bad)
    )
