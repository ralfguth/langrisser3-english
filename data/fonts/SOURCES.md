# Font sources

External font assets used by the build pipeline. All third-party fonts
listed here are used under their original licenses; this directory is the
canonical project location for them so anyone can reproduce the build
without hunting external URLs.

## Mx437_CL_EagleIII_8x16.ttf

- **Family**: Mx437 CL Eagle III 8x16
- **Variant**: Mx (mixed outline + embedded bitmap; the embedded bitmap is
  pulled when PIL rasterizes at SIZE=16 with mode `'1'` / FreeType
  `FT_LOAD_TARGET_MONO`).
- **Source pack**: VileR — *The Ultimate Oldschool PC Font Pack*, **v2.2**
- **Pack URL**: <https://int10h.org/oldschool-pc-fonts/download/>
- **Pack file fetched**: `oldschool_pc_font_pack_v2.2_linux.zip`
  (SHA256 `b30dc3ecc9931ad2dd8be7517dd01813c8834a1911b582ab7643191b41a3d759`)
- **Path inside zip**: `ttf - Mx (mixed outline+bitmap)/Mx437_CL_EagleIII_8x16.ttf`
- **TTF SHA256**: `2cd0c5dce071b8518fcf7b476cc32abc59a09636f9b09f748f00e86d8fc2dc9b`
- **TTF size**: 50,412 bytes (mtime 2020-11-21)
- **Original face origin**: Cirrus Logic CL-GD5320 video BIOS (v3.08), 8×16 ROM glyphs.
- **License**: CC BY-SA 4.0 (per VileR, "All fonts here are free for use under
  the CC BY-SA 4.0 license"). Attribution: VileR / int10h.org.

### How it is used

`tools/font_jbm_generate.py` rasterizes this TTF at 8×16 / 16×16 cells via
PIL `Image.new('1', ...)` (FreeType MONO), emitting Python `bytes.fromhex()`
literals that get hand-pasted into `tools/font_tools.py`. The build pipeline
itself does **not** import the TTF — the inline hex bytes in `font_tools.py`
are the source of truth at build time. The TTF lives here for reproducibility
of the regeneration step.

### Regeneration

```bash
python3 tools/font_jbm_generate.py > /tmp/eagle3_glyphs.py
# Hand-paste the dict literals into tools/font_tools.py.
```
