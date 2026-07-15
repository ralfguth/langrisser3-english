"""Bigram pairing must STOP at <$FFFE> (entry terminator) and <$FFFC> (line
break) and restart the column fresh — never compose one tile from characters on
opposite sides of such a code (user principle, 2026-06-25: "parar no FFFE e
começar novamente na próxima linha").

Deterministic proof: encoding a whole entry must equal encoding each
FFFE/FFFC-delimited piece independently and concatenating (with the codes
between). If they match, no bigram straddles the boundary. Covers both the
production encoder and the new-layout encoder.
"""
import re
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import font_tools as ft                       # noqa: E402
import new_encoder as ne                      # noqa: E402
from d00_tools import encode_text_to_entry    # noqa: E402

SCRIPTS = REPO / "scripts" / "en"
SPLIT = re.compile(r"(<\$FFF[CE]>)")


def _code_bytes(tok: str) -> bytes:
    return struct.pack(">H", int(tok[2:6], 16))


def _dialogue_lines():
    files = sorted(SCRIPTS.glob("scen*E.txt")) + [SCRIPTS / "plotE.txt"]
    for f in files:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line:
                yield f.name, line


def _crosses(enc, line: str) -> bool:
    full = enc(line)
    recon = bytearray()
    for piece in SPLIT.split(line):
        if not piece:
            continue
        recon += _code_bytes(piece) if SPLIT.fullmatch(piece) else enc(piece)
    return bytes(recon) != full


def test_old_encoder_never_crosses_fffe_or_fffc():
    enc = lambda t: encode_text_to_entry(t, ft.CHAR_TILE_MAP, ft.BIGRAM_TILE_MAP)
    bad = [fn + ": " + repr(ln[:50]) for fn, ln in _dialogue_lines() if _crosses(enc, ln)]
    assert not bad, "bigram crosses an FFFE/FFFC boundary:\n" + "\n".join(bad[:12])


def test_new_encoder_never_crosses_fffe_or_fffc():
    bad = [fn + ": " + repr(ln[:50]) for fn, ln in _dialogue_lines() if _crosses(ne.encode, ln)]
    assert not bad, "new encoder crosses an FFFE/FFFC boundary:\n" + "\n".join(bad[:12])
