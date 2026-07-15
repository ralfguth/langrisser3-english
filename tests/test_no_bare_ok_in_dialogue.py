"""Casual affirmative "OK" must not appear bare in scen dialogue.

Bug (playtest 2026-06-13, screenshot 16:08): Pierre's line rendered as
"O K! Will do." — the two adjacent uppercase letters O+K map to the
CENTERED full-width tiles 17-42 (each a half-width glyph centered in a
16px tile with padding), so they read as "O K" with a gap. JP wrote it
full-width (ＯＫ / オッケー), which is tight on the JP font but gappy on
ours until the deferred FONT.BIN half-width-caps rebuild.

    Red state: scen005E/035E/041E/125E each begin an entry with "OK!".

Fix: use lowercase "Okay!" — it encodes via the tight Ok/ay bigrams and
keeps the casual, peppy tone. This guard bans the bare uppercase word so
the defect cannot return. (All-caps SFX/onomatopoeia, acronyms like NPC/HQ,
and emphasis words are a deliberate, separate style and are NOT covered.)
"""
import glob
import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
BARE_OK = re.compile(r"\bOK\b")


def test_no_bare_ok_word_in_scen_dialogue():
    offenders = []
    for path in sorted(glob.glob(str(PROJ / "scripts/en/scen*E.txt"))):
        for ln, line in enumerate(Path(path).read_text(encoding="utf-8")
                                  .splitlines(), 1):
            if BARE_OK.search(line):
                offenders.append(f"{Path(path).name}:{ln}  {line[:40]!r}")
    assert not offenders, (
        "bare 'OK' renders as centered 'O K'; use 'Okay':\n  "
        + "\n  ".join(offenders)
    )
