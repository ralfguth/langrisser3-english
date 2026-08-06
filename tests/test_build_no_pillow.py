"""The build must run with a bare Python — no Pillow (issue #7).

Red state (v0.7.0): tools/title_dg2.py read the mandatory title-credit PNG
through `from PIL import Image`. Users who patch with a stock Python 3 got
six clean build steps and then a hard crash in step 6:

    ModuleNotFoundError: No module named 'PIL'

...with a half-built ISO and no patch. v0.6.1 had no such step and worked, so
the regression was ours. These tests block PIL at import time and pin that the
title path still decodes the indexed PNG byte-identically.

The goldens below were produced by Pillow 11 on the shipping asset, so a
future stdlib decoder can never silently drift from what Pillow saw.
"""
import hashlib
import importlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

ASSET = REPO / "assets" / "title_credit" / "title_credit_indexed.png"

# Pillow-produced goldens for assets/title_credit/title_credit_indexed.png.
PIX_SHA256 = "5c563eb3b7cf330a282f3c5e8612297b0fc05787a46633dd162cf5186df4f911"
PAL_SHA256 = "b6fd5950cc0d668984529763d67f49dd95c791596b9e1a35b7026d1bda55b980"


class _BlockPIL:
    """meta_path finder that makes `import PIL` fail like a machine without it."""

    def find_spec(self, name, path=None, target=None):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("No module named 'PIL' (blocked by test)")
        return None


@pytest.fixture
def no_pillow():
    """Run the body on a Python where Pillow does not exist."""
    saved_modules = {k: v for k, v in sys.modules.items()
                     if k == "PIL" or k.startswith("PIL.")}
    for k in saved_modules:
        del sys.modules[k]
    blocker = _BlockPIL()
    sys.meta_path.insert(0, blocker)
    # Drop the build-path modules so they re-import under the blocker.
    for name in ("title_dg2", "tools.title_dg2", "png_indexed", "tools.png_indexed"):
        sys.modules.pop(name, None)
    try:
        with pytest.raises(ImportError):
            importlib.import_module("PIL")
        yield
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved_modules)
        for name in ("title_dg2", "tools.title_dg2", "png_indexed", "tools.png_indexed"):
            sys.modules.pop(name, None)


def _pix_bytes(px, w, h):
    return bytes(px[x, y] for y in range(h) for x in range(w))


def test_indexed_png_pixels_decode_without_pillow(no_pillow):
    """The exact call that crashed the user's build: _read_indexed_png on the
    mandatory credit asset."""
    title_dg2 = importlib.import_module("title_dg2")
    w, h, px = title_dg2._read_indexed_png(str(ASSET))
    assert (w, h) == (320, 224)
    assert hashlib.sha256(_pix_bytes(px, w, h)).hexdigest() == PIX_SHA256


def test_indexed_png_palette_decodes_without_pillow(no_pillow):
    title_dg2 = importlib.import_module("title_dg2")
    pal = title_dg2._indexed_png_palette(str(ASSET))
    assert len(pal) == 256
    flat = bytes(c for rgb in pal for c in rgb)
    assert hashlib.sha256(flat).hexdigest() == PAL_SHA256


def test_build_module_imports_without_pillow(no_pillow):
    """`python3 build.py` must not die on import either — every module the
    build pulls in has to be Pillow-free."""
    sys.modules.pop("build", None)
    try:
        importlib.import_module("build")
    finally:
        sys.modules.pop("build", None)


def test_pillow_and_stdlib_decoders_agree():
    """Belt and braces: when Pillow IS installed, both paths must produce the
    same pixels and palette (no silent drift in the shipped asset)."""
    pytest.importorskip("PIL")
    from PIL import Image

    png_indexed = importlib.import_module("png_indexed")
    im = Image.open(ASSET)
    w, h = im.size
    pil_px = im.load()
    own_w, own_h, own_px = png_indexed.read_indexed_png(str(ASSET))
    assert (own_w, own_h) == (w, h)
    assert _pix_bytes(own_px, w, h) == _pix_bytes(pil_px, w, h)

    pil_pal = list(im.getpalette() or [])
    pil_pal += [0] * (768 - len(pil_pal))
    own_pal = png_indexed.read_indexed_palette(str(ASSET))
    assert bytes(c for rgb in own_pal for c in rgb) == bytes(pil_pal)


@pytest.mark.parametrize("bit_depth", [1, 2, 4, 8])
def test_stdlib_decoder_handles_every_indexed_bit_depth(tmp_path, bit_depth):
    """Artists export indexed PNGs at whatever depth their tool picks; a 4-bit
    export must not become a cryptic crash mid-build."""
    pytest.importorskip("PIL")
    from PIL import Image

    png_indexed = importlib.import_module("png_indexed")
    n = 2 ** bit_depth
    im = Image.new("P", (37, 11))
    px = im.load()
    for y in range(11):
        for x in range(37):
            px[x, y] = (x * 7 + y * 3) % n
    p = tmp_path / f"depth{bit_depth}.png"
    im.save(p, bits=bit_depth)

    w, h, own = png_indexed.read_indexed_png(str(p))
    ref = Image.open(p).load()
    assert (w, h) == (37, 11)
    assert _pix_bytes(own, w, h) == _pix_bytes(ref, w, h)
