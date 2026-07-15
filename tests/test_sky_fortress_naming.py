"""Guard: 空中要塞 (the Empire's excavated flying fortress, Geier's) must render
as "Sky Fortress", DISTINCT from 浮遊城 = "Floating Castle" (Larcuss's prologue
castle, destroyed in scen002).

Red state (before the original fix): commit a40de99 wrongly unified 空中要塞 →
"Floating Castle" corpus-wide, conflating two different structures. These 10 scen
files reference 空中要塞 and NEVER 浮遊城 (verified), so any "Floating Castle" in
them is the mis-rendered Sky Fortress.

Red state (this hardening, v0.6 review): the original substring check missed the
WRAP-SPLIT form ``Floating<$FFFC>Castle`` — a control code sits between the two
words, so ``"Floating Castle" in text`` was False even though the leak renders as
"Floating Castle" in-game. scen022 and scen081 (Sky-Fortress files) plus plotE
SC-19/30/31 (空中要塞 blocks) leaked through that gap. The guard now strips
``<$...>`` codes before matching, and checks plotE per scenario block (plotE is
mixed: SC-01 is the real 浮遊城, SC-19/30/31 are 空中要塞).
"""
import re
from pathlib import Path

EN = Path(__file__).resolve().parent.parent / "scripts" / "en"

# Files that mention 空中要塞 and NOT 浮遊城 (so "Floating Castle" here = a bug).
SKY_FORTRESS_FILES = [
    "scen022E.txt", "scen069E.txt", "scen079E.txt", "scen081E.txt",
    "scen082E.txt", "scen083E.txt", "scen084E.txt", "scen085E.txt",
    "scen101E.txt", "scen102E.txt",
]

# Prologue files that legitimately carry 浮遊城 = "Floating Castle".
PROLOGUE_FLOATING_CASTLE = ["scen042E.txt", "scen002E.txt"]

# plotE is MIXED. Verified against scripts/jp/plotJ.txt:
#   SC-01 (<$FFF80001>) → 浮遊城  → "Floating Castle" (stays)
#   SC-19 (<$FFF80013>) → 空中要塞 → "Sky Fortress"
#   SC-30 (<$FFF8001E>) → 空中要塞 → "Sky Fortress"
#   SC-31 (<$FFF8001F>) → 空中要塞 → "Sky Fortress"
PLOT = EN / "plotE.txt"
PLOT_SKY_FORTRESS_MARKERS = ["<$FFF80013>", "<$FFF8001E>", "<$FFF8001F>"]
PLOT_FLOATING_CASTLE_MARKER = "<$FFF80001>"

_CODE = re.compile(r"<\$[0-9A-Fa-f]+>")


def _strip(text: str) -> str:
    """Drop ``<$...>`` control codes so a wrap-split term reads as plain prose.

    Codes become a single space, then runs of whitespace collapse, so
    ``Floating<$FFFC>Castle`` and ``Floating Castle`` both normalize to
    ``Floating Castle``.
    """
    return re.sub(r"\s+", " ", _CODE.sub(" ", text))


def _plot_block(marker: str) -> str:
    """Return the stripped text of the plotE line carrying a scenario marker."""
    for line in PLOT.read_text(encoding="utf-8").splitlines():
        if marker in line:
            return _strip(line)
    raise AssertionError(f"plotE marker {marker} not found")


def test_sky_fortress_files_have_no_floating_castle():
    """No 空中要塞-only file may say 'Floating Castle' — wrap-splits included."""
    offenders = {}
    for name in SKY_FORTRESS_FILES:
        text = _strip((EN / name).read_text(encoding="utf-8"))
        if "Floating Castle" in text:
            offenders[name] = text.count("Floating Castle")
    assert not offenders, f"'Floating Castle' leaked into Sky Fortress files: {offenders}"


def test_sky_fortress_term_is_present():
    """The distinct term must actually appear after the sweep."""
    corpus = "".join(
        (EN / name).read_text(encoding="utf-8") for name in SKY_FORTRESS_FILES
    )
    assert "Sky Fortress" in corpus


def test_prologue_keeps_floating_castle_and_not_sky_fortress():
    """The real 浮遊城 must stay 'Floating Castle' and never become Sky Fortress."""
    for name in PROLOGUE_FLOATING_CASTLE:
        text = _strip((EN / name).read_text(encoding="utf-8"))
        assert "Floating Castle" in text, f"{name} lost its 浮遊城 term"
        assert "Sky Fortress" not in text, f"{name} wrongly got a Sky Fortress"


def test_plot_sky_fortress_scenarios_render_sky_fortress():
    """plotE SC-19/30/31 are 空中要塞 → 'Sky Fortress', not 'Floating Castle'."""
    offenders = {}
    for marker in PLOT_SKY_FORTRESS_MARKERS:
        block = _plot_block(marker)
        if "Floating Castle" in block or "Sky Fortress" not in block:
            offenders[marker] = block
    assert not offenders, (
        "plotE 空中要塞 blocks must say 'Sky Fortress', not 'Floating Castle': "
        f"{list(offenders)}"
    )


def test_plot_prologue_scenario_keeps_floating_castle():
    """plotE SC-01 is the 浮遊城 prologue → keeps 'Floating Castle', no Sky Fortress."""
    block = _plot_block(PLOT_FLOATING_CASTLE_MARKER)
    assert "Floating Castle" in block, "plotE SC-01 lost its 浮遊城 term"
    assert "Sky Fortress" not in block, "plotE SC-01 wrongly got a Sky Fortress"
