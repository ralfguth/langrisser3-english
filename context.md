# Langrisser III English Translation - Context

## Arquitetura do projeto

### Pipeline: `python3 build.py`
1. Lê JP ISO (Track 01 bin, 2352 bytes/setor Mode 1)
2. Extrai FONT.BIN e D00.DAT via ISO9660 parsing
3. Carrega CWX font.bin como FONT.BIN (preserva bigrams + UI tiles)
4. Encoda scripts EN com bigram encoding no D00.DAT
5. Aplica patches CWX (menus/UI) in-place
6. **Patcha D00.DAT IN-PLACE** (NÃO rebuild) — usa `patch_d00_inplace()`
7. Monta CD image final (track01 + audio tracks)

### Limitação crítica: acesso direto por setor
O game engine do Saturn lê arquivos por setor absoluto na ISO, NÃO pelo filesystem ISO9660.
- **Nenhum arquivo pode ser realocado** (mover D00.DAT ou S00.CHR = tela preta)
- **D00.DAT deve caber no espaço original**: extent 10528, 1859 setores = 3,807,232 bytes
- **S00.CHR** está logo depois (extent 12387) — sem gap
- `rebuild_d00()` em d00_tools.py: **NÃO USAR** (realoca, causa tela preta)
- `patch_d00_inplace()`: **USAR ESTE** — patcha seções dentro do D00.DAT original
  - Usa espaço alocado real (sector gap entre seções adjacentes)
  - Seções que cabem → EN; que não cabem → mantém JP original

### Sistema de bigrams (tile compression)
- Cada tile 16x16 contém DOIS caracteres de 8px lado a lado
- Resultado: ~24 chars/linha em vez de ~12 (dobrando a capacidade)
- CWX font.bin tem 1319 bigram tiles verificados (801 LC + 518 UC)
- Encoder em d00_tools.py faz matching greedy left-to-right de bigrams
- Fallback para single-char tiles quando não há bigram disponível

### Dois sistemas de fonte independentes
- **FONT.BIN** (54,112 bytes = 1691 tiles x 32 bytes): Usado pelo D00.DAT (diálogos)
  - CWX font.bin é usado DIRETAMENTE como FONT.BIN
- **FNT_SYS.BIN** (56,804 bytes): Fonte do sistema para menus/UI
  - CWX substitui 84% dele com glyphs EN

### UI tiles dentro de grupos de bigram (CRÍTICO)
Mapeamento deve PULAR posições de UI tiles:
- LC: m (offsets 15,22), p (4), y (18,19)
- UC: E (22), F (19), N (23)
- Validação: `test_font.py::TestBigramTileMapRegression`

### D00.DAT (cenários/diálogos)
- 125 seções, cada uma: header -> script bytecode -> text block (17 pointers) -> text area
- Text area: offset table + entries (2-byte BE tile codes)
- Control codes: FFFF=terminator, FFFE=end dialogue, FFFC=newline, FFFD=scroll, F600=name var
- Control codes não-standard: F702-F708 (120 ocorrências), FE** (temporizadores/efeitos)
- Áudio dos diálogos: controlado pelo bytecode (pre_text_data), não pelo texto

### CWX v0.2 patch (lang3a2/)
8 arquivos same-size: font.bin, fnt_sys.bin, prog_3-6.bin, a0lang.bin, syswin.bin

### Scripts EN (scripts/en/)
- 125 arquivos scen001E.txt a scen125E.txt (formato Akari Dawn)
- **Chars não-mapeados**: ä, ü, ö nos scripts são DROPADOS silenciosamente pelo encoder
  - Diehärte→Diehrte (errado!), Altemüller→Altemller, Jügler→Jgler, Böser→Bser
  - T8 pendente: substituir ä→a, ü→u, ö→o

### Ferramentas (tools/)
- `iso_tools.py`: ISO9660 Mode 1/2352 parsing, EDC/ECC, patch files
- `d00_tools.py`: Parse/encode/rebuild D00.DAT (com bigram encoding)
- `font_tools.py`: CWX font.bin loader, tile maps, UI tile skip logic
- `jp_dumper.py`: Dump scripts JP do D00.DAT
- `script_cleaner.py`: Limpeza de scripts EN

### Testes (tests/) — 35 testes
- `test_entry_counts.py`: Valida contagem de entries JP vs EN
- `test_d00.py`: Parsing, round-trip, encoding, script parsing, in-place patching
- `test_font.py`: Char tile map, bigram regression, font patching

## Decisões técnicas
- Não usar CWX como base do PROJETO — começar sempre do JP ISO
- MAS reusar font.bin do CWX como FONT.BIN (preserva bigrams + UI tiles)
- Corrigir dados nos scripts, não nos parsers
- D00.DAT: **patch in-place** (não rebuild) — seções que não cabem ficam JP
- Bigram encoding: greedy left-to-right, fallback single-char

## Análise de tamanho D00.DAT (ver d00_size_report.md para detalhes)
- JP: 3,807,232 bytes | EN original: 4,018,176 (+210,944)
- Estado inicial do T10: 46 cabiam, 79 overflow (total 112,532 bytes)
- Após trimming parcial: 101 cabiam, 24 overflow
- Estado atual: **125 cabem, 0 overflow**
- `d00_size_report.md` foi regenerado como snapshot completo do estado atual

## Estado atual do build (2026-04-10)
```
125 sections patched EN, 0 kept JP
D00.DAT: 3,807,232 bytes (same as original)
CWX menu patches: 7 files
35 tests passing
Jogo carrega OK — todas as 125 seções de cenário são aplicadas em EN
```
**T10 concluido: 46→125 seções EN.**

### Método de encurtamento
- Medir o espaço real disponível por seção usando `measure.py`
- Trabalhar com diff alvo entre `0` e `+50`
- Priorizar seções com maior overflow real
- Seguir tom japonês (conciso, direto) em vez do tom prolixo do EN
- Preservar lore, personalidade, informação de gameplay
- Cortar filler words, reformular frases longas, simplificar quiz/trivia text
